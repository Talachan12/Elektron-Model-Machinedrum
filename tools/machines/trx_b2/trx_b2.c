/*
 * TRX-B2 du Machinedrum (SPS-1 UW, OS 1.63), porte a l'echantillon pres depuis le code du DSP A (DSP56303) :
 * P:$102c31 (init), $102c4a (trig), $102c5a (rendu de 32 echantillons) ; potards -> mots du DSP : fonction
 * ColdFire 0x201fd2 de l'OS du Machinedrum. Prouve identique au DSP emule (dsp56300) sur des centaines de reglages.
 *
 * Le DSP calcule en fractionnaire 24 bits avec des accumulateurs de 56 bits. Ici tout tient sur 32 bits :
 *   mpy x,y puis move a,reg  =  floor(x*y / 2^23)              (hi23, 4 multiplications de moities de 12 bits) ;
 *   la partie fractionnaire de l'accumulateur, quand une comparaison ou une somme en depend, est le reste
 *   x*y mod 2^23, c'est-a-dire les 23 bits de poids faible de muls.l (lo23).
 * Echantillons : entiers 24 bits signes (fraction du DSP * 2^23) dans des int32_t.
 */
#include "trx_b2.h"

static inline int32_t s24(uint32_t v) { return (int32_t)(v << 8) >> 8; }

/* floor(x*y / 2^23) pour x, y sur 24 bits ; seul -1 * -1 deborde (move a,reg sature : 0x7fffff) */
static inline int32_t hi23(int32_t x, int32_t y)
{
	const int32_t xh = x >> 12, xl = x & 0xfff, yh = y >> 12, yl = y & 0xfff;
	return 2 * xh * yh + ((xh * yl + xl * yh + ((xl * yl) >> 12)) >> 11);
}

static inline int32_t mpy_mov(int32_t x, int32_t y)            /* mpy x,y,a ; move a,reg */
{
	const int32_t r = hi23(x, y);
	return r > 0x7fffff ? 0x7fffff : r;
}

static inline int32_t lo23(int32_t x, int32_t y)               /* x*y mod 2^23 */
{
	return (int32_t)(((uint32_t)x * (uint32_t)y) & 0x7fffff);
}

static inline int32_t sat24(int32_t v)
{
	return v > 0x7fffff ? 0x7fffff : (v < -0x800000 ? -0x800000 : v);
}

void trx_b2_init(trx_b2_t *v)                                   /* P:$102c31 */
{
	v->ramp_decay = 0x7fef9e;
	v->noise_decay = 0x75c28f;
	v->noise_a = 0x12e70c;
	v->noise_b = 0x1914a5;
	v->hold_env = 0x7fffff;
	v->amp_env = 0;
	v->ramp_env = 0;
	v->noise_env = 0;
	v->attack = 0;
	v->phase = 0;
	v->tick_env = 0;
}

void trx_b2_trig(trx_b2_t *v)                                   /* P:$102c4a */
{
	v->ramp_env = v->ramp;
	v->attack = 0x0147ae;
	v->noise_env = v->noise;
	v->tick_env = v->tick;
	v->hold_env = 0x7fffff;
}

/* Fonction ColdFire 0x201fd2 : potards -> mots du DSP (24 bits de poids faible de chaque mot long envoye). */
void trx_b2_set_knobs(trx_b2_t *v, const uint8_t k[8])
{
	const int32_t ptch = k[0], dec = k[1], ramp = k[2], hold = k[3];
	const int32_t tick = k[4], nois = k[5], dirt = k[6], dist = k[7];
	int32_t d, q;

	v->pitch = s24((uint32_t)((trx_b2_pitch_tbl[ptch] - 0x800) * 9 + 0x76e));
	v->ramp = s24((uint32_t)(((ramp << 7) * 76087) >> 14));
	v->dec = s24((uint32_t)trx_b2_dec_tbl[dec]);
	v->hold = s24((uint32_t)trx_b2_hold_tbl[hold]);
	d = ((dist << 7) * (dist << 7)) >> 12;
	v->slope[0] = s24((uint32_t)(-60 * d - 0x8000));
	v->slope[1] = s24((uint32_t)(70 * d + 0x8000));
	v->slope[2] = s24((uint32_t)(-0x8000 - 50 * d));
	v->slope[3] = s24((uint32_t)(40 * d + 0x8000));
	q = (24 * trx_b2_dirt_tbl[dirt]) / 0x26d0b;                  /* divs.l : quotient tronque vers zero */
	v->dirt_shift = s24((uint32_t)q);
	v->dirt_round = s24((uint32_t)(((q >= 0 && q < 32) ? (1u << q) : 0u) >> 1));
	v->noise = s24((uint32_t)(((nois << 7) << 9) & 0x1fffe00));
	v->tick = s24((uint32_t)(((tick << 7) << 8) & 0xffff00));
}

