#!/usr/bin/env python3
"""Construit un firmware Model:Cycles modifié à partir de TA propre copie de l'OS officiel.

Aucune image firmware Elektron n'est distribuée ici. Ce script applique des tables
de patchs (octets) listées dans tweaks/<device>_OS<ver>/*.json à la section 3 (MAIN OS)
de ton .syx, puis reconstruit et re-signe le conteneur (checksums + HMAC-SHA256).

    python3 tools/build.py --list
    python3 tools/build.py -i model-cycles_OS1.13.syx --all
    python3 tools/build.py -i model-cycles_OS1.13.syx -t 6ch-multiout
    python3 tools/build.py -i model-cycles_OS1.13.syx -t 6ch-multiout --expect-mainos 65e24b50...

Sécurité : chaque octet « old » est vérifié avant écriture ; le SHA-256 de la section 3
d'origine est vérifié ; après build, tous les checksums et le HMAC sont recontrôlés.
Deux tweaks déclarés incompatibles (champ « conflicts ») sont refusés ensemble. Un tweak
qui écrit dans une zone 0xFF (cave) est refusé si l'image d'origine pointe dans cette zone,
sauf si cette référence est elle-même réécrite par un des tweaks choisis.
Seule la section 3 est touchée : bootloader et updater sont conservés à l'identique,
donc la récupération par le STARTUP MENU (MIDI IN) reste disponible.

Le moteur bas niveau (mtlib) vient de drumkilla/elektron-model-tweaks (MIT) ; voir tools/mtlib/LICENSE.
"""
import argparse
import array
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from mtlib import aplib, container            # noqa: E402
from mtlib.syx import unwrap, wrap, BYTES_PER_MSG  # noqa: E402

TWEAKS = ROOT / "tweaks"
BASE = 0x40000400                             # VA du premier octet de la section 3 (MAIN OS)


def sha(b):
    return hashlib.sha256(b).hexdigest()


HEX = re.compile(r"(?:[0-9a-fA-F]{2})*")


def unhex(s):
    """bytes.fromhex, mais sans espace (deux chiffres par octet), comme fromHex de docs/flasher/builder.js."""
    if not isinstance(s, str) or not HEX.fullmatch(s):
        raise SystemExit(f"!! hexadecimal invalide : {str(s)[:24]}")
    return bytes.fromhex(s)


def load_catalog():
    """{ 'model-cycles_OS1.13': (device_dict, {id: tweak_dict}) }"""
    cat = {}
    for d in sorted(TWEAKS.glob("*_OS*")):
        dev = json.loads((d / "device.json").read_text(encoding="utf-8"))
        tweaks = {}
        for f in sorted(d.glob("[0-9]*.json")):
            t = json.loads(f.read_text(encoding="utf-8"))
            tweaks[t["id"]] = t
        cat[d.name] = (dev, tweaks)
    return cat


def pick_target(cat, syx_sha):
    for name, (dev, tweaks) in cat.items():
        if dev["stock_syx_sha256"] == syx_sha:
            return name, dev, tweaks
    return None, None, None


def cmd_list(cat):
    for name, (dev, tweaks) in cat.items():
        print(f"{dev['device']} OS {dev['os']}  ({name})")
        for t in tweaks.values():
            excl = f"  (incompatible avec : {', '.join(t['conflicts'])})" if t.get("conflicts") else ""
            print(f"  {t['id']:16} {t['name']}{excl}")


def check_conflicts(chosen):
    ids = {t["id"] for t in chosen}
    for t in chosen:
        for other in t.get("conflicts", []):
            if other in ids:
                raise SystemExit(f"!! {t['id']} et {other} sont incompatibles (ils modifient les memes octets) : "
                                 "choisis l'un ou l'autre avec -t")
        for need in t.get("requires", []):               # s'applique par-dessus un autre tweak (notes/31)
            if need not in ids:
                raise SystemExit(f"!! {t['id']} demande aussi {need} (-t {need},{t['id']})")


