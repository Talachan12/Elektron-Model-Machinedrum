#!/usr/bin/env python3
"""Preuve des machines du Machinedrum ajoutées au Model:Cycles (tools/machines/md, tools/gen_md_machines.py) :
TrxB2, EfmBD, EfmSD en 7e, 8e et 9e machines. Le vrai code de l'OS, émulé (Unicorn), avec la charge utile telle
que le crochet de démarrage la reconstitue.

  1. Démarrage : le crochet (stub.S, PACK) reconstitue la charge utile, la SRAM reste intacte, retour normal.
  2. Interface : les vérifications de test_syntakt_machines.py appliquées aux 3 machines (rangées, descripteurs,
     écran MACHINES, molette, enregistrements, changement de machine, icône).
  3. Son : à chaque bloc, ce que l'OS passe à l'update de la machine (note, paramètres, trig) est relu, et ce que
     sort notre render est comparé à la référence compilée pour l'ordinateur (host_ref.c : bridge.c + trx_b2.c +
     efm.c, dont les cœurs sont identiques au DSP émulé du Machinedrum) ; changement de machine sur une piste ;
     les machines d'origine ne changent pas.
  4. Coût : instructions par bloc (une voix de chaque machine), comparées à KICK.

    python3 tools/emu/test_md_machines.py --cycles firmware/model-cycles_OS1.13.syx \\
        --md firmware/Elektron_SPS1-1UW_OS1.63.syx

Durée : environ 10 min.
"""
import argparse
import json
import pathlib
import struct
import subprocess
import sys
import tempfile

import numpy as np
from unicorn import UC_HOOK_CODE
from unicorn import m68k_const as mk

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "machines" / "md"))

import build                        # noqa: E402
import gen_sdvintage_7th as g7      # noqa: E402
import gen_syntakt_engines as gs    # noqa: E402
import gen_md_machines as gt        # noqa: E402
import headers                      # noqa: E402
import mcengine as E                # noqa: E402
import test_macro as TMc            # noqa: E402
import test_syntakt_machines as tsm  # noqa: E402

DEV = HERE.parent.parent / "tweaks" / "model-cycles_OS1.13"
check = TMc.check
FIRST = 6                           # TrxB2 ; EfmBD 7, EfmSD 8
NAMES = [m["name"] for m in gt.MACHINES]
BASE_KW = dict(note=60, pitch=64, color=0, shape=0, sweep=96, contour=64, punch=0, gate=0, finetune=64, decay=64)


class Fw(TMc.Fw):
    """md : chemin de l'OS du Machinedrum (le tweak versionné n'a que des recettes « md »)."""

    def __init__(self, stock, tweaks, md=None):
        p, _ = build.apply_writes(stock, tweaks)
        pl, _ = build.build_payload(tweaks, stock, None, md)
        self.img, self.tweaks = bytes(p) + pl, tweaks
        self.blob_end = None
        ours = [t for t in tweaks if t["id"] == gt.TID]
        self.payload = None
        if not ours:
            return
        ap_ = ours[0]["append"]
        self.pay = int(ap_["dest"], 16)
        self.runtime = build.payload_runtime(ours[0], stock, None, build.md_data(md))
        self.payload = (self.pay, self.runtime)
        self.nm = FIRST + len(NAMES)
        data = self.pay + gs.LAYOUT["DATA"]
        u32 = lambda va: struct.unpack_from(">I", self.runtime, va - self.pay)[0]
        self.upds = [u32(data + 4 * self.nm + 4 * (FIRST + i)) for i in range(len(NAMES))]
        self.rnds = [u32(data + 8 * self.nm + 4 * (FIRST + i)) for i in range(len(NAMES))]
        self.upd, self.rnd = self.upds[0], self.rnds[0]
        self.sym = {k: int(v, 16) for k, v in ours[0]["symbols"].items()}


