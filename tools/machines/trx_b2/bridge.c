/*
 * TRX-B2 : machine ajoutee du Model:Cycles (OS 1.13), la grosse caisse TRX-B2 du Machinedrum (OS 1.63), portee a
 * l'echantillon pres depuis le code du DSP A du Machinedrum (trx_b2.c). Les tables du Machinedrum (hauteur, DEC,
 * HOLD, DIRT) sont lues au build dans le fichier OS du Machinedrum de l'utilisateur ; le sinus est recalcule par
 * l'algorithme du DSP (md_sine.py).
 *
 * Contrat de la boucle des voix (notes/14, comme MACRO) : update(pmod, v, p) puis render(out, v), une fois par
 * bloc de 32 trames a 48 kHz. p = parametres de la piste (mots 8.8 : +0x14 PITCH, +0x16 COLOR, +0x18 SHAPE,
 * +0x1a SWEEP, +0x1c CONTOUR, +0x1e PUNCH, +0x24 DECAY) ; v+0x38 : trig ; out : 32 x int32 (Q31).
 *
 * Le TRX-B2 rend comme sur le Machinedrum, par blocs de 32 echantillons a 44,1 kHz (ses enveloppes de bruit et
 * de HOLD avancent d'un pas par bloc) ; un filtre polyphase (160/147, 24 coefficients par phase) ramene a 48 kHz.
 *
 * Potards : PITCH = PTCH (+ note du trig - 60), DECAY = DEC, SWEEP = RAMP, CONTOUR = HOLD, COLOR = DIST,
 * SHAPE = DIRT, PUNCH = TICK (64 si PUNCH, 0 sinon) ; NOIS = 0.
 */
#include "trx_b2.h"
#include "rs_coef.h"

typedef signed char s8;
typedef short s16;
typedef int32_t s32;
typedef uint32_t u32;

#ifndef CYC_VOICE0
#define CYC_VOICE0  0x42308828
#endif
#define CYC_VSTRIDE 0x31c
#define MARK_OFF    0x2c
#define MARK        0x4d444232                       /* 'MDB2' */
#define TRIG_NOTE0  60                               /* note du trig qui laisse PTCH = PITCH */
#define TICK_ON     64

#define V32(o)      (*(s32 *)(v + (o)))
#define P16(o)      (*(const s16 *)(p + (o)))

#define HIST        (RS_T - 1)

struct track {
	trx_b2_t b2;
	/* 44,1 kHz : historique du filtre puis le dernier bloc, en deux moities de 16 bits (muls.w) : x = xh * 256 + xl */
	int16_t xh[HIST + TRX_B2_BLOCK], xl[HIST + TRX_B2_BLOCK];
	s32 n;                                           /* echantillons valides */
	s32 z;                                           /* dont nuls a la fin */
	s32 i;                                           /* echantillon d'entree aligne sur la prochaine sortie */
	s32 frac;                                        /* phase du filtre, 0..RS_L-1 */
	s32 trig;                                        /* trig a jouer au prochain bloc du Machinedrum */
	unsigned char knobs[8];
};

static struct track tracks[6];

static inline struct track *track_of(const char *v)
{
	return &tracks[((u32)v - CYC_VOICE0) / CYC_VSTRIDE];
}

static inline s32 knob(s32 x)                        /* 8.8 -> 0..127 */
{
	x >>= 8;
	return x < 0 ? 0 : (x > 127 ? 127 : x);
}

static void track_init(struct track *t)
{
	int k;

	trx_b2_init(&t->b2);
	for (k = 0; k < HIST + TRX_B2_BLOCK; k++)
		t->xh[k] = t->xl[k] = 0;
	t->n = HIST;
	t->z = HIST;
	t->i = HIST;
	t->frac = 0;
	t->trig = 0;
}

