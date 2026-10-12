"""Lecture de l'OS du Machinedrum (SPS-1 UW, OS 1.63) au build : les 4 tables que la fonction TRX-B2 de l'OS
(ColdFire, 0x201fd2) lit pour transformer les potards en mots du DSP. Rien de ce fichier n'est versionne.

Transport : messages F0 00 20 3C 02 00 7E de 112 octets = [checksum 2 quartets][adresse 6 quartets]
[32 mots de 16 bits en (2, 7, 7) bits]. Image a partir de 0x4000 : 4 sections [u32 longueur][u32 somme] + aPLib
(le codec des Models, tools/mtlib) ; la section 0 est l'OS ColdFire, charge en 0x200000."""
import hashlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from mtlib import aplib  # noqa: E402

OS_SHA256 = "a58cd61f2efacfb07add0c643162fb4365c30e73831f2021c17b4aa3b42cabd5"   # Elektron_SPS1-1UW_OS1.63.syx
CF_BASE = 0x200000
TABLES = {                  # adresse, pas (octets) entre deux valeurs de potard
    "pitch": (0x24bd94, 4),             # tbl[PTCH >> 7]
    "dec": (0x24bf94 + 0x190, 12),      # (DEC * 3) >> 7 = 3k
    "hold": (0x24c794 + 0x320, 8),      # (HOLD >> 4) & 0xffc = 8k octets
    "dirt": (0x24d794, 4),              # tbl[DIRT >> 7]
}

NAME_AT = 0x24f4b9          # "TRXB2PTCHDEC\0RAMPHOLDTICKNOISDIRTDIST" : verifie que c'est le bon OS
NAME = b"TRXB2PTCHDEC\x00RAMPHOLDTICKNOISDIRTDIST"
FN_AT, FN_HEAD = 0x201fd2, bytes.fromhex("4feffff448d70c04226f0010246f0014")


def image(path):
    d = pathlib.Path(path).read_bytes()
    img = {}
    i = 0
    while (s := d.find(b"\xf0", i)) >= 0:
        e = d.find(b"\xf7", s)
        m = d[s:e + 1]
        i = e + 1
        if len(m) != 112 or m[1:7] != bytes.fromhex("00203c02007e"):
            continue
        addr = 0
        for n in m[9:15]:
            addr = (addr << 4) | n
        data = bytearray()
        for g in range(15, 111, 3):
            data += ((m[g] << 14) | (m[g + 1] << 7) | m[g + 2]).to_bytes(2, "big")
        img[addr] = bytes(data)
    if not img:
        raise SystemExit("!! pas un OS du Machinedrum")
    base = min(img)
    out = bytearray(max(img) + 64 - base)
    for a, v in img.items():
        out[a - base:a - base + 64] = v
    return bytes(out), hashlib.sha256(d).hexdigest()


def coldfire_os(path):
    img, sha = image(path)
    n = int.from_bytes(img[:4], "big")
    if (sum(img[8:8 + n]) & 0xffffffff) != int.from_bytes(img[4:8], "big"):
        raise SystemExit("!! section 0 de l'OS du Machinedrum : somme fausse")
    return aplib.depack(img[:8 + n])[0], sha


# TRX-SD (fonction ColdFire 0x2013a6) : une valeur par potard
def _sd_cf(long, long_any):
    lut = lambda off, idx: [long(0x24bf94 + off + 4 * idx(k)) for k in range(128)]
    return {
        "sd_dec1": lut(0x370, lambda k: k),                              # DEC
        "sd_dec2": lut(0x3a0, lambda k: k >> 1),                         # DEC / 2 : bruit
        "sd_benv": [long_any(0x24bf94 + 0x3c + (((k << 7) * 5) >> 10)) for k in range(128)],  # adresse non alignee
        "sd_clip": [long(0x24c794 + 0x1e0 + 4 * (((k << 7) * 0x62b3) >> 21)) for k in range(128)],
    }


