/*
 * EFM-BD et EFM-SD du Machinedrum (SPS-1 UW, OS 1.63), portes a l'echantillon pres depuis le code du DSP A :
 *   EFM-BD : P:$102eef (init), $102ef3 (trig), $102f06 (rendu) ; potards : fonction ColdFire 0x20211c ;
 *   EFM-SD : P:$102f68, $102f6f, $102f85 ; potards : 0x2021fc.
 * Tout tient sur 32 bits : chaque produit du DSP (mpy, mpyr) est calcule en partie entiere floor(x y / 2^23) et reste
 * x y mod 2^23 (hilo) ; les phases et le retour, de 48 bits sur le DSP, ne servent que par additions et par les
 * 15 bits de l'index : partie entiere (modulo 2^32) + fraction de 24 bits. Memes sorties que le DSP emule.
 *
 * Synthese : un modulateur sinus avec retour sur lui-meme (MFB) module la porteuse ; l'indice de modulation est
 * proportionnel a la hauteur. EFM-BD ajoute une enveloppe de hauteur (RAMP, RDEC) ; EFM-SD un bruit de Fibonacci
 * filtre (passe-haut fixe) puis un passe-haut sur toute la sortie (HPF).
 */
#include "efm.h"
#include "trx_b2.h"                                      /* trx_b2_sine, trx_b2_pitch_tbl, md_lut */

static inline int32_t s24(uint32_t v) { return (int32_t)(v << 8) >> 8; }
static inline int32_t sat24(int32_t v) { return v > 0x7fffff ? 0x7fffff : (v < -0x800000 ? -0x800000 : v); }

/* floor(x y / 2^23) (et x y mod 2^23 dans *lo), x et y sur 24 bits : moities de 12 bits, 3 multiplications
 * (Karatsuba), chaque produit tient sur 32 bits */
static inline int32_t hilo(int32_t x, int32_t y, int32_t *lo)
{
	const int32_t xh = x >> 12, xl = x & 0xfff, yh = y >> 12, yl = y & 0xfff;
	const int32_t hh = xh * yh, ll = xl * yl, mm = (xh + xl) * (yh + yl) - hh - ll;
	*lo = (int32_t)(((uint32_t)mm << 12) + (uint32_t)ll) & 0x7fffff;
	return 2 * hh + ((mm + (ll >> 12)) >> 11);
}

static inline int32_t hi23(int32_t x, int32_t y)
{
	int32_t lo;
	return hilo(x, y, &lo);
}

/* mpyr x,y : a1 apres l'arrondi convergent (sans repliement : 0x800000 possible) */
static inline int32_t rnd(int32_t x, int32_t y)
{
	int32_t l;
	const int32_t h = hilo(x, y, &l);
	return h + (l > 0x400000 || (l == 0x400000 && (h & 1)));
}

/* x y / 2^k (k = 4 ou 7, 48 bits) -> partie entiere et fraction de 24 bits */
static inline void prod_shr(int32_t x, int32_t y, int k, int32_t *i, int32_t *f)
{
	int32_t l;
	const int32_t h = hilo(x, y, &l);                     /* x y = h 2^23 + l */
	*i = h >> (k + 1);
	*f = ((h & ((2 << k) - 1)) << (23 - k)) + (l >> k);
}

/* --- potards (fonctions ColdFire) : mots de 16 bits = potard << 7 ; tables de l'OS du Machinedrum --- */

static int32_t pitch_word(int32_t d0, int32_t oct)       /* tbl[d0 & 0x7f] << (d0 >> 7) + oct */
{
	return s24((uint32_t)(trx_b2_pitch_tbl[d0 & 0x7f] << ((d0 >> 7) + oct)));
}

static int32_t lut(int32_t knob, int32_t mul)            /* 0x24bf94 + 0x24c + 4 * ((potard << 7) * mul >> 12) */
{
	return s24((uint32_t)md_lut[((knob << 7) * mul) >> 12]);
}

void efm_bd_set_knobs(efm_bd_t *v, const uint8_t k[8])  /* 0x20211c */
{
	const int32_t ptch = k[0], dec = k[1], ramp = k[2], rdec = k[3], mod = k[4], mfrq = k[5], mdec = k[6];
	const int32_t mfb = k[7];
	int32_t f;

	v->p[1] = pitch_word(((ptch << 7) >> 5) + 0x20, 1);
	v->p[2] = lut(dec, 0x46);
	f = (mfrq << 7) << 9;
	v->p[3] = s24((uint32_t)(f > 0xffff ? f : 0x10000));
	v->p[4] = s24((uint32_t)(((mod << 7) << 9) & 0x1fffe00));
	v->p[5] = lut(mdec, 0x52);
	v->p[6] = s24((uint32_t)(((mfb << 7) << 9) & 0x1fffe00));
	v->p[7] = s24((uint32_t)(((ramp << 7) << 9) - 0x100000));
	v->p[8] = lut(rdec, 0x4b);
}

