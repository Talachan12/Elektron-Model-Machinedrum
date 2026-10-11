#!/usr/bin/env python3
"""Génère le tweak des machines du Machinedrum (OS 1.63) ajoutées au Model:Cycles, portées à l'échantillon près depuis
le code de son DSP : TrxB2 (7e machine), TrxSD (8e), TrxCH (9e). Sources : tools/machines/md/ (bridge.c, trx_b2.c, trx_sd.c,
trx_ch.c).

Même mécanique que MACRO (gen_macro.py, notes/43) et que les moteurs du Syntakt (gen_syntakt_engines.py) : charge
utile à gs.PAY_ALONE, détours (gs.detours_asm) et tables déplacées de gs.LAYOUT, pour n machines ajoutées.

Aucun octet Elektron dans le JSON : le code est compilé avec des bouche-trous à la place du sinus et des tables du
Machinedrum (headers.py, fichier C à part : le compilateur ne peut pas les replier), et la charge utile porte, pour
chacun, une recette {"md": nom, "size": n} que build.py remplit au build depuis TON OS du Machinedrum (--md) :
tables des fonctions ColdFire de l'OS du Machinedrum, sinus recalculé par l'algorithme du DSP (md_sine.py).

    M68K_CROSS=m68k-elf- python3 tools/gen_md_machines.py --cycles firmware/model-cycles_OS1.13.syx \\
        [--md firmware/Elektron_SPS1-1UW_OS1.63.syx] [--check]

--md : vérifie en plus que la charge utile remplie par build.py est, octet pour octet, celle du même code compilé
avec les vraies données.
"""
import argparse
import json
import pathlib
import struct
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "emu"))
sys.path.insert(0, str(HERE / "machines" / "md"))

import gen_macro as gm             # noqa: E402
import gen_sdvintage_exact as gx   # noqa: E402
import gen_sdvintage_7th as g7     # noqa: E402
import gen_syntakt_engines as gs   # noqa: E402
import gen_syntakt_machines as g8  # noqa: E402
import headers                     # noqa: E402
import sprites                     # noqa: E402
import usb_steady                  # noqa: E402
import voice_loop                  # noqa: E402

SRC = HERE / "machines" / "md"
OUT = gm.DEV / "26-md-machines.json"
TID = "md-machines"
BASE = gx.BASE
CFLAGS = ["-mcpu=54418", "-O2", "-U_FORTIFY_SOURCE", "-ffreestanding", "-fno-builtin",
          "-fno-tree-loop-distribute-patterns", "-nostdlib", "-fno-pic", "-fno-common", "-ffunction-sections",
          "-fdata-sections", "-fomit-frame-pointer", "-Wall", "-Wextra", "-Werror"]
