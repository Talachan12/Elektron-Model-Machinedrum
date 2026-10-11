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

    return {k: [s32(at(a + step * i, 4)) for i in range(128)] for k, (a, step) in TABLES.items()}, sha


if __name__ == "__main__":
    t, sha = tables(sys.argv[1])
    print("sha256", sha)
    for k, v in t.items():
        print(k, v[:4], "...", v[-2:])
