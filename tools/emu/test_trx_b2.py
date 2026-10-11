#!/usr/bin/env python3
"""Preuve de la machine TrxB2 (tools/machines/trx_b2, tools/gen_trx_b2.py) : le TRX-B2 du Machinedrum en 7e machine.
Le vrai code de l'OS, émulé (Unicorn), avec la charge utile telle que le crochet de démarrage la reconstitue.

  1. Démarrage : le crochet (stub.S, PACK) reconstitue la charge utile, la SRAM reste intacte, retour normal.
  2. Interface : les vérifications de test_syntakt_machines.py appliquées à TrxB2 (rangées, descripteurs, écran
     MACHINES, molette, enregistrements, changement de machine, icône).
  3. Son : à chaque bloc, ce que l'OS passe à trx_b2_update (note, paramètres, trig) est relu, et la sortie de la
     piste est comparée à la référence compilée pour l'ordinateur (host_ref.c : bridge.c + trx_b2.c, dont le cœur
     est identique au DSP émulé du Machinedrum, cf. trx_b2/compare) ; les machines d'origine ne changent pas.
  4. Coût : instructions par bloc (une voix TrxB2), comparées à KICK.

    python3 tools/emu/test_trx_b2.py --cycles firmware/model-cycles_OS1.13.syx --md firmware/Elektron_SPS1-1UW_OS1.63.syx
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
sys.path.insert(0, str(HERE.parent / "machines" / "trx_b2"))

import build                        # noqa: E402
import gen_sdvintage_7th as g7      # noqa: E402
import gen_syntakt_engines as gs    # noqa: E402
import gen_trx_b2 as gt             # noqa: E402
import headers                      # noqa: E402
import mcengine as E                # noqa: E402
import test_macro as TMc            # noqa: E402
import test_syntakt_machines as tsm  # noqa: E402

DEV = HERE.parent.parent / "tweaks" / "model-cycles_OS1.13"
check = TMc.check
IDX = 6
BASE_KW = dict(note=60, pitch=64, color=0, shape=0, sweep=96, contour=64, punch=0, gate=0, finetune=64, decay=64)


class Fw(TMc.Fw):
    """md : chemin de l'OS du Machinedrum (le tweak versionné n'a que des recettes « md »)."""

    def __init__(self, stock, tweaks, md=None):
        p, _ = build.apply_writes(stock, tweaks)
        pl, _ = build.build_payload(tweaks, stock, None, md)
        self.img, self.tweaks = bytes(p) + pl, tweaks
        self.blob_end = None
        ours = [t for t in tweaks if t["id"] == "trx-b2"]
        self.payload = None
        if not ours:
            return
        ap_ = ours[0]["append"]
        self.pay = int(ap_["dest"], 16)
        self.runtime = build.payload_runtime(ours[0], stock, None, build.md_data(md))
        self.payload = (self.pay, self.runtime)
        self.nm, self.index = 7, IDX
        data = self.pay + gs.LAYOUT["DATA"]
        u32 = lambda va: struct.unpack_from(">I", self.runtime, va - self.pay)[0]
        self.upd = u32(data + 4 * self.nm + 4 * self.index)
        self.rnd = u32(data + 8 * self.nm + 4 * self.index)
        self.sym = {k: int(v, 16) for k, v in ours[0]["symbols"].items()}


def boot(fw):
    """test_macro.boot, avec notre tweak à la place de MACRO."""
    for t in fw.tweaks:
        if t["id"] == "trx-b2":
            t["id"] = "macro-as-trx-b2"         # test_macro.boot cherche le tweak par ce préfixe
    try:
        TMc.boot(fw)
    finally:
        for t in fw.tweaks:
            if t["id"] == "macro-as-trx-b2":
                t["id"] = "trx-b2"


def interface(stock, fw):
    tsm.SAFE = True
    tsm.ADDED = [dict(gt.MACHINE, code="trx-b2", index=IDX, label="TRX-B2")]
    tsm.N, tsm.NM, tsm.TOP = 1, 7, 6
    tsm.FIRST, tsm.REC = {6: 76}, {6: gs.RECS}
    tsm.ROWS, tsm.CCROWS = gs.ROWSN, gs.CCROWSN
    tsm.NAMES = ["Kick", "Snare", "Metal", "Perc", "Tone", "Chord", gt.MACHINE["name"]]
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
        src = HERE.parent / "machines" / "trx_b2"
        self.exe = tmp / "host_ref"
        (tmp / "decl.h").write_text("extern char voices[];\n")
        subprocess.run(["cc", "-O2", "-std=c99", "-Wno-pointer-to-int-cast", "-include", str(tmp / "decl.h"),
                        f"-I{src}", f"-I{gen}", "-DCYC_VOICE0=((u32)(unsigned long)voices)",
                        str(src / "bridge.c"), str(src / "trx_b2.c"), str(gen / "trx_b2_md.c"),
                        str(src / "host_ref.c"), "-o", str(self.exe)], check=True)

    def run(self, recs):
        lines = "".join(" ".join(str(x) for x in r) + "\n" for r in recs)
        out = subprocess.run([str(self.exe)], input=lines.encode(), capture_output=True, check=True).stdout
        return np.frombuffer(out, dtype="<i4").reshape(-1, 32).astype(np.int64)


def play(fw, kw, blocks, trigs=(1,), changes=None, track=0, count=False):
    """Une piste sur TrxB2 : (sortie de la piste, sortie de notre render à son retour, entrées de trx_b2_update,
    accès hors mémoire, instructions par bloc). Après la machine, l'OS applique l'étage de piste (volume) : on
    compare donc, comme test_macro.py, ce que sort notre code."""
    e = fw.engine(solo=track)
    e.set(track, machine=IDX, **kw)
    recs, direct, v, cap = [], [], E.VOICE0 + track * E.VSTRIDE, {}
    uc = e.uc

    def upd(uc_, a, s, u):
        sp = uc.reg_read(mk.UC_M68K_REG_A7)
        pmod, vv, pp = struct.unpack(">iII", uc.mem_read(sp + 4, 12))
        if vv != v:
            return
        w = lambda o: struct.unpack(">h", uc.mem_read(pp + o, 2))[0]
        trig = struct.unpack(">i", uc.mem_read(v + 0x38, 4))[0]
        recs.append([1 if trig else 0, w(0x14), w(0x16), w(0x18), w(0x1a), w(0x1c), w(0x1e), w(0x24), pmod >> 16])

    def rnd(uc_, a, s, u):
        sp = uc.reg_read(mk.UC_M68K_REG_A7)
        ret, out, vv = struct.unpack(">III", uc.mem_read(sp, 12))
        if vv == v:
            cap["ret"], cap["out"] = ret, out

    def back(uc_, a, s, u):
        if a == cap.get("ret"):
            direct.append(np.frombuffer(bytes(uc.mem_read(cap.pop("out"), 128)), ">i4").astype(np.int64))
            cap.pop("ret")
    uc.hook_add(UC_HOOK_CODE, upd, begin=fw.upd, end=fw.upd)
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


def cases():
    out = [("défauts", BASE_KW, (1, 120), None, 200)]
    for k, vals in (("color", (0, 60, 127)), ("shape", (30, 90, 127)), ("sweep", (0, 127)), ("contour", (0, 127)),
                    ("decay", (0, 30, 127)), ("pitch", (0, 127)), ("punch", (1,))):
        for val in vals:
            out.append((f"{k.upper()} {val}", dict(BASE_KW, **{k: val}), (1, 90), None, 150))
    out += [
        ("notes du clavier", dict(BASE_KW, note=48), (1, 40, 80), {40: {"note": 72}, 80: {"note": 0}}, 120),
        ("potards qui bougent à chaque bloc", dict(BASE_KW, decay=100), (1,),
         {b: {"color": (3 * b) % 128, "shape": (7 * b) % 128, "sweep": 127 - (5 * b) % 128} for b in range(100)}, 100),
        ("trigs rapprochés", dict(BASE_KW, punch=1), tuple(range(1, 100, 3)), None, 110),
        ("LFO hors bornes (potards < 0, PITCH + note > 127)", dict(BASE_KW, color=-20, sweep=-3, shape=127.9, pitch=120, note=90), (1,), None, 60),
    ]
    return out


def sound(fw, ref):
    bad, peaks, n = [], [], 0
    for name, kw, trigs, changes, blocks in cases():
        _, out, recs, unm, _ = play(fw, kw, blocks, trigs, changes)
        want = ref.run(recs)
        n += 1
        # la machine ne change qu'au bloc qui suit le 1er trig (notes/43 §2) : avant, la piste joue encore KICK
        skip = blocks - len(recs)
        peaks.append(int(np.abs(out).max()))
        if skip != 2 or len(out) != len(recs) or not np.array_equal(want, out) or unm or peaks[-1] < 1 << 24:
            first = next((i for i in range(min(len(want), len(out))) if not np.array_equal(want[i], out[i])), None)
            bad.append(name)
            print(f"        ECART {name} : {len(recs)} appels / {blocks} blocs (attendu {blocks - 2}), 1er bloc différent {first}, "
                  f"crête {peaks[-1]:.3g}, hors mémoire {unm[:2]}")
    check(not bad, f"sortie de TrxB2 (au retour de son render) identique échantillon par échantillon à la référence (pont + cœur TRX-B2 "
                   f"compilés pour l'ordinateur) : {n} cas, crêtes {min(peaks):.2g} à {max(peaks):.2g} sur 2^31 {bad}")


def stock_unchanged(stock, fw):
    """6 pistes sur les machines d'origine : identiques à l'OS d'origine, et aucun appel de notre code."""
    def run(f, hook):
        e = f.engine()
        for t in range(6):
            e.set(t, **dict(BASE_KW, machine=t, color=64, shape=64, contour=64, decay=60))
        ran = []
        if hook:
            e.uc.hook_add(UC_HOOK_CODE, lambda *a: ran.append(1), begin=f.upd, end=f.upd)
        out = [e.block(0x3f if b in (1, 50) else 0) for b in range(100)]
        return np.stack(out), ran
    a, _ = run(Fw(stock, []), False)
    b, ran = run(fw, True)
    check(np.array_equal(a, b) and not ran, "6 pistes sur les machines d'origine : identiques à l'OS d'origine, "
                                            "TrxB2 jamais appelée")