def cave_zones(main_os, chosen):
    """Zones 0xFF de l'image d'origine ou un tweak ecrit (caves) : [(lo, hi)] en offsets.
    lo recule jusqu'au debut du bloc 0xFF (un objet qui commencerait avant l'ecriture
    serait touche) ; hi s'arrete a la fin des octets ecrits (un objet qui commence
    apres n'est pas touche, meme si ses premiers octets valent 0xFF)."""
    zones = {}                                  # debut du bloc -> fin ecrite la plus haute
    for t in chosen:
        for w in t["writes"]:
            old = bytes.fromhex(w["old"])
            if len(old) < 2 or old.count(0xFF) != len(old):
                continue
            lo, hi = w["off"], w["off"] + len(old)
            while lo > 0 and main_os[lo - 1] == 0xFF:
                lo -= 1
            zones[lo] = max(hi, zones.get(lo, hi))
    return sorted(zones.items())


def refs_into(main_os, zones):
    """References, dans le MAIN OS d'ORIGINE, vers les zones [(lo, hi)] (offsets).
    Renvoie (sures, douteuses) : [(va de la reference, va visee, nature)].
    Sures : constantes 32 bits (pointeurs, jmp/jsr abs.l, lea/move #imm).
    Douteuses : adressages (d16,PC) de lea/pea/jmp/jsr/move et branchements Bcc/BRA/BSR,
    qu'une donnee peut imiter."""
    w = array.array("H", main_os[:len(main_os) & ~1])
    if sys.byteorder == "little":
        w.byteswap()
    vz = [(lo + BASE, hi + BASE) for lo, hi in zones]
    lo_all, hi_all = min(a for a, _ in vz), max(b for _, b in vz)

    def inside(t):
        return lo_all <= t < hi_all and any(a <= t < b for a, b in vz)

    def s16(x):
        return x - 0x10000 if x & 0x8000 else x

    sure, doubt = [], []
    n = len(w)
    for i in range(n - 1):
        x, va = w[i], BASE + 2 * i
        v = (x << 16) | w[i + 1]
        if inside(v):
            sure.append((va, v, "constante 32 bits"))
        t = None
        if (x & 0x3F) == 0x3A and ((x & 0xF1FF) == 0x41FA or x in (0x487A, 0x4EFA, 0x4EBA)
                                    or ((x & 0xC000) == 0 and (x & 0x3000))):
            t, kind = va + 2 + s16(w[i + 1]), "adressage (d16,PC)"
        elif (x & 0xF000) == 0x6000:
            d8 = x & 0xFF
            if d8 == 0:
                t = va + 2 + s16(w[i + 1])
            elif d8 == 0xFF:
                t = va + 2 + ((((w[i + 1] << 16) | (w[i + 2] if i + 2 < n else 0)) ^ 0x80000000) - 0x80000000)
            else:
                t = va + 2 + (d8 - 0x100 if d8 & 0x80 else d8)
            kind = "branchement"
        if t is not None and inside(t):
            doubt.append((va, t, kind))
    return sure, doubt


def known_ref(known, chosen, zones, hit):
    """Entree de device.json « cave_refs_ok » qui couvre cette reference, ou None.
    Une reference connue ne bloque plus si TOUTES les ecritures des tweaks choisis qui touchent sa
    zone restent dans la partie verifiee a la main [lo, hi) (ex. : entrees jamais lues d'une table)."""
    va, tgt, _ = hit
    zlo, zhi = next((lo, hi) for lo, hi in zones if lo + BASE <= tgt < hi + BASE)
    for k in known or ():
        if int(k["ref"], 16) != va:
            continue
        lo, hi = int(k["lo"], 16) - BASE, int(k["hi"], 16) - BASE
        spans = [(w["off"], w["off"] + len(bytes.fromhex(w["old"]))) for t in chosen for w in t["writes"]]
        if all(lo <= a and b <= hi for a, b in spans if a < zhi and b > zlo):
            return k
    return None


