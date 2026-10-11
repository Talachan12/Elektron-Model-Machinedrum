/*
 * TRX-CH du Machinedrum (SPS-1 UW, OS 1.63), porte a l'echantillon pres depuis le code du DSP A :
 * P:$10201f (init), $102034 (trig), $10204d (rendu) ; potards : fonction ColdFire 0x201800. Tout sur 32 bits
 * (mdmath.h), memes sorties que le DSP emule.
 *
 * Synthese : un bruit de Fibonacci (niveau : MTAL) et six carres de periodes fixes (114, 102, 86, 80, 58 et 52
 * echantillons ; niveau : MTAL), puis deux resonateurs en cascade (accordes par LPF), un passe-haut (HPF) et un
 * passe-haut fixe ; l'enveloppe tient un bloc, descend lineairement pendant 2 DEC blocs, puis decroit d'un facteur
 * fixe par echantillon (GAP). En plus du Machinedrum : Q (y4 = y7 = 0x46 sur le Machinedrum), l'index de la table
 * qui regle la resonance des filtres 1 et 2 ; Q = 0x46 donne exactement le TRX-CH.
 */
#include "trx_ch.h"
#include "md_data.h"
#include "mdmath.h"

#define SQ 0x7ffcb9                                       /* carres de P:$102600.. : +SQ puis -SQ */

static const unsigned char osc_len[6] = { 114, 102, 86, 80, 58, 52 }, osc_hi[6] = { 72, 51, 43, 40, 29, 26 };

void trx_ch_set_knobs(trx_ch_t *v, const uint8_t k[6])   /* 0x201800 ; y9, y10 : au trig (trx_ch_trig) */
{
	const int32_t hpf = k[2] << 7, lpf = k[3] << 7, mtal = k[4] << 7;

	v->p[1] = 0x126;
	v->p[2] = m_s24((uint32_t)ch_gap[k[0]]);
	v->p[3] = ((lpf * 0xac77) >> 22) + 0x680;
	v->p[6] = ((hpf * 0x2d83) >> 20) + 0x600;
	v->p[4] = k[5];                                      /* 0x46 sur le Machinedrum */
	v->p[7] = k[5];
	v->p[5] = 0x80000 - mtal * 25;
	v->p[8] = mtal * 14 + 0x10000;
	v->dec = k[1];
}

void trx_ch_init(trx_ch_t *v)                            /* $10201f */
{
	int k;

	v->env = 0;
	v->n0 = 0;
	v->n1 = 1;
	for (k = 0; k < 6; k++)
		v->pos[k] = 0;
	/* y21..y32 : laisses par la machine precedente sur le Machinedrum (le trig les remet a zero) */
	for (k = 0; k < 4; k++)
		v->f1[k] = v->f2[k] = v->f3[k] = 0;
	for (k = 0; k < 5; k++)
		v->g[k] = 0;
	v->p[9] = v->p[10] = 0;
}

void trx_ch_trig(trx_ch_t *v)                            /* $102034, et y9/y10 envoyes avec le trig */
{
	int k;

	v->p[9] = 1;
	v->p[10] = v->dec << 1;
	v->env = m_sat24(0x6ccccd + v->env);
	for (k = 0; k < 5; k++)
		v->g[k] = v->p[8];
	for (k = 0; k < 4; k++)
		v->f1[k] = v->f2[k] = v->f3[k] = 0;
}

/* coefficients d'un filtre ($102100.. et suivants) : c1 = lim(4 K1 K2), c2 = lim(-2 K2^2), c0 = lim(1/2 - 4 K1 K2 - c2) */
static void coefs(int32_t K1, int32_t K2, int32_t *c0, int32_t *c1, int32_t *c2)
{
	int32_t l, lk;
	const int32_t h = hilo(K1, K2, &l), hk = hilo(K2, K2, &lk);

	*c1 = m_sat24(2 * h + (l >> 22));
	*c2 = m_sat24(-(hk + (lk != 0)));
	if (c0)
		*c0 = m_sat24(0x400000 - *c2 - (2 * h + (l >> 22) + ((l & 0x3fffff) != 0)));
}