def cost(fw):
    track, _, _, _, n = play(fw, BASE_KW, 60, (1,), count=True)
    e = fw.engine(solo=0)
    e.set(0, **dict(BASE_KW, machine=0, color=10, shape=16, sweep=16, contour=24, decay=28))
    e.count_instructions()
    k0, kick = [], []
    for b in range(60):
        k0.append(e.instructions)
        kick.append(e.block(1 if b == 1 else 0)[0])
    nk = np.diff(k0 + [e.instructions])
    print(f"    coût par bloc (instructions de toute la boucle des voix, une piste) : TrxB2 {int(np.median(n[3:]))} "
          f"(max {int(n[3:].max())}), KICK {int(np.median(nk[3:]))} ; budget ~166 000 cycles par bloc à 250 MHz")
    print(f"    crête de la piste (après l'étage de piste de l'OS) : TrxB2 défauts {np.abs(track).max() / 2**31:.2f}, "
          f"KICK défauts {np.abs(np.stack(kick)).max() / 2**31:.2f} (pleine échelle = 1)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True)
    ap.add_argument("--md", required=True)
    args = ap.parse_args()
    stock = g7.cycles_main(args.cycles)
    tw = json.loads((DEV / "26-trx-b2.json").read_text(encoding="utf-8"))
    fw = Fw(stock, [tw], args.md)
    print("1. démarrage"); boot(fw)
    print("2. interface"); interface(stock, fw)
    with tempfile.TemporaryDirectory() as d:
        ref = HostRef(pathlib.Path(d), pathlib.Path(args.md).resolve())
        print("3. son"); sound(fw, ref); stock_unchanged(stock, fw)
    print("4. coût"); cost(fw)
    fails = TMc.t7.FAIL if hasattr(TMc.t7, "FAIL") else []
    print("ÉCHECS :" if fails else "tout est bon", fails or "")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