def check_caves(main_os, chosen, force, dirty=None, patched=None, known=None):
    """Refuse d'ecrire dans une zone 0xFF que l'image d'origine reference : elle ne serait pas libre.
    Une reference dont les octets sont eux-memes reecrits par les tweaks choisis (dirty) n'existe
    plus dans l'image patchee (patched) : elle est listee a part et ne bloque pas (ex. : pointeur de
    sprite redirige vers un autre masque identique pour liberer le sien, notes/14). Une constante
    reecrite qui pointe encore dans la zone reste bloquante. Une reference verifiee a la main
    (known = device.json « cave_refs_ok ») ne bloque pas tant que les ecritures restent dans sa partie libre."""
    zones = cave_zones(main_os, chosen)
    if not zones:
        return
    for lo, hi in zones:
        print(f"  zone 0xFF utilisee : 0x{lo + BASE:08x}..0x{hi + BASE - 1:08x} ({hi - lo} o)")
    sure, doubt = refs_into(main_os, zones)
    if dirty is not None:
        def rewritten(hit):
            o = hit[0] - BASE
            if not any(dirty[o:o + 4]):
                return False
            if patched is not None and hit[2].startswith("constante"):
                v = int.from_bytes(patched[o:o + 4], "big")
                if any(lo + BASE <= v < hi + BASE for lo, hi in zones):
                    return False                    # toujours une reference vers la zone
            return True
        gone = [h for h in sure + doubt if rewritten(h)]
        sure = [h for h in sure if not rewritten(h)]
        doubt = [h for h in doubt if not rewritten(h)]
        for va, t, kind in gone:
            print(f"  reference reecrite par un tweak (neutralisee) : 0x{va:08x} -> 0x{t:08x} ({kind})")
    if known:
        acked = [(h, known_ref(known, chosen, zones, h)) for h in sure]
        for (va, t, _), k in acked:
            if k:
                print(f"  reference connue, ecritures dans sa partie libre : 0x{va:08x} -> 0x{t:08x} ({k['why']})")
        sure = [h for h, k in acked if not k]
    starts = {lo + BASE for lo, _ in zones}

    def show(hits):
        for va, t, kind in hits:
            z = max(s for s in starts if s <= t)
            note = " (1er octet de la zone : peut aussi etre la fin de l'objet precedent)" if t == z else ""
            print(f"     0x{va:08x} : {kind} -> 0x{t:08x} (zone +0x{t - z:x}){note}")

    if doubt:
        print("  a verifier au desassembleur (peut-etre des donnees qui ressemblent a du code) :")
        show(doubt)
    if not sure:
        print("  references (constantes 32 bits) vers ces zones dans l'image d'origine : aucune")
        return
    print("!! l'image d'origine pointe dans une zone 0xFF ou un tweak veut ecrire :")
    show(sure)
    if not force:
        raise SystemExit("   Cette zone n'est peut-etre pas libre : refus d'ecrire.\n"
                         "   Verifie ces references a la main, puis relance avec --force-cave si elles sont sans danger.")
    print("   --force-cave : on continue quand meme.")


def apply_writes(main_os, tweaks_selected):
    data = bytearray(main_os)
    dirty = bytearray(len(main_os))
    for t in tweaks_selected:
        for w in t["writes"]:
            off = w["off"]
            old = unhex(w["old"])
            new = unhex(w["new"])
            if not isinstance(off, int) or isinstance(off, bool) or off < 0 or off + len(old) > len(data):
                raise SystemExit(f"!! {t['id']} : ecriture hors de la section 3 (off {off})")
            cur = bytes(data[off:off + len(old)])
            if cur == new and cur != old:
                continue                         # la meme ecriture, deja faite par un autre tweak (masque partage)
            if cur != old:
                raise SystemExit(
                    f"!! {t['id']} @ {off}: octets 'old' attendus {old.hex()} "
                    f"mais trouves {cur.hex()} — refus d'ecrire")
            data[off:off + len(new)] = new
            for k in range(off, off + len(new)):
                dirty[k] = 1
    return bytes(data), dirty