# knobs : COLOR, SHAPE, SWEEP, CONTOUR = (nom long, nom court, défaut) ; decay : défaut de DECAY ; image : celle
# d'une machine du Cycles (l'OS n'en a que 6). Défauts : ceux du Machinedrum.
MACHINES = (
    dict(name="TrxB2", image=0, decay=64, update="trx_b2_update",
         knobs=(("Distortion", "DIST", 0), ("Dirt", "DIRT", 0), ("Ramp", "RAMP", 96), ("Hold", "HOLD", 64))),
    dict(name="TrxSD", image=1, decay=32, update="trx_sd_update",
         knobs=(("Snap", "SNAP", 64), ("Tone", "TONE", 64), ("Bump", "BUMP", 0), ("Bump Env", "BENV", 64))),
    # TRX-CH : PITCH = LPF (défaut 64) ; SWEEP = Q, résonance des filtres (70 : celle du Machinedrum)
    dict(name="TrxCH", image=2, decay=32, update="trx_ch_update",
         knobs=(("Metal", "MTAL", 64), ("High Pass", "HPF", 64), ("Resonance", "RES", 70), ("Gap", "GAP", 32))),
)
RENDER = "md_render32"
# SRAM interne (notes/28) : comme les moteurs du Syntakt, à la place des tables d'ondes de CHORD (recopiées dans la
# charge utile, CHORD_PTRS réécrits). Le crochet de démarrage (stub.S, SRAM_RUN_AT / SRAM2_RUN_AT) recopie le début de
# la charge utile dans les deux zones. Zone 1 : tout notre code, le filtre et les petites tables (exécutés et lus à
# chaque bloc : hors du cache d'instructions de 8 Ko et de la SDRAM) ; zone 2 : l'état des pistes. Le sinus (128 Ko)
# et l'échantillon d'attaque de TrxSD (16 Ko, lu dans l'ordre) restent en SDRAM, après la place des deux zones.
(SRAM1, SRAM1_END), (SRAM2, SRAM2_END) = gs.CHORD_BANKS
SRAM1_LEN, SRAM2_LEN = SRAM1_END - SRAM1, SRAM2_END - SRAM2
SINE_OFF = (SRAM1_LEN + SRAM2_LEN + 0xff) & ~0xff     # le sinus, en SDRAM, après la place de transit des deux zones
CHORD_OFF = 0x36000                                   # tables d'ondes de CHORD (30 Ko), après les enregistrements
CHORD_LEN = sum(hi - lo for lo, hi in gs.CHORD_BANKS)
LINK = """SECTIONS
{{
  .sdram {sine:#x} : {{ *(.rodata.trx_b2_sine) *(.rodata.sd_snap) *(.rodata.ch_*) }}
  .sram {sram1:#x} : AT({code:#x}) {{ *(.text.md_render32) *(.text*) . = ALIGN(4); *(.rodata*) *(.data*) }}
  .sram2 {sram2:#x} (NOLOAD) : {{ *(.bss*) *(COMMON) }}
  /DISCARD/ : {{ *(.comment) *(.note*) *(.eh_frame*) }}
}}
"""


def lma(va, pay):
    """Adresse de transit (dans la charge utile) d'une adresse d'exécution."""
    if SRAM1 <= va < SRAM1_END:
        return pay + va - SRAM1
    if SRAM2 <= va < SRAM2_END:
        return pay + SRAM1_LEN + va - SRAM2
    return va


def chord_moved(a, pay):
    at = pay + CHORD_OFF
    for lo, hi in gs.CHORD_BANKS:
        if lo <= a < hi:
            return at + a - lo
        at += hi - lo
    raise SystemExit(f"!! {a:#x} : pas une table d'ondes de CHORD")


def compile_machines(tmp, md_syx, pay):
    """Notre C : zone 1 de SRAM (code, filtre, petites tables, transit au début de pay), zone 2 (variables), sinus
    en SDRAM. Rend (octets de pay jusqu'à la fin du sinus, symboles aux adresses d'exécution)."""
    gen = headers.write(md_syx, tmp / "gen")
    objs = []
    for src in (SRC / "bridge.c", SRC / "trx_b2.c", SRC / "trx_sd.c", SRC / "trx_ch.c", gen / "trx_b2_md.c"):
        o = tmp / (src.stem + ".o")
        gx.run([gx.CROSS + "gcc", *CFLAGS, f"-I{SRC}", f"-I{gen}", "-c", str(src), "-o", str(o)])
        objs.append(o)
    ld, elf, out = tmp / "link.ld", tmp / "md.elf", tmp / "md.bin"
    ld.write_text(LINK.format(sine=pay + SINE_OFF, sram1=SRAM1, code=pay, sram2=SRAM2))
    keep = [x for m in MACHINES for x in ("-u", m["update"])]
    gx.run([gx.CROSS + "ld", "-T", str(ld), "--gc-sections", "--no-warn-rwx-segments", "-e", RENDER, *keep,
            "-o", str(elf), *map(str, objs)])
    secs = {}
    for line in gx.run([gx.CROSS + "objdump", "-h", str(elf)]).splitlines():
        f = line.split()
        if len(f) > 4 and f[0].isdigit():
            secs[f[1]] = (int(f[3], 16), int(f[2], 16))      # adresse d'exécution, taille
    extra = set(secs) - {".sdram", ".sram", ".sram2"}
    if extra:
        raise SystemExit(f"!! sections inattendues : {sorted(extra)}")
    if secs[".sram"][1] > SRAM1_LEN or secs.get(".sram2", (0, 0))[1] > SRAM2_LEN:
        raise SystemExit(f"!! SRAM : {secs['.sram'][1]} o / {SRAM1_LEN}, {secs.get('.sram2', (0, 0))[1]} o / {SRAM2_LEN}")
    if secs[".sdram"][1] != 4 * (32768 + 4096 + 3 * 128 + 2 * 960 + 2):
        raise SystemExit("!! sinus, échantillon d'attaque et tables de TrxCH")
    undef = [l for l in gx.run([gx.CROSS + "nm", "-u", str(elf)]).splitlines() if l.strip()]
    if undef:
        raise SystemExit(f"!! symboles non résolus : {undef}")
    gx.run([gx.CROSS + "objcopy", "-O", "binary", "-R", ".sram2", str(elf), str(out)])
    blob = out.read_bytes()                                 # de pay (transit de la zone 1) à la fin du sinus
    syms = {}
    for line in gx.run([gx.CROSS + "nm", str(elf)]).splitlines():
        p_ = line.split()
        if len(p_) == 3:
            syms[p_[2]] = int(p_[0], 16)
    if len(blob) != SINE_OFF + secs[".sdram"][1] or SINE_OFF + secs[".sdram"][1] > CHORD_OFF:
        raise SystemExit(f"!! charge utile : {len(blob)} o")
    return blob, syms, dict(sram=secs[".sram"][1], sram2=secs.get(".sram2", (0, 0))[1])