def boot(fw):
    """Le crochet de démarrage, exécuté pour de vrai au début de la remise à zéro du BSS (0x400004b2) : charge utile
    reconstituée (morceaux, zéros), puis ses deux zones de transit recopiées en SRAM à la place des tables d'ondes de
    CHORD (le reste de la SRAM intact), et celles-ci lues par l'OS à leur nouvelle place."""
    from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_MEM_UNMAPPED
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(mk.UC_CPU_M68K_ANY)
    uc.mem_map(0x40000000, 0x02400000)
    uc.mem_write(E.BASE, fw.img)
    dst, rt = fw.payload
    uc.mem_map(dst, 0x00100000)
    uc.mem_write(dst, b"\xa5" * 0x00100000)
    uc.mem_map(0x80000000, 0x00010000)
    sram = bytearray(0x10000)
    for lo, hi, d in gs.CY_SRAM_INIT:
        sram[d - 0x80000000:d - 0x80000000 + hi - lo] = fw.img[lo - E.BASE:hi - E.BASE]
    uc.mem_write(0x80000000, bytes(sram))
    uc.mem_map(0x90000000, 0x00020000)
    uc.mem_write(E.STOP, b"\x4e\x71\x4e\x71")
    bad = []
    uc.hook_add(UC_HOOK_MEM_UNMAPPED, lambda u, a, addr, s_, v, d: bad.append(addr) or False)
    keep = {r: 0x11110000 + i for i, r in enumerate((mk.UC_M68K_REG_D2, mk.UC_M68K_REG_D3, mk.UC_M68K_REG_D4,
                                                     mk.UC_M68K_REG_D5, mk.UC_M68K_REG_D6, mk.UC_M68K_REG_D7,
                                                     mk.UC_M68K_REG_A2, mk.UC_M68K_REG_A3, mk.UC_M68K_REG_A4,
                                                     mk.UC_M68K_REG_A5, mk.UC_M68K_REG_A6))}
    for r, v in keep.items():
        uc.reg_write(r, v)
    sp0 = 0x90010000
    uc.mem_write(sp0, struct.pack(">I", E.STOP))
    uc.reg_write(mk.UC_M68K_REG_A7, sp0)
    uc.emu_start(0x400004b2, E.STOP, count=100_000_000)
    regs = all(uc.reg_read(r) == v for r, v in keep.items())
    check(uc.reg_read(mk.UC_M68K_REG_PC) == E.STOP and uc.reg_read(mk.UC_M68K_REG_A7) == sp0 + 4 and regs
          and not bad, "0x400004b2 -> notre crochet -> remise à zéro du BSS de l'OS, retour normal, d2..d7/a2..a6 "
                       "intacts, aucun accès hors mémoire")
    check(bytes(uc.mem_read(dst, len(rt))) == rt, f"charge utile reconstituée à {dst:#x} : {len(rt)} o")
    want = bytearray(sram)
    (b1, e1), (b2, e2) = gs.CHORD_BANKS
    want[b1 - 0x80000000:e1 - 0x80000000] = rt[:e1 - b1]
    want[b2 - 0x80000000:e2 - 0x80000000] = rt[e1 - b1:e1 - b1 + e2 - b2]
    check(bytes(uc.mem_read(0x80000000, 0x10000)) == bytes(want),
          "SRAM : nos deux zones à la place des tables d'ondes de CHORD, le reste intact")
    ptrs = [struct.unpack_from(">I", fw.img, gs.CHORD_PTRS + 4 * i - E.BASE)[0] for i in range(31)]
    stock_ptrs = [struct.unpack_from(">I", fw_stock_img, gs.CHORD_PTRS + 4 * i - E.BASE)[0] for i in range(31)]
    same = all(dst <= p < dst + len(rt) and rt[p - dst:p - dst + 0x404] == bytes(sram[o - 0x80000000:o - 0x80000000 + 0x404])
               for p, o in zip(ptrs, stock_ptrs))
    check(same, "tables d'ondes de CHORD : les 31 pointeurs visent leur copie dans la charge utile, identique à leur "
                "contenu d'origine en SRAM")
    end = E.BASE + len(fw.img)
    check(end <= gs.END_LIMIT, f"image décompressée jusqu'à {end:#x} (limite {gs.END_LIMIT:#x})")


