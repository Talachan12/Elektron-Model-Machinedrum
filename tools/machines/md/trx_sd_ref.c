/*
 * REFERENCE (ordinateur seulement) : TRX-SD du Machinedrum transcrit instruction par instruction (modele dsp56.h,
 * petite memoire X/Y et registres d'adresse du DSP) ; trx_sd.c en est la version rapide (memes sorties, prouve).
 * DSP A : P:$10074c (init), $10075b (trig), $100776 (rendu) ; potards : fonction ColdFire 0x2013a6.
 */
#include "trx_sd.h"
#include "dsp56.h"
#include "trx_b2.h"
#include "md_data.h"

#define SINE(i) trx_b2_sine[(i) & 0x7fff]

void trx_sd_set_knobs(trx_sd_t *v, const uint8_t k[8])  /* 0x2013a6 */
{
	const int32_t ptch = k[0] << 7, bump = k[2] << 7, snap = k[4] << 7, tone = k[5] << 7;
	const int32_t tune = k[6] << 7;
	int32_t y7, d;

	y7 = (ptch >> 2) + 0x1000;
	v->p[7] = d_s24((uint32_t)y7);
	v->p[11] = d_s24((uint32_t)((ptch >> 5) + 0x400));
	v->p[1] = d_s24((uint32_t)sd_dec1[k[1]]);
	v->p[2] = d_s24((uint32_t)sd_dec2[k[1]]);
	v->p[5] = d_s24((uint32_t)(snap << 9));
	d = snap - 0x2000;
	v->p[6] = d_s24((uint32_t)(snap > 0x1fff ? ((d * d) >> 4) & (int32_t)0xfffffc00 : 0));
	v->p[3] = d_s24((uint32_t)(0x7fffff - (tone << 8)));
	v->p[4] = d_s24((uint32_t)(tone << 8));
	v->p[8] = d_s24((uint32_t)(((y7 >> 6) * ((tune >> 9) + 0xb9)) >> 1));
	v->p[10] = d_s24((uint32_t)((bump * bump) >> 18));
	v->p[12] = d_s24((uint32_t)sd_benv[k[3]]);
	v->p[9] = d_s24((uint32_t)sd_clip[k[7]]);
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
	a56 a, b;

	v->aenv = d_lim24(d_w56(d_from24(0x50c335) + d_from24(v->aenv)));
	v->bump_n = 0x140;
	v->dist = 0x7eb852;
	b = d_from24(v->last);
	b = b < 0 ? -b : b;
	b = d_w56(b << 4);
	a = d_w56(d_from24(0x4ccccd) + b);
	v->bump = 0;
	v->nenv = d_lim24(a);
	v->pos = v->ph1 = v->ph1f = v->ph2 = v->ph2f = 0;
}

/* oscillateur : $100784..$1007a1 (et $1007a2..$1007cd) ; incr = a (56 bits), sortie amp * sinus */
static void osc(int32_t *ph, int32_t *phf, a56 inc, int32_t amp, int32_t *dst)
{
	const int32_t x1 = d_a1(inc), x0 = (int32_t)(inc & 0xffffff);
	const a56 x = d_from24(x1) + x0;
	a56 b = d_from24(*ph) + (*phf & 0xffffff);
	uint32_t r3 = d_idx(b);
	int k;

	b = d_and1(d_w56(b + x), 0x7fff);
	for (k = 0; k < 31; k++) {
		const a56 a = d_mpy(SINE(r3), amp);
		r3 = d_idx(b);
		dst[k] = d_lim24(a);
		b = d_and1(d_w56(b + x), 0x7fff);
	}
	dst[31] = d_lim24(d_mpy(SINE(r3), amp));
	*ph = d_a1(b);
	*phf = (int32_t)(b & 0xffffff);
}

