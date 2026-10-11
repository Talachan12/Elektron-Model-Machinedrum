/*
 * Produits du DSP56303 sur 32 bits pour les machines du Machinedrum (trx_sd.c) : pour x, y sur 24 bits,
 * hilo(x, y) = floor(x y / 2^23) et *lo = x y mod 2^23, c'est-a-dire a1 et a0 / 2 de mpy x,y,a.
 * ColdFire : l'EMAC de la boucle des voix (MACSR = 0xa0 : fractionnaire signe, troncature) donne, pour
 * (x << 8) * (y << 8), floor(x y / 2^15) en une instruction (mac.l puis movclr.l, qui laisse ACC0 a zero) ; muls.l
 * donne les 32 bits du bas : les deux couvrent le produit exact de 47 bits (jamais -1 * -1 ici).
 * Ordinateur : moities de 12 bits, 3 multiplications (Karatsuba).
 */
#ifndef MDMATH_H
#define MDMATH_H
#include <stdint.h>

static inline int32_t m_s24(uint32_t v) { return (int32_t)(v << 8) >> 8; }
static inline int32_t m_sat24(int32_t v) { return v > 0x7fffff ? 0x7fffff : (v < -0x800000 ? -0x800000 : v); }

#if defined(__mcoldfire__)
static inline int32_t m_prod15(int32_t x, int32_t y)
{
	int32_t r;
	__asm__ volatile ("mac.l %1,%2,%%acc0\n\tmovclr.l %%acc0,%0" : "=d"(r) : "d"(x << 8), "d"(y << 8));
	return r;
}

static inline int32_t hilo(int32_t x, int32_t y, int32_t *lo)
{
	*lo = (int32_t)((uint32_t)x * (uint32_t)y) & 0x7fffff;
	return m_prod15(x, y) >> 8;
}

static inline int32_t hi23(int32_t x, int32_t y)
{
	return m_prod15(x, y) >> 8;
}

static inline void emac_begin(void)                      /* ACC0 a zero (mac.l l'accumule) */
{
	int32_t r;
	__asm__ volatile ("movclr.l %%acc0,%0" : "=d"(r));
	(void)r;
}
#else
static inline int32_t hilo(int32_t x, int32_t y, int32_t *lo)
{
	const int32_t xh = x >> 12, xl = x & 0xfff, yh = y >> 12, yl = y & 0xfff;
	const int32_t hh = xh * yh, ll = xl * yl, mm = (xh + xl) * (yh + yl) - hh - ll;
	*lo = (int32_t)(((uint32_t)mm << 12) + (uint32_t)ll) & 0x7fffff;
	return 2 * hh + ((mm + (ll >> 12)) >> 11);
}

static inline int32_t hi23(int32_t x, int32_t y)
{
	int32_t lo;
	return hilo(x, y, &lo);
}

static inline void emac_begin(void)
{
}
#endif

/* move a,reg apres mpy x,y,a : a1 sature (seul -1 * -1 deborde) */
static inline int32_t mpy24(int32_t x, int32_t y)
{
	const int32_t h = hi23(x, y);
	return h > 0x7fffff ? 0x7fffff : h;
}

#endif
