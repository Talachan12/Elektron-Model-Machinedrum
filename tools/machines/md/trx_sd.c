/*
 * TRX-SD du Machinedrum (SPS-1 UW, OS 1.63), porte a l'echantillon pres depuis le code du DSP A :
 * P:$10074c (init), $10075b (trig), $100776 (rendu) ; potards : fonction ColdFire 0x2013a6.
 * Version rapide pour le ColdFire de trx_sd_ref.c (transcription instruction par instruction) : tout sur 32 bits
 * (mdmath.h), memes sorties que le DSP emule.
 *
 * Synthese : deux sinus (TONE : leur dosage, TUNE : l'ecart du 2e) avec une bosse de hauteur (BUMP, BENV), une
 * saturation qui decroit (CLIP), l'ampli (DEC) ; un bruit de Fibonacci par deux resonateurs en cascade (accordes
 * par PTCH), son ampli (DEC / 2) et son niveau (SNAP au-dela de 64) ; l'echantillon d'attaque (SNAP).
 */
#include "trx_sd.h"
#include "trx_b2.h"
#include "md_data.h"
#include "mdmath.h"

void trx_sd_set_knobs(trx_sd_t *v, const uint8_t k[8])  /* 0x2013a6 */
{
	const int32_t ptch = k[0] << 7, bump = k[2] << 7, snap = k[4] << 7, tone = k[5] << 7;
	const int32_t tune = k[6] << 7;
	const int32_t y7 = (ptch >> 2) + 0x1000, d = snap - 0x2000;

	v->p[7] = m_s24((uint32_t)y7);
	v->p[11] = m_s24((uint32_t)((ptch >> 5) + 0x400));
	v->p[1] = m_s24((uint32_t)sd_dec1[k[1]]);
	v->p[2] = m_s24((uint32_t)sd_dec2[k[1]]);
	v->p[5] = m_s24((uint32_t)(snap << 9));
	v->p[6] = m_s24((uint32_t)(snap > 0x1fff ? ((d * d) >> 4) & (int32_t)0xfffffc00 : 0));
	v->p[3] = m_s24((uint32_t)(0x7fffff - (tone << 8)));
	v->p[4] = m_s24((uint32_t)(tone << 8));
	v->p[8] = m_s24((uint32_t)(((y7 >> 6) * ((tune >> 9) + 0xb9)) >> 1));
	v->p[10] = m_s24((uint32_t)((bump * bump) >> 18));
	v->p[12] = m_s24((uint32_t)sd_benv[k[3]]);
	v->p[9] = m_s24((uint32_t)sd_clip[k[7]]);
}

void trx_sd_init(trx_sd_t *v)                            /* $10074c */
{
	v->n0 = 0x29a;
	v->n1 = 1;
	v->f1a = v->f1b = v->f2a = v->f2b = 0;
	v->last = 0;          /* y16 : laisse par la machine precedente sur le Machinedrum ; 0 apres le demarrage */
	v->aenv = v->nenv = v->bump = v->pos = v->ph1 = v->ph1f = v->ph2 = v->ph2f = v->dist = v->bump_n = 0;
}

void trx_sd_trig(trx_sd_t *v)                            /* $10075b */
{
	const int32_t l = v->last < 0 ? -v->last : v->last;
	v->aenv = m_sat24(0x50c335 + v->aenv);
	v->bump_n = 0x140;
	v->dist = 0x7eb852;
	v->bump = 0;
	v->nenv = m_sat24(0x4ccccd + 16 * l);
	v->pos = v->ph1 = v->ph1f = v->ph2 = v->ph2f = 0;
}

/* oscillateur ($100784.. / $1007a2..) : increment (p + 2 bosse) 2^19, index de 15 bits + fraction de 24 bits */
static void osc(int32_t *ph, int32_t *phf, int32_t p, int32_t bump, int32_t amp, int32_t *dst)
{
	const int32_t q = p + 2 * bump, ii = q >> 5, fi = (q & 31) << 19;
	int32_t i = *ph & 0x7fff, f = *phf, k;

	for (k = 0; k < 32; k++) {
		dst[k] = mpy24(trx_b2_sine[i], amp);
		f += fi;
		i = (i + ii + (f >> 24)) & 0x7fff;
		f &= 0xffffff;
	}
	*ph = i;
	*phf = f;
}

/* bruit de Fibonacci modulo 2^24 ($1007e9) */
static void noise(trx_sd_t *v, int32_t nz[32])
{
	uint32_t a = (uint32_t)v->n0 & 0xffffff, b = (uint32_t)v->n1 & 0xffffff, c;
	int k;

	for (k = 0; k < 32; k++) {
		c = (a + b) & 0xffffff;
		nz[k] = m_s24(c);
		a = b;
		b = c;
	}
	v->n0 = m_s24(a);
	v->n1 = m_s24(b);
}

