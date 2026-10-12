/* TRX-B2 (Machinedrum SPS-1 UW, OS 1.63) - bit-exact C port of DSP56303 code
 * at P:$102c31 (init), $102c4a (trig), $102c5a (render 32 samples).
 * Samples are 24-bit signed integers (DSP fractional * 2^23) held in int32_t. */
#ifndef TRX_B2_H
#define TRX_B2_H
#include <stdint.h>

#define TRX_B2_BLOCK 32

typedef struct {
	/* parameters from the host, y:(r6+1..12) */
	int32_t pitch, ramp, dec, hold, slope[4], dirt_shift, dirt_round, noise, tick;
	/* state, y:(r6+13..25) */
	int32_t ramp_decay;   /* +$d  */
	int32_t ramp_env;     /* +$e  */
	int32_t attack;       /* +$10 */
	int32_t noise_env;    /* +$11 */
	int32_t noise_decay;  /* +$12 */
	int32_t noise_a, noise_b; /* +$13, +$14 */
	int32_t amp_env;      /* +$15 */
	int32_t tick_env;     /* +$17 */
	int32_t hold_env;     /* +$18 */
	int32_t phase;        /* +$19 */
} trx_b2_t;

/* Donnees du Machinedrum, dans un fichier a part (trx_b2_md.c, genere par headers.py) : le compilateur ne peut
 * pas les replier dans le code, et build.py --md les remplit depuis l'OS du Machinedrum de l'utilisateur.
 * Sinus de 32 768 points tel que le DSP le construit en $148000 (md_sine.py) ; tables de la fonction 0x201fd2. */
extern const int32_t trx_b2_sine[32768];
extern const int32_t trx_b2_pitch_tbl[128], trx_b2_dec_tbl[128], trx_b2_hold_tbl[128], trx_b2_dirt_tbl[128];

void trx_b2_init(trx_b2_t *v);
/* knobs: PTCH DEC RAMP HOLD TICK NOIS DIRT DIST, 0..127 each */
void trx_b2_set_knobs(trx_b2_t *v, const uint8_t knobs[8]);
void trx_b2_trig(trx_b2_t *v);
/* returns 0 when the block is exactly silent (out all zero) */
int trx_b2_render(trx_b2_t *v, int32_t out[TRX_B2_BLOCK]);

#endif