void efm_sd_set_knobs(efm_sd_t *v, const uint8_t k[8])  /* 0x2021fc */
{
	const int32_t ptch = k[0], dec = k[1], nois = k[2], ndec = k[3], mod = k[4], mfrq = k[5], mdec = k[6];
	const int32_t hpf = k[7];
	int32_t f;

	v->p[1] = pitch_word((((ptch << 7) * 5) >> 8) + 0x40, 3);
	v->p[2] = lut(dec, 0x46);
	f = (mfrq << 7) << 9;
	v->p[3] = s24((uint32_t)(f > 0xffff ? f : 0x10000));
	v->p[4] = s24((uint32_t)(((mod << 7) << 9) & 0x1fffe00));
	v->p[5] = lut(mdec, 0x52);
	v->p[6] = 0x7a1200;
	v->p[7] = s24((uint32_t)(((nois << 7) << 8) & 0xffff00));
	v->p[8] = lut(ndec, 0x32);
	v->p[9] = 0x44aa20;
	v->p[10] = s24((uint32_t)(0x7fffff - ((hpf << 7) << 8)));
}

/* modulateur avec retour (MFB) : $102f2c..$102f42 / $102fe0..$102ff6 ; renvoie modulateur * enveloppe.
 * b = phase + retour ; index = a1 & 0x7fff ; phase = (index, fraction) - retour + increment */
static inline int32_t fm_mod(int32_t *pi, int32_t *pf, int32_t *fi, int32_t *ff, int32_t ratio, int32_t fbk,
			     int32_t pitch, int32_t *menv, int32_t mdec)
{
	const int32_t bf = *pf + *ff;
	const int32_t idx = (*pi + *fi + (bf >> 24)) & 0x7fff;
	const int32_t s = trx_b2_sine[idx], e = *menv;
	int32_t ii, fi_, f;

	prod_shr(pitch, ratio, 4, &ii, &fi_);
	f = (bf & 0xffffff) - *ff + fi_;
	*pi = idx - *fi + ii + (f >> 24);
	*pf = f & 0xffffff;
	prod_shr(fbk, s, 7, fi, ff);
	*menv = s24(hi23(mdec, e));
	return s24(rnd(e, s));
}

/* porteuse : $102f43..$102f51 / $102ff7..$103005 ; increment = pitch 2^16 + c mod / 16 */
static inline int32_t fm_carrier(int32_t *pi, int32_t *pf, int32_t m, int32_t pitch, int32_t mod)
{
	const int32_t c = s24(rnd(m, pitch));
	const int32_t s = trx_b2_sine[*pi & 0x7fff];
	int32_t ii, fi, f;

	prod_shr(c, mod, 4, &ii, &fi);
	f = *pf + ((pitch & 0xff) << 16) + fi;
	*pi = (*pi + (pitch >> 8) + ii + (f >> 24)) & 0x7fff;
	*pf = f & 0xffffff;
	return s;
}

/* --- EFM-BD --- */

void efm_bd_init(efm_bd_t *v)                            /* $102eef (le reste vient du trig) */
{
	v->ph1i = v->ph1f = v->ph2i = v->ph2f = v->fbi = v->fbf = 0;
	v->ramp = v->menv = v->aenv = 0;
}

void efm_bd_trig(efm_bd_t *v)                            /* $102ef3 */
{
	v->aenv = sat24(0x50c335 + v->aenv);
	v->ph1i = v->ph2i = 0xfa0;
	v->ph1f = v->ph2f = v->fbi = v->fbf = 0;
	v->ramp = v->p[7];
	v->menv = 0x7fffff;
}

int efm_bd_render(efm_bd_t *v, int32_t out[EFM_BLOCK])  /* $102f06 */
{
	const int32_t p1 = v->p[1], p2 = v->p[2], p3 = v->p[3], p4 = v->p[4], p5 = v->p[5], p6 = v->p[6];
	const int32_t p8 = v->p[8];
	int i;

	if (!v->aenv) {                                      /* ampli a zero : sortie nulle jusqu'au prochain trig, */
		for (i = 0; i < EFM_BLOCK; i++)                  /* qui remet tout le reste a zero */
			out[i] = 0;
		return 0;
	}
	for (i = 0; i < EFM_BLOCK; i++) {
		/* $102f25 : hauteur + enveloppe de RAMP */
		const int32_t r = v->ramp;
		int32_t l;
		const int32_t pitch = s24((uint32_t)(8 * hilo(r, p1, &l) + (l >> 20) + p1));
		int32_t m, s;
		v->ramp = s24(hi23(p8, r));
		/* enveloppe du modulateur eteinte : il ne compte plus jusqu'au trig, qui le remet a zero */
		m = v->menv ? fm_mod(&v->ph1i, &v->ph1f, &v->fbi, &v->fbf, p3, p6, pitch, &v->menv, p5) : 0;
		s = fm_carrier(&v->ph2i, &v->ph2f, m, pitch, p4);
		/* $102f52 : ampli */
		out[i] = s24(rnd(v->aenv, s));
		v->aenv = s24(hi23(p2, v->aenv));
	}
	return 1;
}

