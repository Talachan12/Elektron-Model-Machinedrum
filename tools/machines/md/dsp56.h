/*
 * Modele exact des operations du DSP56303 (reference pour l'ordinateur : trx_sd_ref.c) : accumulateur de 56 bits
 * (a2:a1:a0, a1 au bit 24) dans un int64_t, mots de 24 bits dans des int32_t.
 */
#ifndef DSP56_H
#define DSP56_H
#include <stdint.h>

typedef int64_t a56;

static inline int32_t d_s24(uint32_t v) { return (int32_t)(v << 8) >> 8; }
static inline a56 d_w56(a56 v) { return (a56)((uint64_t)v << 8) >> 8; }
static inline a56 d_from24(int32_t v) { return (a56)((uint64_t)(int64_t)v << 24); }   /* move reg,a */
static inline a56 d_from48(a56 v) { return (a56)((uint64_t)v << 16) >> 16; }          /* move l:,a */
static inline int32_t d_a1(a56 a) { return d_s24((uint32_t)(a >> 24)); }             /* move a1,reg (sans limite) */
static inline uint32_t d_idx(a56 a) { return (uint32_t)(a >> 24) & 0xffffff; }       /* move a1,rN */
static inline int32_t d_lim24(a56 a)                                                 /* move a,reg : limiteur */
{
	if (a > 0x7fffffffffffLL)
		return 0x7fffff;
	if (a < -0x800000000000LL)
		return -0x800000;
	return (int32_t)(a >> 24);
}
static inline a56 d_mpy(int32_t x, int32_t y) { return (a56)x * y * 2; }
static inline a56 d_and1(a56 a, uint32_t imm)                                        /* and #imm,a : a1 seul */
{
	return (a & ~((a56)0xffffff << 24)) | ((a56)((uint32_t)(a >> 24) & 0xffffff & imm) << 24);
}

#endif