END_LIMIT = 0x40200000       # l'image décompressée doit finir sous la zone de travail du bootstrap (notes/17)


def payload_runtime(t, main_os, st_img, md=None):
    """Charge utile d'un tweak « append » telle qu'en mémoire à l'exécution (à partir de append.dest) : recette
    exécutée sur TON fichier Syntakt (st_img, section 7 vérifiée), pour les morceaux « cycles » sur TON MAIN OS
    Cycles d'origine, et pour les morceaux « md » (TRX-B2) sur TON OS du Machinedrum (md : {nom : octets},
    tools/machines/trx_b2/headers.py)."""
    ap_ = t["append"]
    dest, size = int(ap_["dest"], 16), ap_["size"]
    out = bytearray(size)
    for part in ap_["parts"]:
        at = int(part["dest"], 16) - dest
        if "syntakt" in part:
            lo, hi = (int(x, 16) for x in part["syntakt"])
            chunk = st_img[lo - BASE:hi - BASE]
        elif "cycles" in part:                          # plage de l'OS Cycles d'origine (notes/18)
            lo, hi = (int(x, 16) for x in part["cycles"])
            chunk = main_os[lo - BASE:hi - BASE]
        elif "md" in part:                              # donnée de l'OS du Machinedrum (TRX-B2)
            if md is None:
                raise SystemExit(f"!! {t['id']} a besoin de ton OS du Machinedrum : --md Elektron_SPS1-1UW_OS1.63.syx")
            chunk = md[part["md"]]
            if len(chunk) != part["size"]:
                raise SystemExit(f"!! {t['id']} : {part['md']} de {len(chunk)} o, {part['size']} attendus")
        else:
            chunk = unhex(part["hex"])
        out[at:at + len(chunk)] = chunk
    for va, old, new in ap_["reloc"]:
        at = int(va, 16) - dest
        o, n = unhex(old), unhex(new)
        if len(o) != 4 or len(n) != 4 or not 0 <= at <= len(out) - 4:
            raise SystemExit(f"!! relocalisation {va} : 4 octets attendus dans la charge utile")
        if out[at:at + 4] != o:
            raise SystemExit(f"!! relocalisation {va} : {old} attendu, {out[at:at + 4].hex()} trouvé")
        out[at:at + 4] = n
    return bytes(out)


def payload_image(t, runtime):
    """Ce qui va dans l'image : la charge utile entière, rangée en morceaux (append.pack : [adresse, taille] ; hors
    des morceaux, tout doit être à zéro : le crochet de démarrage remet à zéro, puis recopie les morceaux), ou
    compressée (append.compress = "aplib" : tools/aplib_grow.py pack, décompressée par le crochet, notes/50)."""
    ap_ = t["append"]
    if "compress" in ap_:
        if ap_["compress"] != "aplib":
            raise SystemExit(f"!! {t['id']} : compression {ap_['compress']!r} inconnue")
        import aplib_grow                               # noqa: E402
        return aplib_grow.pack(runtime)
    if "pack" not in ap_:
        return runtime
    dest, out, kept = int(ap_["dest"], 16), bytearray(), bytearray(runtime)
    for a, n in ap_["pack"]:
        at = int(a, 16) - dest
        out += runtime[at:at + n]
        kept[at:at + n] = bytes(n)
    if any(kept):
        raise SystemExit(f"!! {t['id']} : octets non nuls hors des morceaux rangés")
    return bytes(out)


def md_data(path):
    """Sinus et tables du TRX-B2 depuis l'OS du Machinedrum de l'utilisateur (vérifié par son SHA-256)."""
    sys.path.insert(0, str(HERE / "machines" / "trx_b2"))
    import headers                                      # noqa: E402  (tools/machines/trx_b2/headers.py)
    return headers.md_parts(path)