int trx_sd_render(trx_sd_t *v, int32_t out[TRX_SD_BLOCK])   /* $100776 */
{
	int32_t X[0x40];                                     /* x:$00..$3f du DSP (tampons $20 et $40, etats) */
	int32_t Y[2];                                        /* y:0, y:1 : coefficients du 2e etage */
	int32_t T[TRX_SD_BLOCK];                             /* x:$40..$5f : le ton */
	a56 a, b;
	int32_t x0, x1, y0, y1;
	int k;

	/* $100784 : oscillateur 1 */
	a = d_w56((d_from24(v->p[7]) >> 1) + d_from24(v->bump)) >> 4;
	osc(&v->ph1, &v->ph1f, a, v->p[3], T);
	/* $1007a2 : oscillateur 2, puis la bosse de hauteur */
	x0 = v->bump;
	a = d_w56((d_from24(v->p[8]) >> 1) + d_from24(x0)) >> 4;
	if (d_from24(v->pos) - d_from24(v->bump_n) > 0)
		b = d_mpy(v->p[12], x0);
	else
		b = d_w56(d_w56(d_from24(v->p[10]) << 1) + d_from24(x0));
	v->bump = d_lim24(b);
	osc(&v->ph2, &v->ph2f, a, v->p[4], X + 0x20);
	/* $1007ce : saturation qui decroit (CLIP) */
	x0 = v->dist;
	v->dist = d_lim24(d_mpy(v->p[9], x0));
	for (k = 0; k < 32; k++) {
		y0 = T[k];
		y1 = X[0x20 + k];
		a = d_w56(d_from24(y0) + d_from24(y1));
		b = d_w56(d_mpy(y0, x0) + d_mpy(x0, y1));
		b = d_w56(b << 6);
		T[k] = d_lim24(d_w56(a + b));
	}
	/* $1007df : ampli du ton */
	x0 = v->p[1];
	x1 = v->aenv;
	for (k = 0; k < 32; k++) {
		a = d_mpy(x1, T[k]);
		b = d_mpy(x1, x0);
		T[k] = d_lim24(a);
		x1 = d_lim24(b);
	}
	v->aenv = x1;
	/* $1007e9 : bruit de Fibonacci (a1 seul compte) */
	{
		uint32_t b1 = (uint32_t)v->n0 & 0xffffff, n1 = (uint32_t)v->n1 & 0xffffff, t;
		for (k = 0; k < 31; k++) {
			b1 = (b1 + n1) & 0xffffff;
			t = n1;
			n1 = b1;
			X[0x20 + k] = d_s24(b1);
			b1 = t;
		}
		b1 = (b1 + n1) & 0xffffff;
		v->n0 = d_s24(n1);
		v->n1 = d_s24(b1);
		X[0x20 + 31] = d_s24(b1);
	}
	/* $1007f6 : deux resonateurs en cascade, coefficients des tables du DSP (selon PTCH) */
	{
		const int32_t kn = (v->p[11] - 0x400) >> 2;        /* potard PTCH */
		const int32_t K1 = sd_k1[kn], K2 = sd_k2[kn];
		int r1, r2, r3, r4, r0;
		x1 = K1;
		y1 = K2;
		a = d_mpy(y1, x1);
		x0 = y1;
		b = -d_mpy(x0, y1);
		x1 = d_lim24(b);
		a = d_w56(a << 1);
		X[3] = v->f1a;                                   /* y:(r6+$19) -> x:3, puis $1a -> x:2 (r1 modulo 2) */
		X[2] = v->f1b;
		x0 = d_lim24(a);
		a = d_w56(a + d_from24(x1));
		a = d_w56(a - d_from24(0x400000));
		a = d_w56(-a);
		Y[1] = d_lim24(b);
		y1 = d_lim24(b);
		Y[0] = d_lim24(a);
		X[0x1e] = v->f2a;
		X[0x1f] = v->f2b;
		r1 = 3;
		x1 = X[r1]; r1 ^= 1;
		a = d_mpy(y1, x1); y1 = X[r1]; r1 ^= 1;
		r0 = 0x20; r4 = 0;
		a = d_w56(a + d_mpy(x0, y1)); x1 = X[r0++]; y0 = Y[r4]; r4 ^= 1;
		a = d_w56(a + d_mpy(x1, y0));
		r3 = 0x1e; r2 = 0x1f;
		for (k = 0; k < 32; k++) {
			int32_t pa;
			x1 = X[r3++]; y1 = Y[r4]; r4 ^= 1; a = d_w56(a << 1);
			b = d_mpy(y1, x1); y1 = X[r2++];
			pa = d_lim24(a); b = d_w56(b + d_mpy(x0, y1)); x1 = pa; y0 = Y[r4]; r4 ^= 1;
			b = d_w56(b + d_mpy(x1, y0)); X[r1] = d_lim24(a); r1 ^= 1;
			x1 = X[r1]; r1 ^= 1; y1 = Y[r4]; r4 ^= 1; b = d_w56(b << 1);
			a = d_mpy(y1, x1); y1 = X[r1]; r1 ^= 1;
			a = d_w56(a + d_mpy(x0, y1)); x1 = (r0 < 0x40) ? X[r0] : 0; r0--; y0 = Y[r4]; r4 ^= 1;
			a = d_w56(a + d_mpy(x1, y0)); X[r0] = d_lim24(b); r0 += 2;
		}
		v->f1a = X[r1]; r1 ^= 1;
		v->f1b = X[r1]; r1 ^= 1;
		v->f2b = X[r2];                                  /* move x:(r2)-,y1 ; move x:(r2),y1 */
		v->f2a = X[r2 - 1];
	}
	/* $100844 : ampli du bruit, puis ton + bruit */
	x1 = v->nenv;
	x0 = v->p[2];
	for (k = 0; k < 32; k++) {
		a = d_mpy(x1, X[0x20 + k]);
		b = d_mpy(x1, x0);
		X[0x20 + k] = d_lim24(a);
		x1 = d_lim24(b);
	}
	v->nenv = x1;
	x0 = v->p[6];
	for (k = 0; k < 32; k++)
		T[k] = d_lim24(d_w56(d_from24(T[k]) + d_mpy(X[0x20 + k], x0)));
	/* $10085a : echantillon d'attaque (SNAP), 32 mots par bloc tant qu'il en reste */
	b = d_from24(v->pos);
	if (b - d_from24(0xfe0) > 0) {
		v->pos = d_lim24(d_w56(b + d_from24(0x20)));
		for (k = 0; k < 32; k++)
			out[k] = T[k];
	} else {
		const int32_t at = v->pos;
		v->pos = d_lim24(d_w56(b + d_from24(0x20)));
		x0 = v->p[5];
		for (k = 0; k < 32; k++)
			out[k] = d_lim24(d_w56(d_from24(T[k]) + d_mpy(sd_snap[at + k], x0)));
	}
	v->last = out[31];
	return 1;
}