/* --- EFM-SD --- */

void efm_sd_init(efm_sd_t *v)                            /* $102f68 */
{
	v->aenv = v->nenv = 0;
	v->n0 = 0x789abc;
	v->n1 = 0;            /* y15 : laisse par la machine precedente sur le Machinedrum ; 0 apres le demarrage */
	v->ph1i = v->ph1f = v->ph2i = v->ph2f = v->fbi = v->fbf = 0;
	v->menv = 0;
	v->hs1 = v->ho1 = v->hs2 = v->ho2 = 0;
}

void efm_sd_trig(efm_sd_t *v)                            /* $102f6f */
{
	v->aenv = sat24(0x50c335 + v->aenv);
	v->ph1i = v->ph2i = 0x1f4;
	v->ph1f = v->ph2f = v->fbi = v->fbf = 0;
	v->hs1 = v->ho1 = v->hs2 = v->ho2 = 0;
	v->menv = 0x7fffff;
	v->nenv = 0x7fffff;
}

/* passe-haut a 1 pole, sur place : $102fbf..$102fdb (bruit) et $103019..$103035 (sortie) ;
 * c = coef/2 + 1/2 ; y[n] = c x[n] - c x[n-1] + coef y[n-1] (c x[n-1] : a1 garde du produit precedent) */
static void hpf(int32_t *buf, int32_t coef, int32_t *state, int32_t *last)
{
	const int32_t c = s24((uint32_t)((coef >> 1) + 0x400000));
	int32_t s = *state, y = *last, k;

	for (k = 0; k < EFM_BLOCK; k++) {
		const int32_t x = buf[k];
		int32_t l1, l2;
		const int32_t h = hilo(x, c, &l1);
		y = sat24(h + hilo(y, coef, &l2) + ((l1 + l2) >> 23) - s);
		s = s24(h);
		buf[k] = y;
	}
	*state = s;
	*last = y;
}

/* $102fac : bruit de Fibonacci modulo 2^24, 32 valeurs */
static void noise(efm_sd_t *v, int32_t nz[EFM_BLOCK])
{
	uint32_t a = (uint32_t)v->n0, b = (uint32_t)v->n1, c;
	int i;

	for (i = 0; i < EFM_BLOCK; i++) {
		c = (a + b) & 0xffffff;
		if (nz)
			nz[i] = s24(c);
		a = b;
		b = c;
	}
	v->n0 = s24(a);
	v->n1 = s24(b);
}

int efm_sd_render(efm_sd_t *v, int32_t out[EFM_BLOCK])  /* $102f85 */
{
	const int32_t p1 = v->p[1], p2 = v->p[2], p3 = v->p[3], p4 = v->p[4], p5 = v->p[5], p6 = v->p[6];
	const int32_t p7 = v->p[7], p8 = v->p[8];
	int32_t nz[EFM_BLOCK];
	int i;

	if (!v->aenv && !v->nenv) {                          /* ni ton ni bruit jusqu'au prochain trig (le bruit avance) : */
		noise(v, 0);                                     /* seule la fin du passe-haut de sortie peut encore sonner */
		for (i = 0; i < EFM_BLOCK; i++)
			out[i] = 0;
		if (!v->hs2 && !v->ho2)
			return 0;
		hpf(out, v->p[10], &v->hs2, &v->ho2);
		return 1;
	}
	/* enveloppe du bruit eteinte : son filtre ne compte plus jusqu'au trig, qui le remet a zero */
	noise(v, v->nenv ? nz : 0);
	if (v->nenv)
		hpf(nz, v->p[9], &v->hs1, &v->ho1);

	/* $102fde : FM + bruit */
	for (i = 0; i < EFM_BLOCK; i++) {
		const int32_t m = v->menv ? fm_mod(&v->ph1i, &v->ph1f, &v->fbi, &v->fbf, p3, p6, p1, &v->menv, p5) : 0;
		const int32_t s = fm_carrier(&v->ph2i, &v->ph2f, m, p1, p4);
		const int32_t tone = s24(rnd(v->aenv, s));
		const int32_t n = v->nenv ? s24(rnd(v->nenv, nz[i])) : 0;
		v->aenv = s24(hi23(p2, v->aenv));
		v->nenv = s24(hi23(p8, v->nenv));
		out[i] = sat24(rnd(n, p7) + tone);
	}
	hpf(out, v->p[10], &v->hs2, &v->ho2);
	return 1;
}