def build_tweak(img, md_syx=None):
    """gm.build_tweak (sans Model-TG) pour n machines. md_syx = None : le tweak versionné (bouche-trous remplacés par
    des recettes « md »)."""
    pay = gs.PAY_ALONE
    gs.set_base(pay)
    n = len(MACHINES)
    first = 6
    nm = first + n
    top = nm - 1
    cur = img
    u32 = lambda va: struct.unpack_from(">I", cur, va - BASE)[0]
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        blob, syms, used = compile_machines(tmp, md_syx, pay)
        names_at, upd_at, rnd_at, map_at = gs.DATA, gs.DATA + 4 * nm, gs.DATA + 8 * nm, gs.DATA + 16 * nm
        firsts = [76 + 5 * i for i in range(n)]
        stubs, ssyms = gm.assemble(tmp, "det", gs.detours_asm(n, [m["image"] for m in MACHINES], firsts), gs.STUBS)
        if gs.STUBS + len(stubs) > gs.DATA:
            raise SystemExit("!! détours trop grands")

        # --- données : noms, tables update/render, machine -> enregistrement, chaînes
        strings = [m["name"] for m in MACHINES] + [k[i] for m in MACHINES for k in m["knobs"] for i in (0, 1)]
        at, addr = map_at + ((nm + 3) & ~3), {}
        for s_ in strings:
            if s_ not in addr:
                addr[s_] = at
                at += len(s_) + 1
        names = [u32(g7.NAMES + 4 * i) for i in range(6)] + [addr[m["name"]] for m in MACHINES]
        upd = [u32(g7.UPDATE_TAB + 4 * i) for i in range(6)] + [syms[m["update"]] for m in MACHINES]
        rnd = [u32(g7.RENDER_TAB + 4 * i) for i in range(6)] + [syms[RENDER]] * n
        data = bytearray()
        for t in (names, upd, rnd, range(1, nm + 1)):
            data += b"".join(g7.be32(x) for x in t)
        data += cur[gs.MAP - BASE:gs.MAP - BASE + 6] + bytes(range(6, nm)) + bytes(((nm + 3) & ~3) - nm)
        for s_ in addr:
            data += s_.encode("ascii") + b"\0"
        if gs.DATA + len(data) > gs.DESCN:
            raise SystemExit("!! données")

        # --- 5 descripteurs par machine, sur le modèle de ceux de SNARE
        new = bytearray()
        for m in MACHINES:
            for k, (long_, short, default, *rng) in enumerate(m["knobs"]):
                e = bytearray(img[g7.DESC + (g7.SNARE_DESC + k) * g7.DSTRIDE - BASE:][:g7.DSTRIDE])
                e[0x00:0x04] = g7.be32(6)
                if rng:
                    e[0x08:0x0c], e[0x0c:0x10] = g7.be32(rng[0] << 8), g7.be32(rng[1] << 8)
                e[0x10:0x14] = g7.be32(default << 8)
                e[0x2c:0x30] = g7.be32(addr[long_])
                e[0x34:0x38] = g7.be32(addr[short])
                new += e
            e = bytearray(img[g7.DESC + (g7.SNARE_DESC + 4) * g7.DSTRIDE - BASE:][:g7.DSTRIDE])
            e[0x10:0x14] = g7.be32(m["decay"] << 8)
            new += e

        # --- écritures (comme gm.build_tweak sans Model-TG)
        writes = []

        def w(va, old, new_):
            if cur[va - BASE:va - BASE + len(old)] != old:
                raise SystemExit(f"!! {va:#x} : {old.hex()} attendu, {cur[va - BASE:va - BASE + len(old)].hex()} trouvé")
            writes.append({"off": va - BASE, "old": old.hex(), "new": new_.hex()})

        def moveq(va, old, new_, reg_byte):
            w(va, bytes([reg_byte, old]), bytes([reg_byte, new_]))

        def jmp(va):
            return bytes.fromhex("4ef9") + g7.be32(va)

        writes.append(None)                     # crochet de démarrage : écrit plus bas
        red = sprites.redirect_write(gx.CAVE)
        w(BASE + red["off"], bytes.fromhex(red["old"]), bytes.fromhex(red["new"]))
        w(gx.HOOK, bytes.fromhex(gx.HOOK_OLD), jmp(gx.CAVE) + bytes.fromhex("4e71"))
        moved = {g7.DESC: gs.DESCN, g7.DESC + 8: gs.DESCN + 8, g7.DESC + 0x20: gs.DESCN + 0x20, g7.ROWS: gs.ROWSN,
                 g7.CCROWS: gs.CCROWSN, g7.NAMES: names_at, g7.UPDATE_TAB: upd_at, g7.RENDER_TAB: rnd_at,
                 gs.MAP: map_at}
        want = {g7.DESC: 34, g7.DESC + 8: 1, g7.DESC + 0x20: 2, g7.ROWS: 5, g7.CCROWS: 2, gs.MAP: 1, g7.RENDER_TAB: 1}
        for old, new_ in moved.items():
            rs = g7.refs32(cur, old)
            if len(rs) != want.get(old, 1):
                raise SystemExit(f"!! références à {old:#x} : {len(rs)}")
            for va in rs:
                w(va, g7.be32(old), g7.be32(new_))
        jumps = g7.JUMPS + g8.JUMPS8
        for va in g7.BOUNDS:
            if va in {j[0] for j in jumps}:
                continue
            b0, b1 = cur[va - BASE], cur[va - BASE + 1]
            if b0 & 0xf1 != 0x70 or b1 not in (75, 76):
                raise SystemExit(f"!! {va:#x}")
            moveq(va, b1, b1 + 5 * n, b0)
        for va, reg in ((0x400a7dba, 0x72), (0x400a7df4, 0x70), (0x4005a6a6, 0x72), (0x400147a4, 0x70),
                        (0x400148aa, 0x72), (0x400148b2, 0x70), (0x400a25e0, 0x70)):
            if cur[va - BASE] != reg or cur[va - BASE + 1] not in (5, 6):
                raise SystemExit(f"!! borne {va:#x}")
            moveq(va, cur[va - BASE + 1], top, reg)
        moveq(0x4005a572, 5, 6, 0x72)
        w(0x4005a2b8, bytes.fromhex("487800c0"), bytes.fromhex("4878") + (32 * nm).to_bytes(2, "big"))
        if nm > gs.MARKS_ROW:
            w(0x400a26a2, bytes.fromhex("7850428545f9"), jmp(ssyms["marks"]))
        else:
            moveq(0x400a26e8, cur[0x400a26e8 - BASE + 1], nm, 0x70)
        for va in (0x4001b69c, 0x400a40a6, 0x400a4fb0):
            moveq(va, 5, 1, 0x70)
        for va, old, sym in jumps:
            w(va, bytes.fromhex(old), jmp(ssyms[sym]))
        for va, old, sym in g7.CALLS:
            w(va, bytes.fromhex(old), bytes.fromhex("4eb9") + g7.be32(ssyms[sym]) + bytes.fromhex("4e71"))
        # tables d'ondes de CHORD : lues dans la charge utile, leur place en SRAM reçoit notre code (notes/28)
        ptrs = [u32(gs.CHORD_PTRS + 4 * i) for i in range(31)]
        w(gs.CHORD_PTRS, b"".join(g7.be32(x) for x in ptrs), b"".join(g7.be32(chord_moved(x, pay)) for x in ptrs))

        # --- charge utile
        parts = [
            {"dest": f"{pay:#x}", "hex": blob.hex()},
            {"dest": f"{gs.STUBS:#x}", "hex": stubs.hex()},
            {"dest": f"{gs.DATA:#x}", "hex": bytes(data).hex()},
            {"dest": f"{gs.DESCN:#x}", "cycles": [f"{g7.DESC:#x}", f"{g7.DESC + g7.NDESC * g7.DSTRIDE:#x}"]},
            {"dest": f"{gs.DESCN + g7.NDESC * g7.DSTRIDE:#x}", "hex": bytes(new).hex()},
        ]
        for lo, hi in gs.CHORD_BANKS:           # tables d'ondes de CHORD, depuis le MAIN OS de l'utilisateur
            src = next(s_ + lo - d_ for s_, e_, d_ in gs.CY_SRAM_INIT if d_ <= lo and hi <= d_ + e_ - s_)
            parts.append({"dest": f"{chord_moved(lo, pay):#x}", "cycles": [f"{src:#x}", f"{src + hi - lo:#x}"]})
        lo_, hi_ = g7.DESC - BASE, g7.DESC - BASE + g7.NDESC * g7.DSTRIDE
        final, orig = bytearray(cur[lo_:hi_]), img[lo_:hi_]
        alg = g7.ALG_DESC * g7.DSTRIDE + 0x0c
        if struct.unpack_from(">I", final, alg)[0] != (first - 1) << 8:
            raise SystemExit("!! max du paramètre Algorithm")
        struct.pack_into(">I", final, alg, top << 8)
        reloc = [[f"{gs.DESCN + k:#x}", orig[k:k + 4].hex(), final[k:k + 4].hex()]
                 for k in range(0, len(final), 4) if final[k:k + 4] != orig[k:k + 4]]
        size = (CHORD_OFF + CHORD_LEN + 3) & ~3   # jusqu'aux tables d'ondes de CHORD comprises
        segs = gs.segments(parts, size)
        at = BASE + gx.IMAGE_LEN
        if at + sum(n_ for _, n_ in segs) > gs.END_LIMIT:
            raise SystemExit(f"!! ajout de {sum(n_ for _, n_ in segs)} o : l'image dépasserait {gs.END_LIMIT:#x}")
        (tmp / "segs.inc").write_text("".join(f"\t.long\t{a:#x}, {n_ // 4}\n" for a, n_ in segs))
        stub, _ = gm.assemble(tmp, "stub", gx.SRC / "stub.S", gx.CAVE, [
            f"-DPAYLOAD_SRC={at:#x}", f"-DPAYLOAD_DST={pay:#x}", f"-DPAYLOAD_LONGS={size // 4}", "-DPACK",
            f"-DSRAM_RUN_AT={SRAM1:#x}", f"-DSRAM_LONGS={SRAM1_LEN // 4}", f"-DSRAM2_RUN_AT={SRAM2:#x}",
            f"-DSRAM2_LONGS={SRAM2_LEN // 4}", f"-I{tmp}"])
    if len(stub) > sprites.zone(gx.CAVE)[1]:
        raise SystemExit("!! crochet de démarrage trop grand pour sa place")
    writes[0] = {"off": gx.CAVE - BASE, "old": "ff" * len(stub), "new": stub.hex()}
    if cur[gx.CAVE - BASE:gx.CAVE - BASE + len(stub)] != b"\xff" * len(stub):
        raise SystemExit("!! place du crochet de démarrage déjà prise")
    writes.sort(key=lambda x: x["off"])
    for a_, b_ in zip(writes, writes[1:]):
        if a_["off"] + len(a_["new"]) // 2 > b_["off"]:
            raise SystemExit(f"!! écritures qui se chevauchent en {BASE + b_['off']:#x}")

    if md_syx is None:                          # bouche-trous -> recettes « md »
        blob_ = bytearray(blob)
        for name, (sym, cnt) in headers.ARRAYS.items():
            o = lma(syms[sym], pay) - pay
            if blob_[o:o + 4 * cnt] != struct.pack(">I", headers.PLACEHOLDER) * cnt:
                raise SystemExit(f"!! {sym} : bouche-trous introuvables")
            blob_[o:o + 4 * cnt] = bytes(4 * cnt)
            parts.append({"dest": f"{lma(syms[sym], pay):#x}", "md": name, "size": 4 * cnt})
        parts[0]["hex"] = blob_.hex()

    appended = {json.loads(f.read_text(encoding="utf-8"))["id"] for f in gm.DEV.glob("[0-9]*.json")
                if f != OUT and "append" in json.loads(f.read_text(encoding="utf-8"))}
    out = {
        "id": TID,
        "order": 26,
        "name": "Machines du Machinedrum : TrxB2, TrxSD, TrxCH (OS 1.63), à l'échantillon près",
        "description": [
            "TRX-B2 et TRX-SD du Machinedrum en 7e et 8e machines : le code du DSP A du Machinedrum porté",
            "en C, identique à l'échantillon près (comparé au DSP émulé), rendu à 44,1 kHz puis ramené à 48 kHz",
            "(filtre polyphase 160/147). PITCH = PTCH (+ note du trig), DECAY = DEC ; le reste : tools/machines/md/",
            "bridge.c. Généré par tools/gen_md_machines.py. Aucun octet Elektron : build.py --md lit le sinus et les",
            "tables dans TON OS du Machinedrum (Elektron_SPS1-1UW_OS1.63.syx).",
        ],
        "device": "Model:Cycles",
        "os": "1.13",
        "section": 3,
        "status": "experimental",
        "md": {"os": "Elektron_SPS1-1UW_OS1.63.syx", "sha256": headers.md_os.OS_SHA256},
        "conflicts": sorted((gm.other_ids() | appended | {"macro", "macro-tg", "model-tg", "model-tg-st"}) - {TID}),
        "writes": writes,
        "append": {"at": f"{at:#x}", "dest": f"{pay:#x}", "size": size, "parts": parts, "reloc": reloc,
                   "pack": [[f"{a_:#x}", n_] for a_, n_ in segs]},
        "symbols": {k: f"{syms[k]:#x}" for k in [m["update"] for m in MACHINES] + [RENDER]},
    }
    out = usb_steady.add_to(out)
    out = voice_loop.add_to(out)
    # envoi à l'USB à heure fixe : octets de référence de 6ch-usbup et des autres machines ajoutées
    # (m68k-linux-gnu-as) ; m68k-elf-as code un lea en (d16,pc) et décale feed.S de 4 octets
    ref = {w_["off"]: w_ for w_ in json.loads((gm.DEV / "25-macro.json").read_text(encoding="utf-8"))["writes"]}
    steady = {x["off"] for x in usb_steady.writes()}
    for i, w_ in enumerate(out["writes"]):
        if w_["off"] in steady:
            if ref[w_["off"]]["old"] != w_["old"] and set(ref[w_["off"]]["old"] + w_["old"]) != {"f"}:
                raise SystemExit(f"!! usb_steady : {w_['off'] + BASE:#x}")
            out["writes"][i] = ref[w_["off"]]
    return out, dict(code=len(blob), sram=used["sram"], sram2=used["sram2"], image=sum(n_ for _, n_ in segs), syms=syms)


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
    print(f"  {tweak['id']} : {len(tweak['writes'])} écritures, SRAM {info['sram']} + {info['sram2']} o "
          f"(sur {SRAM1_LEN} + {SRAM2_LEN}), sinus en SDRAM, ajout à l'image {info['image']} o")
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
