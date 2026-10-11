/*
 * Machines du Machinedrum (OS 1.63) ajoutees au Model:Cycles (OS 1.13), portees a l'echantillon pres depuis le code
 * du DSP A du Machinedrum : TrxB2 (trx_b2.c), TrxSD (trx_sd.c) et TrxCH (trx_ch.c). Les tables et l'echantillon d'attaque du
 * Machinedrum sont lus au build dans le fichier OS du Machinedrum de l'utilisateur ; le sinus est recalcule par
 * l'algorithme du DSP (md_sine.py).
 *
 * Contrat de la boucle des voix (notes/14, comme MACRO) : update(pmod, v, p) puis render(out, v), une fois par
 * bloc de 32 trames a 48 kHz. p = parametres de la piste (mots 8.8 : +0x14 PITCH, +0x16 COLOR, +0x18 SHAPE,
 * +0x1a SWEEP, +0x1c CONTOUR, +0x1e PUNCH, +0x24 DECAY) ; v+0x38 : trig ; out : 32 x int32 (Q31).
 *
 * Chaque machine rend comme sur le Machinedrum, par blocs de 32 echantillons a 44,1 kHz ; un filtre polyphase
 * (160/147, 24 coefficients par phase, echantillons arrondis a 16 bits : erreur vers -100 dB sous la pleine
 * echelle) ramene a 48 kHz. Une entree update par machine, un rendu commun.
 *
 * Potards (PITCH = PTCH + note du trig - 60, DECAY = DEC pour toutes) :
 *   TrxB2 : SWEEP = RAMP, CONTOUR = HOLD, COLOR = DIST, SHAPE = DIRT, PUNCH = TICK 64 (sinon 0) ; NOIS = 0.
 *   TrxSD : COLOR = SNAP, SHAPE = TONE, SWEEP = BUMP, CONTOUR = BENV, PUNCH = CLIP 64 (sinon 0) ; TUNE = 64.
 *   TrxCH : PITCH = LPF (accord des resonateurs, + note du trig - 60), COLOR = MTAL, SHAPE = HPF, CONTOUR = GAP ;
 *           pas de PTCH sur le Machinedrum ; SWEEP = Q (resonance, 70 = le Machinedrum) ; PUNCH ne sert pas.
 * Sans PUNCH, les valeurs fixes sont les defauts du Machinedrum.
 */
#include "trx_b2.h"
#include "trx_sd.h"
#include "trx_ch.h"
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
#define MARK        0x4d440000                       /* 'MD' + machine : marque de la voix initialisee */
#define TRIG_NOTE0  60                               /* note du trig qui laisse PTCH = PITCH */

enum { M_B2, M_SD, M_CH };

#define V32(o)      (*(s32 *)(v + (o)))
#define P16(o)      (*(const s16 *)(p + (o)))

#define HIST        (RS_T - 1)

