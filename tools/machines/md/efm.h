/* EFM-BD et EFM-SD du Machinedrum (OS 1.63), portes a l'echantillon pres (efm.c). */
#ifndef EFM_H
#define EFM_H
#include <stdint.h>

#define EFM_BLOCK 32

typedef struct {
	int32_t p[9];          /* y1..y8 (p[1..8]) : PTCH, DEC, MFRQ, MOD, MDEC, MFB, RAMP, RDEC */
	/* phases et retour, 48 bits sur le DSP : seuls les 39 bits du bas comptent (index de 15 bits + 24 bits de
	 * fraction, que des additions) -> partie entiere (modulo 2^32) et fraction de 24 bits */
	int32_t ph1i, ph1f;    /* y9:ya : phase du modulateur */
	int32_t ph2i, ph2f;    /* yb:yc : phase de la porteuse */
	int32_t ramp, menv, aenv;  /* yd, ye, yf */
	int32_t fbi, fbf;      /* y10:y11 : retour du modulateur */
} efm_bd_t;

typedef struct {
	int32_t p[11];         /* y1..y10 (p[1..10]) : PTCH, DEC, MFRQ, MOD, MDEC, 0x7a1200, NOIS, NDEC, 0x44aa20, HPF */
	int32_t ph1i, ph1f;    /* yb:yc */
	int32_t ph2i, ph2f;    /* yd:ye */
	int32_t menv, aenv, nenv;  /* yf, y10, y11 */
	int32_t fbi, fbf;      /* y12:y13 */
	int32_t n0, n1;        /* y14, y15 : bruit de Fibonacci */
	int32_t hs1, ho1;      /* y16, y17 : passe-haut du bruit (etat, derniere sortie) */
	int32_t hs2, ho2;      /* y18, y19 : passe-haut de la sortie */
} efm_sd_t;

/* knobs : 0..127, dans l'ordre du Machinedrum */
void efm_bd_init(efm_bd_t *v);
void efm_bd_set_knobs(efm_bd_t *v, const uint8_t k[8]);   /* PTCH DEC RAMP RDEC MOD MFRQ MDEC MFB */
void efm_bd_trig(efm_bd_t *v);
int efm_bd_render(efm_bd_t *v, int32_t out[EFM_BLOCK]);

void efm_sd_init(efm_sd_t *v);
void efm_sd_set_knobs(efm_sd_t *v, const uint8_t k[8]);   /* PTCH DEC NOIS NDEC MOD MFRQ MDEC HPF */
void efm_sd_trig(efm_sd_t *v);
int efm_sd_render(efm_sd_t *v, int32_t out[EFM_BLOCK]);

#endif
