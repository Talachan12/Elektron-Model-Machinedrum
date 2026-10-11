#!/usr/bin/env python3
"""Génère le tweak de la machine TRX-B2 : la grosse caisse TRX-B2 du Machinedrum (OS 1.63), portée à l'échantillon
près depuis le code de son DSP, en 7e machine du Model:Cycles (tools/machines/trx_b2/bridge.c).

Même mécanique que MACRO (gen_macro.py, notes/43) : charge utile à gs.PAY_ALONE, détours et tables déplacées de
gs.LAYOUT ; seule la compilation change (notre C au lieu de Braids).

Aucun octet Elektron dans le JSON : le code est compilé avec des bouche-trous à la place du sinus et des tables du
Machinedrum (headers.py, fichier C à part : le compilateur ne peut pas les replier), et la charge utile porte, pour
chacun, une recette {"md": nom, "size": n} que build.py remplit au build depuis TON OS du Machinedrum (--md) :
tables de la fonction 0x201fd2, sinus recalculé par l'algorithme du DSP (md_sine.py).

    M68K_CROSS=m68k-elf- python3 tools/gen_trx_b2.py --cycles firmware/model-cycles_OS1.13.syx \\
        [--md firmware/Elektron_SPS1-1UW_OS1.63.syx] [--check]

--md : vérifie en plus que la charge utile remplie par build.py est, octet pour octet, celle du même code compilé
avec les vraies données.
"""
import argparse
import json
import struct
import tempfile
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "emu"))
sys.path.insert(0, str(HERE / "machines" / "trx_b2"))

import gen_macro as gm             # noqa: E402
import gen_sdvintage_exact as gx   # noqa: E402
import gen_sdvintage_7th as g7     # noqa: E402
import gen_syntakt_engines as gs   # noqa: E402
import headers                     # noqa: E402
import usb_steady                  # noqa: E402

SRC = HERE / "machines" / "trx_b2"
OUT = gm.DEV / "26-trx-b2.json"
CFLAGS = ["-mcpu=54418", "-O2", "-U_FORTIFY_SOURCE", "-ffreestanding", "-fno-builtin",
          "-fno-tree-loop-distribute-patterns", "-nostdlib", "-fno-pic", "-fno-common", "-ffunction-sections",
          "-fdata-sections", "-fomit-frame-pointer", "-Wall", "-Wextra", "-Werror"]
# COLOR = DIST, SHAPE = DIRT, SWEEP = RAMP, CONTOUR = HOLD ; défauts de la machine du Machinedrum ; image : KICK
MACHINE = dict(name="TrxB2", image=0, decay=64,
               knobs=(("Distortion", "DIST", 0), ("Dirt", "DIRT", 0), ("Ramp", "RAMP", 96), ("Hold", "HOLD", 64)))
LINK = """SECTIONS
{{
  .text {code:#x} : {{ *(.text.trx_b2_update) *(.text.trx_b2_render32) *(.text*) }}
  .rodata : {{ *(.rodata*) }}
  .data : {{ *(.data*) }}
  .bss {bss:#x} (NOLOAD) : {{ *(.bss*) *(COMMON) }}
  /DISCARD/ : {{ *(.comment) *(.note*) *(.eh_frame*) }}
}}
"""


def compile_machine(tmp, md_syx, pay, bss_at=None, code_end=None):
    """Comme gm.compile_machine, pour notre C : (octets de pay, symboles, fin du BSS)."""
    bss_at = pay + gm.BSS_OFF if bss_at is None else bss_at
    code_end = gs.STUBS if code_end is None else code_end
    gen = headers.write(md_syx, tmp / "gen")
    objs = []
    for src in (SRC / "bridge.c", SRC / "trx_b2.c", gen / "trx_b2_md.c"):
        o = tmp / (src.stem + ".o")
        gx.run([gx.CROSS + "gcc", *CFLAGS, f"-I{SRC}", f"-I{gen}", "-c", str(src), "-o", str(o)])
        objs.append(o)
    ld, elf, out = tmp / "link.ld", tmp / "trx_b2.elf", tmp / "trx_b2.bin"
    ld.write_text(LINK.format(code=pay, bss=bss_at))
    gx.run([gx.CROSS + "ld", "-T", str(ld), "--gc-sections", "--no-warn-rwx-segments", "-e", "trx_b2_update",
            "-u", "trx_b2_render32", "-o", str(elf), *map(str, objs)])
    secs = {}
    for line in gx.run([gx.CROSS + "objdump", "-h", str(elf)]).splitlines():
        f = line.split()
        if len(f) > 4 and f[0].isdigit():
            secs[f[1]] = (int(f[3], 16), int(f[2], 16))
    extra = set(secs) - {".text", ".rodata", ".data", ".bss"}
    if extra:
        raise SystemExit(f"!! sections inattendues : {sorted(extra)}")
    undef = [l for l in gx.run([gx.CROSS + "nm", "-u", str(elf)]).splitlines() if l.strip()]
    if undef:
        raise SystemExit(f"!! symboles non résolus : {undef}")
    gx.run([gx.CROSS + "objcopy", "-O", "binary", "-R", ".bss", str(elf), str(out)])
    blob = out.read_bytes()
    syms = {}
    for line in gx.run([gx.CROSS + "nm", str(elf)]).splitlines():
        p_ = line.split()
        if len(p_) == 3:
            syms[p_[2]] = int(p_[0], 16)
    if pay + len(blob) > code_end:
        raise SystemExit(f"!! code et tables trop grands : {len(blob)} o")
    bss = secs.get(".bss", (bss_at, 0))
    if bss[0] != bss_at:
        raise SystemExit("!! BSS")
    # noms attendus par gm.build_tweak
    syms["macro_update"], syms["macro_render"] = syms["trx_b2_update"], syms["trx_b2_render32"]
    syms[gm.BRAIDS_RENDER] = syms["trx_b2_render"]
    return blob, syms, (bss[0] + bss[1] + 3) & ~3