/* filtre 1 ($1020ed) : deux resonateurs en cascade, sur place : y = 2 (c0 x + c1 y[n-1] + c2 y[n-2]), sature */
static void resonators(int32_t K1, int32_t K2, int32_t *st, int32_t *x)
{
	int32_t c0, c1, c2, l1, l2, l3, h, k;
	int32_t s1o = st[0], s1n = st[1], s2o = st[2], s2n = st[3];

	coefs(K1, K2, &c0, &c1, &c2);
	for (k = 0; k < 32; k++) {
		int32_t u, w;
		h = hilo(c2, s1o, &l1) + hilo(c1, s1n, &l2) + hilo(c0, x[k], &l3);
		u = m_sat24(2 * h + ((l1 + l2 + l3) >> 22));
		s1o = s1n;
		s1n = u;
		h = hilo(c2, s2o, &l1) + hilo(c1, s2n, &l2) + hilo(c0, u, &l3);
		w = m_sat24(2 * h + ((l1 + l2 + l3) >> 22));
		s2o = s2n;
		s2n = w;
		x[k] = w;
	}
	st[0] = s1o;
	st[1] = s1n;
	st[2] = s2o;
	st[3] = s2n;
}

/* filtres 2 et 3 ($102131, $102174) : passe-haut, sur place : y = x - 2 x[n-1] + x[n-2] + 2 (c1 y[n-1] + c2 y[n-2]) ;
 * st = (x[-2], x[-1], y[-2], y[-1]) */
static void highpass(int32_t K1, int32_t K2, int32_t *st, int32_t *x)
{
	int32_t c1, c2, l1, l2, h, k;
	int32_t x2 = st[0], x1 = st[1], y2 = st[2], y1 = st[3];

	coefs(K1, K2, 0, &c1, &c2);
	for (k = 0; k < 32; k++) {
		const int32_t in = x[k];
		int32_t y;
		h = hilo(c2, y2, &l1) + hilo(c1, y1, &l2);
		y = m_sat24(in - 2 * x1 + x2 + 2 * h + ((l1 + l2) >> 22));
		x2 = x1;
		x1 = in;
		y2 = y1;
		y1 = y;
		x[k] = y;
	}
	st[0] = x2;
	st[1] = x1;
	st[2] = y2;
	st[3] = y1;
}

int trx_ch_render(trx_ch_t *v, int32_t out[TRX_CH_BLOCK])   /* $10204d */
{
	int32_t x[32], e, k, i;
	uint32_t a = (uint32_t)v->n0 & 0xffffff, b = (uint32_t)v->n1 & 0xffffff, c;

	emac_begin();
	/* bruit de Fibonacci modulo 2^24 */
	for (k = 0; k < 32; k++) {
		c = (a + b) & 0xffffff;
		x[k] = m_s24(c);
		a = b;
		b = c;
	}
	v->n0 = m_s24(a);
	v->n1 = m_s24(b);
	if (!v->p[9] && !v->p[10] && !v->env) {
		/* enveloppe nulle jusqu'au prochain trig, qui remet les filtres a zero : seules les phases avancent */
		for (i = 0; i < 6; i++)
			v->pos[i] = (v->pos[i] + 32) % osc_len[i];
		for (k = 0; k < 32; k++)
			out[k] = 0;
		return 0;
	}
	/* $10205d : niveau du bruit ; $102066 : les 6 carres (aucune somme ne peut saturer : y5 + 6 y8 < 2^23) */
	for (k = 0; k < 32; k++)
		x[k] = mpy24(x[k], v->p[5]);
	for (i = 0; i < 6; i++) {
		const int32_t g = i ? v->g[i - 1] : v->p[8], hi = mpy24(SQ, g), lo = mpy24(-SQ, g);
		const int32_t len = osc_len[i], half = osc_hi[i];
		int32_t p = v->pos[i];
		for (k = 0; k < 32; k++) {
			x[k] += p < half ? hi : lo;
			if (++p == len)
				p = 0;
		}
		v->pos[i] = p;
	}
	resonators(ch_t1[v->p[3] + ch_q1[v->p[4]] - CH_LO], ch_t2[v->p[3] + ch_q2[v->p[4]] - CH_LO], v->f1, x);
	highpass(ch_t1[v->p[6] + ch_q1[v->p[7]] - CH_LO], ch_t2[v->p[6] + ch_q2[v->p[7]] - CH_LO], v->f2, x);
	highpass(ch_dk[0], ch_dk[1], v->f3, x);
	/* $1021b7 : enveloppe (tenue d'un bloc, descente lineaire, puis decroissance GAP) ; sortie env x / 2 */
	e = v->env;
	if (v->p[9]) {
		v->p[9]--;
		for (k = 0; k < 32; k++)
			out[k] = mpy24(e, x[k]) >> 1;
	} else if (v->p[10]) {
		const int32_t d = v->p[1];
		v->p[10]--;
		for (k = 0; k < 32; k++) {
			out[k] = mpy24(e, x[k]) >> 1;
			e -= d;
		}
	} else {
		const int32_t g = v->p[2];
		for (k = 0; k < 32; k++) {
			out[k] = mpy24(e, x[k]) >> 1;
			e = mpy24(g, e);
		}
	}
	v->env = e;
	return 1;
}