def interface(stock, fw):
    tsm.SAFE = True
    n = len(NAMES)
    tsm.ADDED = [dict(m, code=m["name"].lower(), index=FIRST + i, label=m["name"]) for i, m in enumerate(gt.MACHINES)]
    tsm.N, tsm.NM, tsm.TOP = n, FIRST + n, FIRST + n - 1
    tsm.FIRST = {FIRST + i: 76 + 5 * i for i in range(n)}
    tsm.REC = {FIRST + i: gs.RECS + 0x60 * i for i in range(n)}
    tsm.ROWS, tsm.CCROWS = gs.ROWSN, gs.CCROWSN
    tsm.NAMES = ["Kick", "Snare", "Metal", "Perc", "Tone", "Chord"] + NAMES
    a, b = tsm.tables(stock, fw.img, fw.runtime)
    tsm.lookups(a, b)
    tsm.accessors(a, b, stock, fw.img)
    tsm.screens(stock, fw.img, fw.runtime)
    tsm.setter_and_wheel(stock, fw.img, fw.runtime)
    tsm.records_and_change(stock, fw.img, fw.runtime)
    tsm.out_of_range(stock, fw.img, fw.runtime)
    tsm.small_icon(stock, fw.img, fw.runtime)


class HostRef:
    def __init__(self, tmp, md):
        gen = headers.write(md, tmp / "gen")
        src = HERE.parent / "machines" / "md"
        self.exe = tmp / "host_ref"
        (tmp / "decl.h").write_text("extern char voices[];\n")
        subprocess.run(["cc", "-O2", "-std=c99", "-Wno-pointer-to-int-cast", "-include", str(tmp / "decl.h"),
                        f"-I{src}", f"-I{gen}", "-DCYC_VOICE0=((u32)(unsigned long)voices)",
                        str(src / "bridge.c"), str(src / "trx_b2.c"), str(src / "efm.c"), str(gen / "trx_b2_md.c"),
                        str(src / "host_ref.c"), "-o", str(self.exe)], check=True)

    def run(self, recs):
        lines = "".join(" ".join(str(x) for x in r) + "\n" for r in recs)
        out = subprocess.run([str(self.exe)], input=lines.encode(), capture_output=True, check=True).stdout
        return np.frombuffer(out, dtype="<i4").reshape(-1, 32).astype(np.int64)


