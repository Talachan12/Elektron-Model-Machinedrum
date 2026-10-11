#!/usr/bin/env python3
"""Écrit docs/md/md-data.js, les données du patcher web des machines du Machinedrum (site/) : device.json, le tweak
26-md-machines.json (recettes « md », aucun octet Elektron), l'empreinte attendue de l'OS du Machinedrum et celle du
MAIN OS patché, calculée ici avec tools/build.py sur les fichiers officiels.

    python3 tools/gen_md_web.py --cycles firmware/model-cycles_OS1.13.syx --md firmware/Elektron_SPS1-1UW_OS1.63.syx [--check]
"""
import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "machines" / "md"))

import build                  # noqa: E402
import md_os                  # noqa: E402
from mtlib import aplib, container  # noqa: E402
from mtlib.syx import unwrap  # noqa: E402

DEV = HERE.parent / "tweaks" / "model-cycles_OS1.13"
OUT = HERE.parent / "site" / "md-data.js"


def mainos_sha(cycles, md):
    tweak = json.loads((DEV / "26-md-machines.json").read_text(encoding="utf-8"))
    stream, _ = unwrap(pathlib.Path(cycles).read_bytes())
    c = container.parse(stream)
    s3 = next(s for s in c["sections"] if s["id"] == 3)
    main_os, _ = aplib.depack(c["blob"][s3["off"]:s3["off"] + s3["size"]])
    patched, _ = build.apply_writes(main_os, [tweak])
    payload, _ = build.build_payload([tweak], main_os, None, md)
    return hashlib.sha256(bytes(patched) + payload).hexdigest(), tweak


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True)
    ap.add_argument("--md", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    sha, tweak = mainos_sha(args.cycles, args.md)
    data = {"device": json.loads((DEV / "device.json").read_text(encoding="utf-8")), "tweak": tweak,
            "md_sha256": md_os.OS_SHA256, "mainos_sha256": sha}
    text = ("/* Généré par tools/gen_md_web.py : ne pas éditer à la main. Aucun octet Elektron. */\n"
            "window.MD_WEB = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    if args.check:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print(f"  {OUT.name} {'est à jour' if ok else 'NE CORRESPOND PAS'}")
        raise SystemExit(0 if ok else 1)
    OUT.write_text(text, encoding="utf-8")
    print(f"  écrit : {OUT} (MAIN OS attendu {sha[:16]}…)")


if __name__ == "__main__":
    main()