def build_payload(chosen, main_os, syntakt_path, md_path=None):
    """Charges utiles des tweaks « append » (notes/17), l'une après l'autre dans l'ordre des tweaks (Model-TG, puis
    les moteurs du Syntakt de la version combinée, notes/31). Renvoie (octets à ajouter après l'image, dernier
    tweak) ou (b"", None)."""
    apps = sorted((t for t in chosen if t.get("append")), key=lambda t: t["order"])
    if not apps:
        return b"", None
    img = None
    if any("syntakt" in t["append"] for t in apps):     # morceaux copiés du programme audio du Syntakt
        t = next(t for t in apps if "syntakt" in t["append"])
        if not syntakt_path:
            raise SystemExit(f"!! {t['id']} a besoin de ton fichier Syntakt : --syntakt Syntakt_OS1.42.syx")
        sys.path.insert(0, str(HERE / "emu"))
        import syntakt                                  # noqa: E402  (tools/emu/syntakt.py)
        for t in apps:
            st = t["append"].get("syntakt")
            if st and (syntakt.OFFICIAL, syntakt.DSP_SHA256) != (st["os"], st["section_sha256"]):
                raise SystemExit("!! empreintes Syntakt du tweak et de tools/emu/syntakt.py différentes")
        img = syntakt.dsp_image(syntakt_path)           # vérifie le .syx officiel et sa section 7
    md = None
    if any("md" in p_ for t in apps for p_ in t["append"]["parts"]):
        t = next(t for t in apps if any("md" in p_ for p_ in t["append"]["parts"]))
        if not md_path:
            raise SystemExit(f"!! {t['id']} a besoin de ton OS du Machinedrum : --md Elektron_SPS1-1UW_OS1.63.syx")
        md = md_data(md_path)
    out = bytearray()
    for t in apps:
        ap_ = t["append"]
        if BASE + len(main_os) + len(out) != int(ap_["at"], 16):
            raise SystemExit(f"!! {t['id']} : l'image ne finit pas à {ap_['at']}")
        rt = payload_runtime(t, main_os, img, md)
        chunk = payload_image(t, rt)
        out += chunk
        src = pathlib.Path(syntakt_path).name if "syntakt" in ap_ else \
            pathlib.Path(md_path).name + " et le tweak" if md is not None and t["id"] == "trx-b2" else "le tweak seul"
        where = "en place" if ap_["dest"] == ap_["at"] else f"copiée à {ap_['dest']} au démarrage"
        packed = (f", compressée en {len(chunk)} o" if "compress" in ap_ else f", rangée en {len(chunk)} o" if "pack" in ap_
                  else "")
        print(f"  charge utile {t['id']} : {ap_['size']} o depuis {src}, {len(ap_['reloc'])} relocalisations, {where}{packed}")
    if BASE + len(main_os) + len(out) > END_LIMIT:
        raise SystemExit(f"!! l'OS agrandi dépasserait {END_LIMIT:#x}")
    return bytes(out), apps[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", help="ton .syx officiel")
    ap.add_argument("-t", "--tweaks", help="liste d'ids separes par des virgules")
    ap.add_argument("--all", action="store_true", help="applique tous les tweaks du device")
    ap.add_argument("-o", "--output", help="fichier de sortie (defaut: <in>_mod.syx)")
    ap.add_argument("--list", action="store_true", help="liste les tweaks disponibles")
    ap.add_argument("--expect-mainos", help="SHA-256 attendu du MAIN OS patche (verification)")
    ap.add_argument("--syntakt", help="ton Syntakt_OS1.42.syx officiel (tweaks qui en extraient un moteur)")
    ap.add_argument("--md", help="ton Elektron_SPS1-1UW_OS1.63.syx officiel (machine TRX-B2)")
    ap.add_argument("--force-cave", action="store_true",
                    help="ecrit meme si l'image d'origine pointe dans une zone 0xFF utilisee (a verifier a la main)")
    args = ap.parse_args()

    cat = load_catalog()
    if args.list or not args.input:
        cmd_list(cat)
        return

    raw = pathlib.Path(args.input).read_bytes()
    stream, info = unwrap(raw)                       # verifie chaque checksum de paquet
    c = container.parse(stream)
    s3 = next(s for s in c["sections"] if s["id"] == 3)
    main_os, ops = aplib.depack(c["blob"][s3["off"]:s3["off"] + s3["size"]])

    name, dev, tweaks = pick_target(cat, sha(raw))
    if not dev:
        # repli : matcher sur le MAIN OS decompresse
        for nm, (d, tw) in cat.items():
            if d["section_sha256"] == sha(main_os):
                name, dev, tweaks = nm, d, tw
                break
    if not dev:
        raise SystemExit("!! image non reconnue (ni .syx ni section 3). Version d'OS differente ?")
    if sha(main_os) != dev["section_sha256"]:
        raise SystemExit("!! la section 3 ne correspond pas a l'image de reference")
    print(f"cible : {dev['device']} OS {dev['os']}")

    if args.all:
        chosen = list(tweaks.values())
    elif args.tweaks:
        chosen = []
        for tid in args.tweaks.split(","):
            tid = tid.strip()
            if tid not in tweaks:
                raise SystemExit(f"!! tweak inconnu : {tid}")
            chosen.append(tweaks[tid])
    else:
        raise SystemExit("!! choisis --all ou -t <ids>")
    check_conflicts(chosen)
    chosen.sort(key=lambda t: t["order"])            # dans l'ordre des tweaks : l'un peut s'appliquer sur l'autre
    for t in chosen:
        print(f"  + {t['name']}")

    patched, dirty = apply_writes(main_os, chosen)
    check_caves(main_os, chosen, args.force_cave, dirty, patched, dev.get("cave_refs_ok"))
    payload, _ = build_payload(chosen, main_os, args.syntakt, args.md)
    orig_len = len(patched)
    if payload:
        patched = patched + payload
        dirty = dirty + bytearray(b"\x01") * len(payload)
    print(f"  {sum(dirty)} octets changes sur {len(patched)}")
    print(f"  MAIN OS patche SHA-256 : {sha(patched)}")
    if args.expect_mainos and sha(patched) != args.expect_mainos.lower():
        raise SystemExit("!! le MAIN OS patche ne correspond pas au SHA attendu")

    # reconstruction : re-emet le flux aPLib, recalcule checksums + HMAC
    if payload:
        import aplib_grow                               # noqa: E402
        new_s3 = aplib_grow.repack_grow(patched, ops, dirty, orig_len)
        if aplib.depack(new_s3)[0] != patched:
            raise SystemExit("!! recompression de l'OS agrandi : relecture différente")
    else:
        new_s3 = aplib.repack(patched, ops, dirty)
    msg = c["blob"][:len(c["blob"]) - container.DIGEST_LEN]
    expect = c["blob"][len(c["blob"]) - container.DIGEST_LEN:]
    # cle HMAC re-derivee depuis les sections decompressees de l'image d'origine
    plain = []
    for s in c["sections"]:
        try:
            plain.append(aplib.depack(c["blob"][s["off"]:s["off"] + s["size"]])[0])
        except Exception:
            pass
    key = container.find_key(plain, msg, expect)
    if not key:
        raise SystemExit("!! cle HMAC introuvable — image inattendue")
    blob = container.rebuild(c, {3: new_s3}, key)
    out_stream = container.build_stream(blob, BYTES_PER_MSG)
    out_raw = wrap(out_stream, info["product"], info["start_seq"])

    out_path = args.output or args.input.replace(".syx", "") + "_mod.syx"
    pathlib.Path(out_path).write_bytes(out_raw)
    print(f"\n  ecrit : {out_path}  ({len(out_raw)} o)")
    print(f"  .syx SHA-256 : {sha(out_raw)}")
    print("  (le hash du .syx depend du packer ; c'est le MAIN OS patche ci-dessus qui fait foi)")
    print("\n  Flash : STARTUP MENU (FUNC + power on, TRIG 4) puis envoi sur le MIDI IN (jack TRS).")


if __name__ == "__main__":
    main()