struct track {
	s32 kind;
	union {
		trx_b2_t b2;
		trx_sd_t sd;
		trx_ch_t ch;
	} u;
	/* 44,1 kHz : historique du filtre puis le dernier bloc, arrondis a 16 bits pour le filtre (muls.w) ; l'erreur
	 * (1/2 bit de poids 2^8 sur 24 bits) reste vers -90 dB sous la pleine echelle */
	int16_t xh[HIST + TRX_B2_BLOCK];
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

static void track_init(struct track *t, s32 kind)
{
	int k;

	t->kind = kind;
	if (kind == M_B2)
		trx_b2_init(&t->u.b2);
	else if (kind == M_SD)
		trx_sd_init(&t->u.sd);
	else
		trx_ch_init(&t->u.ch);
	for (k = 0; k < HIST + TRX_B2_BLOCK; k++)
		t->xh[k] = 0;
	t->n = HIST;
	t->z = HIST;
	t->i = HIST;
	t->frac = 0;
	t->trig = 0;
}

static void update(s32 kind, s32 pmod, char *v, const char *p)
{
	struct track *t = track_of(v);
	unsigned char *k = t->knobs;
	const s32 punch = P16(0x1e) != 0;
	s32 dec, ptch;

	if (V32(MARK_OFF) != MARK + kind) {              /* 1re note sur cette machine (comme l'init du DSP) */
		track_init(t, kind);
		V32(MARK_OFF) = MARK + kind;
	}
	ptch = knob(P16(0x14)) + (pmod >> 16) - TRIG_NOTE0;
	dec = (s8)p[0x24];
	k[0] = ptch < 0 ? 0 : (ptch > 127 ? 127 : ptch);
	k[1] = dec < 0 ? 0 : (dec > 127 ? 127 : dec);
	if (kind == M_B2) {                              /* PTCH DEC RAMP HOLD TICK NOIS DIRT DIST */
		k[2] = knob(P16(0x1a));
		k[3] = knob(P16(0x1c));
		k[4] = punch ? 64 : 0;
		k[5] = 0;
		k[6] = knob(P16(0x18));
		k[7] = knob(P16(0x16));
	} else if (kind == M_CH) {                       /* GAP DEC HPF LPF MTAL */
		k[3] = k[0];                                 /* LPF <- PITCH (+ note) */
		k[0] = knob(P16(0x1c));                      /* GAP <- CONTOUR */
		k[2] = knob(P16(0x18));                      /* HPF <- SHAPE */
		k[4] = knob(P16(0x16));                      /* MTAL <- COLOR */
		k[5] = knob(P16(0x1a));                      /* Q <- SWEEP (0x46 sur le Machinedrum) */
	} else {                                         /* PTCH DEC BUMP BENV SNAP TONE TUNE CLIP */
		k[2] = knob(P16(0x1a));
		k[3] = knob(P16(0x1c));
		k[4] = knob(P16(0x16));
		k[5] = knob(P16(0x18));
		k[6] = 64;
		k[7] = punch ? 64 : 0;
	}
	if (V32(0x38))
		t->trig = 1;
}

void trx_b2_update(s32 pmod, char *v, const char *p) { update(M_B2, pmod, v, p); }
void trx_sd_update(s32 pmod, char *v, const char *p) { update(M_SD, pmod, v, p); }
void trx_ch_update(s32 pmod, char *v, const char *p) { update(M_CH, pmod, v, p); }

/* un bloc du Machinedrum : l'OS envoie les parametres, puis le DSP joue le trig et rend 32 echantillons */
static void md_block(struct track *t)
{
	s32 x[TRX_B2_BLOCK];
	int k;

	for (k = 0; k < HIST; k++)                       /* garde les HIST derniers echantillons */
		t->xh[k] = t->xh[t->n - HIST + k];
	t->i -= t->n - HIST;
	t->n = HIST;
	if (t->kind == M_B2) {
		trx_b2_set_knobs(&t->u.b2, t->knobs);
		if (t->trig)
			trx_b2_trig(&t->u.b2);
		k = trx_b2_render(&t->u.b2, x);
	} else if (t->kind == M_SD) {
		trx_sd_set_knobs(&t->u.sd, t->knobs);
		if (t->trig)
			trx_sd_trig(&t->u.sd);
		k = trx_sd_render(&t->u.sd, x);
	} else {
		trx_ch_set_knobs(&t->u.ch, t->knobs);
		if (t->trig)
			trx_ch_trig(&t->u.ch);
		k = trx_ch_render(&t->u.ch, x);
	}
	t->trig = 0;
	if (!k) {                                        /* bloc muet (exactement nul) */
		for (k = 0; k < TRX_B2_BLOCK; k++)
			t->xh[HIST + k] = 0;
		t->z = t->z < HIST ? t->z + TRX_B2_BLOCK : HIST + TRX_B2_BLOCK;
	} else {
		for (k = 0; k < TRX_B2_BLOCK; k++) {
			const s32 r = (x[k] + 0x80) >> 8;
			t->xh[HIST + k] = (int16_t)(r > 0x7fff ? 0x7fff : r);
		}
		for (k = TRX_B2_BLOCK; k > 0 && !x[k - 1]; k--)
			;
		t->z = TRX_B2_BLOCK - k;
	}
	t->n += TRX_B2_BLOCK;
}

/* rendu commun aux machines (la table render de l'OS a une entree par machine) */
void md_render32(s32 *out, char *v)
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
			const int16_t *xh = t->xh + t->i - HIST;
			s32 acc = 0;
			/* 16 x 16 bits (muls.w), coefficients Q14 (gen_resampler.py) */
#pragma GCC unroll 24
			for (k = 0; k < RS_T; k++)
				acc += *xh++ * *c++;
			/* acc / 2^14 : echantillon sur 16 bits ; << 16 : pleine echelle du Machinedrum = pleine echelle Q31 */
			out[o] = acc > 0x1fffffff ? 0x7fffffff : (acc < -0x20000000 ? (s32)0x80000000 : acc * 4);
		}
		t->frac += RS_M;
		while (t->frac >= RS_L) {
			t->frac -= RS_L;
			t->i++;
		}
	}
}