def play(fw, kw, blocks, trigs=(1,), changes=None, track=0, count=False, m=0):
    """Une piste sur la machine FIRST + m : (sortie de la piste, sortie de notre render à son retour, entrées de l'update,
    accès hors mémoire, instructions par bloc). Après la machine, l'OS applique l'étage de piste (volume) : on
    compare donc, comme test_macro.py, ce que sort notre code."""
    e = fw.engine(solo=track)
    e.set(track, machine=FIRST + m, **kw)
    recs, direct, v, cap = [], [], E.VOICE0 + track * E.VSTRIDE, {}
    uc = e.uc

    def upd(uc_, a, s, u):
        mi = fw.upds.index(a)
        sp = uc.reg_read(mk.UC_M68K_REG_A7)
        pmod, vv, pp = struct.unpack(">iII", uc.mem_read(sp + 4, 12))
        if vv != v:
            return
        w = lambda o: struct.unpack(">h", uc.mem_read(pp + o, 2))[0]
        trig = struct.unpack(">i", uc.mem_read(v + 0x38, 4))[0]
        recs.append([mi, 1 if trig else 0, w(0x14), w(0x16), w(0x18), w(0x1a), w(0x1c), w(0x1e), w(0x24), pmod >> 16])

    def rnd(uc_, a, s, u):
        sp = uc.reg_read(mk.UC_M68K_REG_A7)
        ret, out, vv = struct.unpack(">III", uc.mem_read(sp, 12))
        if vv == v:
            cap["ret"], cap["out"] = ret, out

    def back(uc_, a, s, u):
        if a == cap.get("ret"):
            direct.append(np.frombuffer(bytes(uc.mem_read(cap.pop("out"), 128)), ">i4").astype(np.int64))
            cap.pop("ret")
    for a_ in fw.upds:
        uc.hook_add(UC_HOOK_CODE, upd, begin=a_, end=a_)
    uc.hook_add(UC_HOOK_CODE, rnd, begin=fw.rnd, end=fw.rnd)
    uc.hook_add(UC_HOOK_CODE, back, begin=E.BASE, end=0x40200000)
    if count:
        e.count_instructions()
    out, n0 = [], []
    for b in range(blocks):
        for k, val in (changes or {}).get(b, {}).items():
            e.set(track, **{k: val})
        if count:
            n0.append(e.instructions)
        out.append(e.block(1 << track if b in trigs else 0)[track])
    return np.stack(out), np.array(direct).reshape(-1, 32), recs, e.unmapped, \
        (np.diff(n0 + [e.instructions]) if count else None)


def cases(m):
    out = [("défauts", BASE_KW, (1, 120), None, 200)]
    for k, vals in (("color", (0, 127)), ("shape", (0, 127)), ("sweep", (0, 127)), ("contour", (0, 127)),
                    ("decay", (0, 127)), ("pitch", (0, 127)), ("punch", (1,))):
        for val in vals:
            out.append((f"{k.upper()} {val}", dict(BASE_KW, **{k: val}), (1, 90), None, 130))
    out += [
        ("notes du clavier", dict(BASE_KW, note=48), (1, 40, 80), {40: {"note": 72}, 80: {"note": 0}}, 120),
        ("potards qui bougent à chaque bloc", dict(BASE_KW, decay=100), (1,),
         {b: {"color": (3 * b) % 128, "shape": (7 * b) % 128, "sweep": 127 - (5 * b) % 128} for b in range(100)}, 100),
        ("trigs rapprochés", dict(BASE_KW, punch=1), tuple(range(1, 100, 3)), None, 110),
        ("LFO hors bornes (potards < 0, PITCH + note > 127)", dict(BASE_KW, color=-20, sweep=-3, shape=127.9, pitch=120, note=90), (1,), None, 60),
    ]
    if m == 0:
        nxt = 1
    else:
        nxt = 0 if m == 2 else 2
    out.append((f"changement de machine -> {NAMES[nxt]}", BASE_KW, (1, 50), {50: {"machine": FIRST + nxt}}, 100))
    return out


def sound(fw, ref):
    for m, name_m in enumerate(NAMES):
        bad, peaks, n = [], [], 0
        for name, kw, trigs, changes, blocks in cases(m):
            _, out, recs, unm, _ = play(fw, kw, blocks, trigs, changes, m=m)
            want = ref.run(recs)
            n += 1
            # la machine ne change qu'au bloc qui suit le 1er trig (notes/43 §2) : avant, la piste joue encore KICK
            skip = blocks - len(recs)
            peaks.append(int(np.abs(out).max()))
            if skip != 2 or len(out) != len(recs) or not np.array_equal(want, out) or unm or peaks[-1] < 1 << 24:
                first = next((i for i in range(min(len(want), len(out))) if not np.array_equal(want[i], out[i])), None)
                bad.append(name)
                print(f"        ECART {name_m} {name} : {len(recs)} appels / {blocks} blocs (attendu {blocks - 2}), "
                      f"1er bloc différent {first}, crête {peaks[-1]:.3g}, hors mémoire {unm[:2]}")
        check(not bad, f"{name_m} : sortie (au retour de son render) identique échantillon par échantillon à la "
                       f"référence compilée pour l'ordinateur : {n} cas, crêtes {min(peaks):.2g} à {max(peaks):.2g} "
                       f"sur 2^31 {bad}")