/* deux resonateurs en cascade ($1007f6..$100837), sur place : y = 2 (c0 x + c1 y[n-1] + c2 y[n-2]), sature */
static void resonators(trx_sd_t *v, int32_t nz[32])
{
	const int32_t kn = (v->p[11] - 0x400) >> 2;          /* potard PTCH */
	const int32_t K1 = sd_k1[kn], K2 = sd_k2[kn];
	int32_t l, l1, l2, l3, h, c0, c1, c2, k;
	int32_t s1o = v->f1a, s1n = v->f1b, s2o = v->f2a, s2n = v->f2b;

	h = hilo(K1, K2, &l);                                /* K1 K2 = h 2^23 + l */
	c1 = m_sat24(2 * h + (l >> 22));                     /* lim(4 K1 K2) */
	{
		int32_t lk;
		const int32_t hk = hilo(K2, K2, &lk);
		c2 = m_sat24(-(hk + (lk != 0)));                 /* lim(-2 K2^2) */
	}
	c0 = m_sat24(0x400000 - c2 - (2 * h + (l >> 22) + ((l & 0x3fffff) != 0)));   /* lim(1/2 - 4 K1 K2 - c2) */
	for (k = 0; k < 32; k++) {
		int32_t u, w;
		h = hilo(c2, s1o, &l1) + hilo(c1, s1n, &l2) + hilo(c0, nz[k], &l3);
		u = m_sat24(2 * h + ((l1 + l2 + l3) >> 22));
		s1o = s1n;
		s1n = u;
		h = hilo(c2, s2o, &l1) + hilo(c1, s2n, &l2) + hilo(c0, u, &l3);
		w = m_sat24(2 * h + ((l1 + l2 + l3) >> 22));
		s2o = s2n;
		s2n = w;
		nz[k] = w;
	}
	v->f1a = s1o;
	v->f1b = s1n;
	v->f2a = s2o;
	v->f2b = s2n;
}

int trx_sd_render(trx_sd_t *v, int32_t out[TRX_SD_BLOCK])   /* $100776 */
{
	int32_t T[32], O[32], nz[32];
	int32_t x0, x1, k;

	emac_begin();
	if (!v->aenv && !v->nenv && v->pos > 0xfe0) {
		/* ni ton, ni bruit, ni echantillon jusqu'au prochain trig (qui remet le reste a zero) ; le bruit et ses
		 * resonateurs, eux, ne sont jamais remis a zero : ils avancent */
		noise(v, nz);
		resonators(v, nz);
		v->pos = m_sat24(v->pos + 0x20);
		for (k = 0; k < 32; k++)
			out[k] = 0;
		v->last = 0;
		return 0;
	}
	/* oscillateurs, puis la bosse de hauteur */
	x0 = v->bump;
	osc(&v->ph1, &v->ph1f, v->p[7], x0, v->p[3], T);
	v->bump = v->pos > v->bump_n ? mpy24(v->p[12], x0) : m_sat24(2 * v->p[10] + x0);
	osc(&v->ph2, &v->ph2f, v->p[8], x0, v->p[4], O);
	/* $1007ce : saturation qui decroit (CLIP) : s + 128 d s / 2^24 */
	x0 = v->dist;
	v->dist = mpy24(v->p[9], x0);
	for (k = 0; k < 32; k++) {
		int32_t l1, l2;
		const int32_t h = hilo(T[k], x0, &l1) + hilo(x0, O[k], &l2);
		T[k] = m_sat24(T[k] + O[k] + 64 * h + ((l1 + l2) >> 17));
	}
	/* $1007df : ampli du ton */
	x0 = v->p[1];
	x1 = v->aenv;
	for (k = 0; k < 32; k++) {
		T[k] = mpy24(x1, T[k]);
		x1 = mpy24(x1, x0);
	}
	v->aenv = x1;
	noise(v, nz);
	resonators(v, nz);
	/* $100844 : ampli du bruit, puis ton + bruit */
	x1 = v->nenv;
	x0 = v->p[2];
	for (k = 0; k < 32; k++) {
		const int32_t n = mpy24(x1, nz[k]);
		x1 = mpy24(x1, x0);
		T[k] = m_sat24(T[k] + hi23(n, v->p[6]));
	}
	v->nenv = x1;
	/* $10085a : echantillon d'attaque (SNAP) */
	if (v->pos > 0xfe0) {
		for (k = 0; k < 32; k++)
			out[k] = T[k];
	} else {
		const int32_t *s = sd_snap + v->pos;
		for (k = 0; k < 32; k++)
			out[k] = m_sat24(T[k] + hi23(s[k], v->p[5]));
	}
	v->pos = m_sat24(v->pos + 0x20);
	v->last = out[31];
	return 1;
}
