/* TRX-SD du Machinedrum (OS 1.63), porte a l'echantillon pres (trx_sd.c). */
#ifndef TRX_SD_H
#define TRX_SD_H
#include <stdint.h>

#define TRX_SD_BLOCK 32

typedef struct {
	int32_t p[13];         /* y1..y12 (p[1..12]) : mots de la fonction ColdFire 0x2013a6 */
	int32_t bump_n;        /* yd : blocs d'attaque de la bosse de hauteur (0x140) */
	int32_t aenv;          /* ye : ampli du ton */
	int32_t nenv;          /* yf : ampli du bruit */
	int32_t bump;          /* y10 : bosse de hauteur */
	int32_t pos;           /* y11 : position dans l'echantillon d'attaque (+0x20 par bloc) */
	int32_t ph1, ph1f;     /* y12:y13 : phase de l'oscillateur 1 (index 15 bits, fraction 24 bits) */
	int32_t ph2, ph2f;     /* y14:y15 : oscillateur 2 */
	int32_t last;          /* y16 : dernier echantillon rendu */
	int32_t n0, n1;        /* y17, y18 : bruit de Fibonacci */
	int32_t f1a, f1b;      /* y19, y1a : 1er resonateur */
	int32_t f2a, f2b;      /* y1b, y1c : 2e resonateur */
	int32_t dist;          /* y1d : saturation du ton (CLIP) */
} trx_sd_t;

/* knobs : PTCH DEC BUMP BENV SNAP TONE TUNE CLIP, 0..127 */
void trx_sd_init(trx_sd_t *v);
void trx_sd_set_knobs(trx_sd_t *v, const uint8_t k[8]);
void trx_sd_trig(trx_sd_t *v);
int trx_sd_render(trx_sd_t *v, int32_t out[TRX_SD_BLOCK]);

#endif