void trx_b2_update(s32 pmod, char *v, const char *p)
{
	struct track *t = track_of(v);
	s32 dec, ptch;

	if (V32(MARK_OFF) != MARK) {                     /* 1re note sur cette machine (comme l'init du DSP) */
		track_init(t);
		V32(MARK_OFF) = MARK;
	}
	ptch = knob(P16(0x14)) + (pmod >> 16) - TRIG_NOTE0;
	dec = (s8)p[0x24];
	t->knobs[0] = ptch < 0 ? 0 : (ptch > 127 ? 127 : ptch);
	t->knobs[1] = dec < 0 ? 0 : (dec > 127 ? 127 : dec);
	t->knobs[2] = knob(P16(0x1a));                   /* RAMP  <- SWEEP */
	t->knobs[3] = knob(P16(0x1c));                   /* HOLD  <- CONTOUR */
	t->knobs[4] = P16(0x1e) ? TICK_ON : 0;           /* TICK  <- PUNCH */
	t->knobs[5] = 0;                                 /* NOIS */
	t->knobs[6] = knob(P16(0x18));                   /* DIRT  <- SHAPE */
	t->knobs[7] = knob(P16(0x16));                   /* DIST  <- COLOR */
	if (V32(0x38))
		t->trig = 1;
}

/* un bloc du Machinedrum : l'OS envoie les parametres, puis le DSP joue le trig et rend 32 echantillons */
static void md_block(struct track *t)
{
	s32 x[TRX_B2_BLOCK];
	int k;

	for (k = 0; k < HIST; k++) {                     /* garde les HIST derniers echantillons */
		t->xh[k] = t->xh[t->n - HIST + k];
		t->xl[k] = t->xl[t->n - HIST + k];
	}
	t->i -= t->n - HIST;
	t->n = HIST;
	trx_b2_set_knobs(&t->b2, t->knobs);
	if (t->trig) {
		trx_b2_trig(&t->b2);
		t->trig = 0;
	}
	if (!trx_b2_render(&t->b2, x)) {                 /* bloc muet (exactement nul) */
		for (k = 0; k < TRX_B2_BLOCK; k++)
			t->xh[HIST + k] = t->xl[HIST + k] = 0;
		t->z = t->z < HIST ? t->z + TRX_B2_BLOCK : HIST + TRX_B2_BLOCK;
	} else {
		for (k = 0; k < TRX_B2_BLOCK; k++) {
			t->xh[HIST + k] = (int16_t)(x[k] >> 8);
			t->xl[HIST + k] = (int16_t)(x[k] & 0xff);
		}
		for (k = TRX_B2_BLOCK; k > 0 && !x[k - 1]; k--)
			;
		t->z = TRX_B2_BLOCK - k;
	}
	t->n += TRX_B2_BLOCK;
}

void trx_b2_render32(s32 *out, char *v)
{
	struct track *t = track_of(v);
	int o, k;

	for (o = 0; o < 32; o++) {
		if (t->i >= t->n)
			md_block(t);
		if (t->i - HIST >= t->n - t->z) {
			out[o] = 0;                              /* toute la fenetre du filtre est nulle */
		} else {
			const short *c = rs_coef[t->frac];       /* a l'envers (headers.py) */
			const int16_t *xh = t->xh + t->i - HIST, *xl = t->xl + t->i - HIST;
			s32 hi = 0, lo = 0;
			long long y;
			/* x * c = (xh * c) * 256 + xl * c, chaque produit en 16 x 16 bits (muls.w, Q14, gen_resampler.py) */
#pragma GCC unroll 24
			for (k = 0; k < RS_T; k++) {
				const short ck = *c++;
				hi += *xh++ * ck;
				lo += *xl++ * ck;
			}
			/* (hi * 256 + lo) >> RS_SHIFT : 24 bits ; << 8 : pleine echelle du Machinedrum = pleine echelle Q31 */
			y = ((long long)hi << (16 - RS_SHIFT)) + (lo >> (RS_SHIFT - 8));
			out[o] = y > 0x7fffffff ? 0x7fffffff : (y < -0x7fffffffLL - 1 ? (s32)0x80000000 : (s32)y);
		}
		t->frac += RS_M;
		while (t->frac >= RS_L) {
			t->frac -= RS_L;
			t->i++;
		}
	}
}
