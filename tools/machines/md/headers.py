"""Fichiers generes du TRX-B2 (jamais versionnes) et donnees du Machinedrum pour build.py --md.

  trx_b2_md.c : sinus (md_sine.py) et tables de l'OS du Machinedrum, ou des valeurs bouche-trou (aucun octet
                Elektron) pour compiler le tweak versionne ; build.py --md les remplace au build ;
  rs_coef.h   : filtre 44,1 -> 48 kHz (gen_resampler.py)."""
import pathlib
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen_resampler  # noqa: E402
import md_os          # noqa: E402
import md_sine        # noqa: E402

# nom de la partie de charge utile ("md" dans le tweak) -> (symbole C, nombre de mots de 32 bits)
ARRAYS = {"sine": ("trx_b2_sine", 32768), "pitch": ("trx_b2_pitch_tbl", 128), "dec": ("trx_b2_dec_tbl", 128),
          "hold": ("trx_b2_hold_tbl", 128), "dirt": ("trx_b2_dirt_tbl", 128),
          "sd_dec1": ("sd_dec1", 128), "sd_dec2": ("sd_dec2", 128), "sd_benv": ("sd_benv", 128),
          "sd_clip": ("sd_clip", 128), "sd_k1": ("sd_k1", 128), "sd_k2": ("sd_k2", 128), "sd_snap": ("sd_snap", 4096),
          "ch_gap": ("ch_gap", 128), "ch_q1": ("ch_q1", 128), "ch_q2": ("ch_q2", 128),
          "ch_t1": ("ch_t1", 960), "ch_t2": ("ch_t2", 960), "ch_dk": ("ch_dk", 2)}
PLACEHOLDER = 0x5a5a5a5a


def md_values(md_syx):
    """{nom : valeurs} depuis l'OS du Machinedrum de l'utilisateur (le sinus : son algorithme)."""
    t, _ = md_os.tables(md_syx)
    t["sine"] = md_sine.table()
    return t


def md_parts(md_syx):
    """{nom : octets grand-boutistes}, comme en memoire sur le ColdFire."""
    return {k: b"".join(struct.pack(">i", x) for x in v) for k, v in md_values(md_syx).items()}


def _arr(sym, vals, per):
    rows = [", ".join(str(x) for x in vals[i:i + per]) for i in range(0, len(vals), per)]
    return "const int32_t %s[%d] = {\n\t%s\n};\n" % (sym, len(vals), ",\n\t".join(rows))


def write(md_syx, out):
    """md_syx = None : valeurs bouche-trou."""
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    vals = md_values(md_syx) if md_syx else {k: [PLACEHOLDER] * n for k, (_, n) in ARRAYS.items()}
    c = "/* Genere par headers.py%s : ne pas versionner. */\n#include \"trx_b2.h\"\n" % (
        " depuis l'OS du Machinedrum de l'utilisateur" if md_syx else " (bouche-trous)")
    for k, (sym, n) in ARRAYS.items():
        assert len(vals[k]) == n
        c += _arr(sym, vals[k], 16 if k == "sine" else 8)
    (out / "trx_b2_md.c").write_text(c)
    ph = gen_resampler.design()
    r = "/* Genere par gen_resampler.py : 44,1 -> 48 kHz, Q%d. */\n" % gen_resampler.SHIFT
    r += "#define RS_L %d\n#define RS_M %d\n#define RS_T %d\n#define RS_SHIFT %d\n" % (
        gen_resampler.L, gen_resampler.M, gen_resampler.T, gen_resampler.SHIFT)
    # chaque phase a l'envers : le pont parcourt la fenetre du plus ancien echantillon au plus recent
    r += "static const short rs_coef[RS_L][RS_T] = {\n" + "".join(
        "\t{ %s },\n" % ", ".join(str(x) for x in reversed(q)) for q in ph) + "};\n"
    (out / "rs_coef.h").write_text(r)
    return out


if __name__ == "__main__":
    print(write(sys.argv[1] if sys.argv[1] != "-" else None, sys.argv[2]))