def dsp_image(path):
    """Mémoire du DSP A (section 1 de l'OS du Machinedrum) : {"P"|"X"|"Y" : {adresse : mot de 24 bits}}. Mots de 24
    bits petit-boutistes, en-tête de 4 mots, puis des enregistrements [espace][adresse][nombre] + mots."""
    img, _ = image(path)
    n0 = int.from_bytes(img[:4], "big")
    at = 8 + n0
    n1 = int.from_bytes(img[at:at + 4], "big")
    if (sum(img[at + 8:at + 8 + n1]) & 0xffffffff) != int.from_bytes(img[at + 4:at + 8], "big"):
        raise SystemExit("!! section 1 de l'OS du Machinedrum : somme fausse")
    d = aplib.depack(img[at:at + 8 + n1])[0]
    w = [int.from_bytes(d[i:i + 3], "little") for i in range(0, len(d) - 2, 3)]
    mem = {"P": {}, "X": {}, "Y": {}}
    i = 4
    while i + 3 <= len(w):
        sp, addr, cnt = w[i:i + 3]
        if cnt == 0 or sp > 2 or i + 3 + cnt > len(w):
            break
        m = mem["PXY"[sp]]
        for k in range(cnt):
            m[addr + k] = w[i + 3 + k]
        i += 3 + cnt
    return mem


def _s24(v):
    return v - (1 << 24) if v & 0x800000 else v


CH_LO, CH_HI = 0x380, 0x740                 # tranches des coefficients de TRX-CH (index - CH_LO)


def tables(path):
    cf, sha = coldfire_os(path)
    if sha != OS_SHA256:
        raise SystemExit(f"!! OS du Machinedrum inattendu (SHA-256 {sha[:8]}…) : il faut Elektron_SPS1-1UW_OS1.63.syx")
    at = lambda va, n: cf[va - CF_BASE:va - CF_BASE + n]
    if at(NAME_AT, len(NAME)) != NAME or at(FN_AT, len(FN_HEAD)) != FN_HEAD:
        raise SystemExit("!! ce n'est pas l'OS 1.63 du Machinedrum attendu (TRX-B2 introuvable)")

    def s32(b):
        v = int.from_bytes(b, "big")
        return v - (1 << 32) if v >> 31 else v

    out = {k: [s32(at(a + step * i, 4)) for i in range(128)] for k, (a, step) in TABLES.items()}
    out.update(_sd_cf(lambda va: s32(at(va, 4)), lambda va: s32(at(va, 4))))
    # TRX-SD, données du DSP A : coefficients des résonateurs du bruit (x:$140900 + yb - 3, x:$141900 + yb - 0x241,
    # yb = PTCH/32 + 0x400 = 4 potard + 0x400) et échantillon d'attaque (P:$100881, 4096 mots)
    dsp = dsp_image(path)
    out["sd_k1"] = [_s24(dsp["X"][0x140900 + 0x400 + 4 * k - 3]) for k in range(128)]
    out["sd_k2"] = [_s24(dsp["X"][0x141900 + 0x400 + 4 * k - 0x241]) for k in range(128)]
    out["sd_snap"] = [_s24(dsp["P"][0x100881 + i]) for i in range(4096)]
    # TRX-CH (ColdFire 0x201800 : GAP ; DSP A P:$10201f) : ses filtres 1 et 2 lisent K1 = x:$140900[f + x:$140000[q]],
    # K2 = x:$141900[f + x:$140080[q]] (f = LPF ou HPF, q = 0x46 sur le Machinedrum, ici SWEEP) : les deux tranches
    # utiles (CH_LO..CH_HI) et les décalages ; le filtre 3 est fixe (f = 0x30, q = 0)
    out["ch_gap"] = [s32(at(0x24bf94 + 0x38c + 4 * (((k << 7) >> 8) & 0xff), 4)) for k in range(128)]
    X = dsp["X"]
    out["ch_q1"] = [_s24(X[0x140000 + q]) for q in range(128)]
    out["ch_q2"] = [_s24(X[0x140080 + q]) for q in range(128)]
    fs = [(((k << 7) * 0xac77) >> 22) + 0x680 for k in range(128)] + [(((k << 7) * 0x2d83) >> 20) + 0x600 for k in range(128)]
    lo, hi = min(fs) + min(out["ch_q1"] + out["ch_q2"]), max(fs) + max(out["ch_q1"] + out["ch_q2"])
    if lo < CH_LO or hi >= CH_HI:
        raise SystemExit("!! TRX-CH : index de filtre hors des tranches lues")
    out["ch_t1"] = [_s24(X[0x140900 + i]) for i in range(CH_LO, CH_HI)]
    out["ch_t2"] = [_s24(X[0x141900 + i]) for i in range(CH_LO, CH_HI)]
    out["ch_dk"] = [_s24(X[0x140900 + 0x30 + out["ch_q1"][0]]), _s24(X[0x141900 + 0x30 + out["ch_q2"][0]])]
    return out, sha


if __name__ == "__main__":
    t, sha = tables(sys.argv[1])
    print("sha256", sha)
    for k, v in t.items():
        print(k, v[:4], "...", v[-2:])
