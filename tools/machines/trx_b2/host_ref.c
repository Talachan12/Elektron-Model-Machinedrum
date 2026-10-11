/*
 * Reference du pont TRX-B2 compilee pour l'ordinateur (tools/emu/test_trx_b2.py) : bridge.c + trx_b2.c, avec une
 * voix et des parametres simules. Une ligne par bloc du Cycles sur l'entree :
 *   trig pitch color shape sweep contour punch decay note      (potards en 8.8, note en demi-tons)
 * Sortie : 32 x int32 par bloc (Q31), petit-boutiste.
 */
#include <stdio.h>
#include <string.h>
#include <stdint.h>

char voices[6 * 0x31c];

void trx_b2_update(int32_t pmod, char *v, const char *p);
void trx_b2_render32(int32_t *out, char *v);

static void w16(char *p, int o, int x)               /* l'ordinateur est petit-boutiste, comme le pont le lit */
{
	*(int16_t *)(p + o) = (int16_t)x;
}

int main(void)
{
	char p[0x40], *v = voices;
	int trig, pitch, color, shape, sweep, contour, punch, decay, note;
	int32_t out[32];

	memset(p, 0, sizeof p);
	while (scanf("%d %d %d %d %d %d %d %d %d", &trig, &pitch, &color, &shape, &sweep, &contour, &punch, &decay,
		     &note) == 9) {
		w16(p, 0x14, pitch);
		w16(p, 0x16, color);
		w16(p, 0x18, shape);
		w16(p, 0x1a, sweep);
		w16(p, 0x1c, contour);
		w16(p, 0x1e, punch);
		p[0x24] = (char)(decay >> 8);                /* octet fort du mot 8.8 sur le ColdFire */
		*(int32_t *)(v + 0x38) = trig;
		trx_b2_update(note << 16, v, p);
		trx_b2_render32(out, v);
		fwrite(out, 4, 32, stdout);
	}
	return 0;
}