/* $102cbb : bruit de Fibonacci modulo 2^24, une valeur tous les 4 echantillons (nz : 8 valeurs, ou rien) */
static void noise_block(trx_b2_t *v, int32_t nz[8])
{
	uint32_t b1 = (uint32_t)v->noise_a & 0xffffff, x1 = (uint32_t)v->noise_b & 0xffffff, x0;
	int i;

	for (i = 0; i < 7; ++i) {
		b1 = (b1 + x1) & 0xffffff;
		x0 = x1;
		if (nz)
			nz[i] = s24(b1);
		x1 = b1;
		b1 = x0;
	}
	b1 = (b1 + x1) & 0xffffff;
	v->noise_a = s24(x1);
	v->noise_b = s24(b1);
	if (nz)
		nz[7] = s24(b1);
}

/* index dans le sinus pour une pente de DIST descendante (quadrants 0 et 2) : floor(-max(a, -0x1fff)) */
static inline int32_t down(int32_t slope, int32_t q)
{
	const int32_t h = hi23(slope, q);
	return h >= -0x1fff ? -h - (lo23(slope, q) != 0) : 0x1fff;
}

static inline int32_t up(int32_t slope, int32_t q)             /* quadrants 1 et 3 : floor(max(a, -0x1fff)) */
{
	const int32_t h = hi23(slope, q);
	return h >= -0x1fff ? h : -0x1fff;
}

int trx_b2_render(trx_b2_t *v, int32_t out[TRX_B2_BLOCK])     /* P:$102c5a */
{
	int32_t sig[TRX_B2_BLOCK], nz[8];
	const int silent = !v->amp_env && !v->attack && !v->tick_env && !v->noise_env;
	int i;

	/* $102c5a : phase += PTCH + enveloppe de RAMP (qui decroit a chaque echantillon) */
	{
		uint32_t ph = (uint32_t)v->phase;
		int32_t env = v->ramp_env;
		const int32_t inc = v->pitch, rd = v->ramp_decay;
		for (i = 0; i < TRX_B2_BLOCK; ++i) {
			env = mpy_mov(rd, env);
			ph = (ph + (uint32_t)inc + (uint32_t)env) & 0x7fffff;
			sig[i] = (int32_t)ph;
		}
		v->ramp_env = env;
		v->phase = (int32_t)ph;
	}

	if (silent) {
		/* rien ne sonne : enveloppes a zero, le resultat est exactement 0 ; on n'avance que l'etat */
		noise_block(v, 0);
		v->hold_env = mpy_mov(v->hold, v->hold_env);
		for (i = 0; i < TRX_B2_BLOCK; ++i)
			out[i] = 0;
		return 0;
	}

	/* $102c6d : pente par quart de periode (DIST) vers le sinus, ecretee au sommet */
	for (i = 0; i < TRX_B2_BLOCK; ++i) {
		const int32_t p = sig[i];
		int32_t idx;
		if (!(p & 0x400000))
			idx = !(p & 0x200000) ? down(v->slope[0], p) : up(v->slope[1], p - 0x400000) + 0x4000;
		else
			idx = !(p & 0x200000) ? down(v->slope[2], p - 0x400000) + 0x4000 : up(v->slope[3], p - 0x800000) + 0x8000;
		sig[i] = trx_b2_sine[idx & 0x7fff];
	}

	/* $102cb1 : DIRT, requantification au multiple de 2^shift le plus proche */
	if (v->dirt_shift) {
		const int sh = v->dirt_shift & 0x3f;
		const int32_t rnd = v->dirt_round;
		for (i = 0; i < TRX_B2_BLOCK; ++i)
			sig[i] = sat24(((sig[i] + rnd) >> sh) << sh);
	}

	noise_block(v, nz);

	/* $102cd2 : decroissances par bloc ; HOLD garde l'ampli constant tant que son compteur est haut */
	{
		const int32_t h = hi23(v->hold, v->hold_env);
		const int32_t decay = h < 0x0147ae ? v->dec : 0x7ffff8;
		int32_t env = v->amp_env, att = v->attack;
		v->noise_env = mpy_mov(v->noise_env, v->noise_decay);
		v->hold_env = h > 0x7fffff ? 0x7fffff : h;

		/* $102ce2 : attaque (+0x147ae par echantillon jusqu'a 1/2), puis decroissance exponentielle */
		for (i = 0; i < TRX_B2_BLOCK; ++i) {
			const int32_t b = hi23(env, decay) + att;
			if (b >= 0x400000)
				att = 0;
			env = sat24(b);
			sig[i] = mpy_mov(sig[i], env);
		}
		v->amp_env = env;
		v->attack = att;
	}

	/* $102cf3 : sortie = signal + 8 * TICK + bruit * enveloppe ; TICK *= 0.9 a chaque echantillon */
	{
		int32_t t = v->tick_env;
		const int32_t ne = v->noise_env;
		if (!t && !ne) {
			for (i = 0; i < TRX_B2_BLOCK; ++i)
				out[i] = sig[i];
		} else {
			for (i = 0; i < TRX_B2_BLOCK; ++i) {
				const int32_t n = (i & 3) ? 0 : nz[i >> 2];
				const int32_t h1 = hi23(t, 0x733333), l1 = lo23(t, 0x733333);
				const int32_t h2 = hi23(n, ne), l2 = lo23(n, ne);
				t = h1 > 0x7fffff ? 0x7fffff : h1;
				out[i] = sat24(sig[i] + 8 * h1 + h2 + ((8 * l1 + l2) >> 23));
			}
		}
		v->tick_env = t;
	}
	return 1;
}