def build_tweak(img, md_syx=None):
    """md_syx = None : le tweak versionné (bouche-trous remplacés par des recettes « md »)."""
    gm.MACHINE, gm.compile_machine = MACHINE, compile_machine
    out, info = gm.build_tweak(img, md_syx, None)
    if md_syx is None:
        parts = out["append"]["parts"]
        blob = bytearray.fromhex(parts[0]["hex"])
        pay = int(parts[0]["dest"], 16)
        for name, (sym, n) in headers.ARRAYS.items():
            at = info["syms"][sym] - pay
            if blob[at:at + 4 * n] != struct.pack(">I", headers.PLACEHOLDER) * n:
                raise SystemExit(f"!! {sym} : bouche-trous introuvables")
            blob[at:at + 4 * n] = bytes(4 * n)
            parts.append({"dest": f"{info['syms'][sym]:#x}", "md": name, "size": 4 * n})
        parts[0]["hex"] = blob.hex()
    out["id"] = "trx-b2"
    out["order"] = 26
    out["name"] = "Machine TrxB2 : la grosse caisse TRX-B2 du Machinedrum (OS 1.63), à l'échantillon près"
    out["description"] = [
        "TRX-B2 du Machinedrum en 7e machine, après les 6 d'origine : le code du DSP A du Machinedrum porté en C,",
        "identique à l'échantillon près (comparé au DSP émulé), rendu à 44,1 kHz puis ramené à 48 kHz (filtre",
        "polyphase 160/147). PITCH = PTCH (+ note du trig), DECAY = DEC, SWEEP = RAMP, CONTOUR = HOLD, COLOR = DIST,",
        "SHAPE = DIRT, PUNCH = TICK (64 ou 0) ; NOIS = 0. Généré par tools/gen_trx_b2.py. Aucun octet Elektron :",
        "build.py --md lit le sinus et les tables dans TON OS du Machinedrum (Elektron_SPS1-1UW_OS1.63.syx).",
    ]
    out["status"] = "experimental"
    out["md"] = {"os": "Elektron_SPS1-1UW_OS1.63.syx", "sha256": headers.md_os.OS_SHA256}
    # envoi à l'USB à heure fixe (usb_steady) : les octets de référence sont ceux de 6ch-usbup et des autres
    # machines ajoutées (m68k-linux-gnu-as) ; m68k-elf-as code un lea en (d16,pc) et décale feed.S de 4 octets.
    # On reprend donc ces écritures, identiques à l'octet près, dans 25-macro.json.
    ref = {w["off"]: w for w in json.loads((gm.DEV / "25-macro.json").read_text(encoding="utf-8"))["writes"]}
    for i, w in enumerate(out["writes"]):
        if w["off"] in {x["off"] for x in usb_steady.writes()}:
            if ref[w["off"]]["old"] != w["old"] and set(ref[w["off"]]["old"] + w["old"]) != {"f"}:
                raise SystemExit(f"!! usb_steady : {w['off'] + gx.BASE:#x}")
            out["writes"][i] = ref[w["off"]]
    # tout tweak qui ajoute une charge utile après l'image (même place, même crochet de démarrage)
    appended = {json.loads(f.read_text(encoding="utf-8"))["id"] for f in gm.DEV.glob("[0-9]*.json")
                if f != OUT and "append" in json.loads(f.read_text(encoding="utf-8"))}
    out["conflicts"] = sorted((set(out["conflicts"]) | appended | {"macro"}) - {"trx-b2"})
    out["symbols"] = {"trx_b2_update": f"{info['syms']['trx_b2_update']:#x}",
                      "trx_b2_render32": f"{info['syms']['trx_b2_render32']:#x}",
                      "trx_b2_render": f"{info['syms']['trx_b2_render']:#x}"}
    return out, info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="model-cycles_OS1.13.syx officiel")
    ap.add_argument("--md", help="Elektron_SPS1-1UW_OS1.63.syx : vérifie la recette contre les vraies données")
    ap.add_argument("--check", action="store_true", help="vérifie que le JSON versionné correspond")
    args = ap.parse_args()
    img = g7.cycles_main(args.cycles)
    if len(img) != gx.IMAGE_LEN:
        raise SystemExit("!! ce n'est pas le MAIN OS 1.13 officiel")
    tweak, info = build_tweak(img)
    text = json.dumps(tweak, indent=1, ensure_ascii=False) + "\n"
    print(f"  {tweak['id']} : {len(tweak['writes'])} écritures, code et tables {info['code']} o, variables "
          f"{info['bss']} o, ajout à l'image {info['image']} o")
    if args.md:
        import build                                   # noqa: E402
        md = pathlib.Path(args.md).resolve()
        filled = build.payload_runtime(tweak, img, None, headers.md_parts(md))
        real, _ = build_tweak(img, md)
        same = filled == build.payload_runtime(real, img, None)
        print(f"    recette remplie depuis l'OS du Machinedrum = code compilé avec les vraies données : "
              f"{'oui' if same else 'NON'}")
        if not same:
            raise SystemExit(1)
    if args.check:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print(f"    {OUT.name} {'est à jour' if ok else 'NE CORRESPOND PAS (autre GCC ?)'}")
        raise SystemExit(0 if ok else 1)
    OUT.write_text(text, encoding="utf-8")
    print(f"    écrit : {OUT}")


if __name__ == "__main__":
    main()
