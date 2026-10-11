/* Donnees du Machinedrum pour TRX-SD (trx_b2_md.c, genere par headers.py ; build.py --md les remplit). */
#ifndef MD_DATA_H
#define MD_DATA_H
#include <stdint.h>

extern const int32_t sd_dec1[128], sd_dec2[128], sd_benv[128], sd_clip[128];   /* fonction ColdFire 0x2013a6 */
extern const int32_t sd_k1[128], sd_k2[128];      /* DSP A : x:$140900 / x:$141900, selon PTCH */
extern const int32_t sd_snap[4096];               /* DSP A : P:$100881, echantillon d'attaque */

#endif
