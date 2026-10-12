/* Donnees du Machinedrum pour TRX-SD (trx_b2_md.c, genere par headers.py ; build.py --md les remplit). */
#ifndef MD_DATA_H
#define MD_DATA_H
#include <stdint.h>

extern const int32_t sd_dec1[128], sd_dec2[128], sd_benv[128], sd_clip[128];   /* fonction ColdFire 0x2013a6 */
extern const int32_t sd_k1[128], sd_k2[128];      /* DSP A : x:$140900 / x:$141900, selon PTCH */
extern const int32_t sd_snap[4096];               /* DSP A : P:$100881, echantillon d'attaque */
/* TRX-CH : GAP (fonction ColdFire 0x201800) ; coefficients de ses filtres (DSP A) : K1 = ch_t1[f + ch_q1[q] - CH_LO],
 * K2 = ch_t2[f + ch_q2[q] - CH_LO] (x:$140900 / x:$141900 a partir de CH_LO, x:$140000 / x:$140080), filtre 3 fixe */
#define CH_LO 0x380
extern const int32_t ch_gap[128], ch_q1[128], ch_q2[128], ch_t1[960], ch_t2[960], ch_dk[2];

#endif