def stock_unchanged(stock, fw):
    """6 pistes sur les machines d'origine : identiques à l'OS d'origine, et aucun appel de notre code."""
    def run(f, hook):
        e = f.engine()
        for t in range(6):
            e.set(t, **dict(BASE_KW, machine=t, color=64, shape=64, contour=64, decay=60))
        ran = []
        if hook:
            for a_ in f.upds:
                e.uc.hook_add(UC_HOOK_CODE, lambda *a: ran.append(1), begin=a_, end=a_)
        out = [e.block(0x3f if b in (1, 50) else 0) for b in range(100)]
        return np.stack(out), ran
    a, _ = run(Fw(stock, []), False)
    b, ran = run(fw, True)
    check(np.array_equal(a, b) and not ran, "6 pistes sur les machines d'origine : identiques à l'OS d'origine, "
                                            "nos machines jamais appelées")


def mixed(fw):
    """5 pistes d'origine + une de nos machines sur la 6e : les 5 pistes d'origine sortent exactement comme sans elle
    (notre code n'abîme ni l'EMAC ni rien d'autre de la boucle des voix)."""
    def run(m6):
        e = fw.engine()
        for t in range(5):
            e.set(t, **dict(BASE_KW, machine=t, color=64, shape=64, contour=64, decay=60))
        e.set(5, **dict(BASE_KW, machine=m6, decay=100))
        return np.stack([e.block(0x3f if b in (1, 30, 61) else 0) for b in range(90)])
    ref = run(TMc.OFF)
    bad = [NAMES[m] for m in range(len(NAMES)) if not np.array_equal(run(FIRST + m)[:, :5], ref[:, :5])]
    check(not bad and ref[:, :5].any(), f"5 pistes d'origine jouées avec chacune de nos machines sur la 6e : "
                                        f"identiques à l'échantillon près {bad}")


def cost(fw):
    e = fw.engine(solo=0)
    e.set(0, **dict(BASE_KW, machine=0, color=10, shape=16, sweep=16, contour=24, decay=28))
    e.count_instructions()
    k0, kick = [], []
    for b in range(60):
        k0.append(e.instructions)
        kick.append(e.block(1 if b == 1 else 0)[0])
    nk = np.diff(k0 + [e.instructions])
    print(f"    KICK : {int(np.median(nk[3:]))} instructions par bloc (toute la boucle des voix, une piste), crête "
          f"{np.abs(np.stack(kick)).max() / 2**31:.2f} ; budget ~166 000 cycles par bloc à 250 MHz")
    for m, name_m in enumerate(NAMES):
        track, _, _, _, n = play(fw, BASE_KW, 60, (1,), count=True, m=m)
        print(f"    {name_m} : {int(np.median(n[3:]))} (max {int(n[3:].max())}), crête après l'étage de piste "
              f"{np.abs(track).max() / 2**31:.2f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True)
    ap.add_argument("--md", required=True)
    args = ap.parse_args()
    stock = g7.cycles_main(args.cycles)
    tw = json.loads((DEV / "26-md-machines.json").read_text(encoding="utf-8"))
    global fw_stock_img
    fw_stock_img = stock
    fw = Fw(stock, [tw], args.md)
    print("1. démarrage"); boot(fw)
    print("2. interface"); interface(stock, fw)
    with tempfile.TemporaryDirectory() as d:
        ref = HostRef(pathlib.Path(d), pathlib.Path(args.md).resolve())
        print("3. son"); sound(fw, ref); stock_unchanged(stock, fw); mixed(fw)
    print("4. coût"); cost(fw)
    fails = TMc.t7.FAIL if hasattr(TMc.t7, "FAIL") else []
    print("ÉCHECS :" if fails else "tout est bon", fails or "")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
