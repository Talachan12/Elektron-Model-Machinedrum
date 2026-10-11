"""Table de sinus de 32 768 points, comme la construit le DSP A du Machinedrum (P:$100068..$10008d) :
récurrence s[n+1] = 2 cos(w) s[n] - s[n-1] en double précision (48 bits), multiplication mpyuu/dmacsu/macsu/
dmacss. On ne recopie que l'algorithme et ses 4 constantes, pas la table."""

M56 = (1 << 56) - 1


def _s56(v):
    v &= M56
    return v - (1 << 56) if v >> 55 else v


def _s24(v):
    v &= 0xffffff
    return v - (1 << 24) if v >> 23 else v


def _limit48(a):
    """move a,l: : valeur 48 bits, saturée si a2 n'est pas l'extension de signe."""
    if a > (1 << 47) - 1:
        return (1 << 47) - 1
    if a < -(1 << 47):
        return -(1 << 47)
    return a


def _limit24(a):
    """move a,y: : a1, saturé."""
    return _limit48(a) >> 24


def table():
    x1, x0 = 0x7fffff, 0xd88586                 # 2 cos(w) / 2, en 48 bits
    hist = [0, (0x000648 << 24) | 0x7ed46b]     # l:0, l:1 (sin(2 pi / 32768) en 48 bits)
    out = [0, 0x000648]
    r1 = 1                                      # r1 pointe sur s[1] en entrant dans la boucle
    for _ in range(0x7ffe):
        y = hist[r1]                            # move l:(r1)+,y
        r1 ^= 1
        y1, y0 = _s24(y >> 24), y & 0xffffff
        a = (x0 * y0) << 1                      # mpyuu x0,y0,a
        a = _s56((a >> 24) + ((_s24(x1) * y0) << 1))   # dmacsu x1,y0,a
        a = _s56(a + ((y1 * x0) << 1))          # macsu y1,x0,a
        a = _s56((a >> 24) + ((_s24(x1) * y1) << 1))   # dmacss x1,y1,a
        a = _s56(a << 1)                        # asl a   (en parallèle : move l:(r1),y)
        older = hist[r1]
        y = older - (1 << 48) if older >> 47 else older
        a = _s56(a - y)                         # sub y,a
        hist[r1] = _limit48(a) & ((1 << 48) - 1)        # move a,l:(r1)
        out.append(_limit24(a))                 # move a,y:(r0)+
    return out


if __name__ == '__main__':
    import struct
    import sys
    t = table()
    if len(sys.argv) > 1:                       # comparaison avec un vidage du DSP émulé (int32 LE, 24 bits)
        ref = [_s24(v) for v in struct.unpack('<32768I', open(sys.argv[1], 'rb').read())]
        bad = [i for i in range(32768) if ref[i] != t[i]]
        print('identique' if not bad else 'différences : %d, première en %d (%d / %d)' % (
            len(bad), bad[0], ref[bad[0]], t[bad[0]]))
