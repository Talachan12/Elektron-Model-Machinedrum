/* TRX-CH du Machinedrum (OS 1.63), porte a l'echantillon pres (trx_ch.c). */
#ifndef TRX_CH_H
#define TRX_CH_H
#include <stdint.h>

#define TRX_CH_BLOCK 32

typedef struct {
	int32_t p[11];         /* y1..y10 (p[1..10]) : mots de la fonction ColdFire 0x201800 (y9, y10 au trig seulement) */
	int32_t g[5];          /* y11..y15 : gains des oscillateurs 2..6 (y8 au trig) */
	int32_t env;           /* y16 : enveloppe */
	int32_t n0, n1;        /* y19, y20 : bruit de Fibonacci */
	int32_t f1[4];         /* y21..y24 : filtre 1 (u[-2], u[-1], v[-2], v[-1]) */
	int32_t f2[4];         /* y25..y28 : filtre 2 (x[-2], x[-1], y[-2], y[-1]) */
	int32_t f3[4];         /* y29..y32 : filtre 3 */
	int32_t pos[6];        /* y33..y38 : phases des 6 oscillateurs carres */
	unsigned char dec;     /* DEC du dernier reglage (y10 n'est envoye qu'au trig) */
} trx_ch_t;

/* knobs : GAP DEC HPF LPF MTAL, 0..127, puis Q (0x46 sur le Machinedrum : resonance des filtres 1 et 2) */
void trx_ch_init(trx_ch_t *v);
void trx_ch_set_knobs(trx_ch_t *v, const uint8_t k[6]);
void trx_ch_trig(trx_ch_t *v);
int trx_ch_render(trx_ch_t *v, int32_t out[TRX_CH_BLOCK]);

#endif
