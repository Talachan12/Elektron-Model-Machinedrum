"""Régulateur de charge en assembleur (notes/36) : une étape pure appliquée aux tweaks des moteurs du Syntakt.

Le régulateur est compilé avec la passerelle (machines/syntakt_bridge/bridge_engines.c) par m68k-elf-gcc 16.2, qui ne
se reproduit pas avec un autre GCC. Ses fonctions sont donc remplacées APRÈS la compilation, à leur propre adresse
(champ « gov » du tweak), par de l'assembleur (machines/gov/*.S, binutils seuls) :
  - audio_end (toutes les versions) : nouvelle règle d'extinction (audio_end.S, gov_cut.S) ;
  - avec Model-TG, voice_gate et voice_after (exécutés pour chaque piste à chaque bloc, en SRAM) : même rôle, moins
    d'instructions (voice_gate_tg.S, voice_after_tg.S).
Les appels ne changent pas : la sonde, le détour de la boucle des voix et voice_done appellent les mêmes adresses.
La partie rare de la décision (gov_cut.S) va dans la place que libèrent les nouvelles fonctions (avec Model-TG,
dans les zones de SRAM déjà rangées dans l'image), ou dans la charge utile, à un endroit libre (sans Model-TG, la
charge utile est recopiée en entier). Les nouvelles variables sont dans la charge utile, hors de tout morceau : à
zéro au démarrage.

gen_syntakt_engines.py applique add_to à la fin de build_tweak (sauf aux firmwares de diagnostic, dont le compteur
est dans audio_end) ; elle s'applique de même à un JSON déjà versionné (même résultat, sans recompiler).

Preuve : tools/emu/test_governor.py, tools/emu/test_model_tg_syntakt.py (et tous les tests du son).
"""
import pathlib
import re
import shutil
import subprocess
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "machines" / "gov"
CROSS = next((c for c in ("m68k-linux-gnu-", "m68k-elf-") if shutil.which(c + "as")), "m68k-linux-gnu-")
TIMER = 0xfc07000c
TRACK_BASE = 0x80001858
# Zones de SRAM reprises aux tables d'ondes de CHORD (notes/28, notes/29) : (décalage de leur image dans la charge
# utile, adresse d'exécution, taille). Avec Model-TG, les fonctions les plus appelées de la passerelle y sont.
SRAM_BANKS = ((0x0, 0x80001c5c, 0x5858), (0x5858, 0x8000cac0, 0x2020))
X_VARS = 0x32f00             # nouvelles variables (décalage dans la charge utile : fin de la zone des données de la
                             # passerelle, DST_BRIDGE + 0x1f00, sous les détours en + 0x33000)
X_CODE = 0x32c00             # sans Model-TG : gov_cut.S (DST_BRIDGE + 0x1c00)
XV = dict(X_LAST_T0=0, X_PREV_LOAD=4, X_BLK=8, X_VT0=12, X_FAST=16, X_SLOW=20, X_CUT=24)   # X_CUT : 6 mots longs
FAR = 0x7ffffff0             # adresse provisoire des pièces, pour mesurer : une adresse sur 16 bits ferait
                             # choisir à l'assembleur l'adressage absolu court (2 octets de moins)
PIECES = ("gov_cut.S", "gov_key.S", "gov_gains.S")      # la décision, rare : dans la place libre
ALIGN = {"gov_gains.S": 4}                               # une table de mots longs ; le code, sur 2 octets
RECENT = 32                  # blocs pendant lesquels une voix éteinte compte encore (fondu de 8, puis la moyenne rapide)
NOTE = ("Régulateur de charge en assembleur (tools/gov_asm.py, notes/36) : pics isolés ignorés, voix la moins audible "
        "dans le mix.")


def x_var(tweak, name):
    """Adresse d'une des nouvelles variables (XV) dans ce tweak : pour les tests (X_SLOW : moyenne lente, en 1/65536
    de bloc)."""
    return int(tweak["append"]["dest"], 16) + X_VARS + XV[name]


def _pct(x):
    return x * 256 // 100     # PCT() de bridge_engines.c


def assemble(name, at, equ):
    """Octets de machines/gov/name avec les constantes equ. Tout y est absolu (constantes) ou relatif au PC (étiquettes
    locales) : l'assembleur résout tout, sans édition de liens (qui alignerait le début sur 4 octets) ; at ne sert
    qu'à vérifier qu'il ne reste aucune relocation."""
    head = "".join(f"        .equ    {k}, {v:#x}\n" for k, v in sorted(equ.items()))
    with tempfile.TemporaryDirectory() as d:
        src, obj, out = (pathlib.Path(d) / n for n in ("a.S", "a.o", "a.bin"))
        src.write_text(head + (SRC / name).read_text(encoding="utf-8"), encoding="utf-8")
        subprocess.run([CROSS + "as", "-mcpu=54418", "-o", str(obj), str(src)], check=True)
        rel = subprocess.run([CROSS + "objdump", "-r", str(obj)], capture_output=True, text=True, check=True).stdout
        if "R_68K" in rel:
            raise SystemExit(f"!! régulateur : {name} demande une édition de liens ({at:#x})")
        subprocess.run([CROSS + "objcopy", "-O", "binary", "-j", ".text", str(obj), str(out)], check=True)
        return out.read_bytes(), {}


_BR = re.compile(r"^(b(?:ra|sr|hi|ls|cc|cs|ne|eq|vc|vs|pl|mi|ge|lt|gt|le))[swl]?$")


def extent(code, run):
    """Fin (exclue) de la fonction compilée qui commence à run, code = ses octets et la suite : parcours de son
    graphe (branchements suivis, arrêt sur rts / jmp), comme le compilateur l'a rangée."""
    with tempfile.TemporaryDirectory() as d:
        b = pathlib.Path(d) / "f.bin"
        b.write_bytes(code)
        txt = subprocess.run([CROSS + "objdump", "-D", "-b", "binary", "-m", "m68k:isa-c:emac",
                              f"--adjust-vma={run:#x}", str(b)], capture_output=True, text=True, check=True).stdout
    ins = {}
    for line in txt.splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\t((?:[0-9a-f]{4} )+)\s*\t(\S+)\s*(.*)$", line)
        if m:
            ins[int(m.group(1), 16)] = (len(m.group(2).split()) * 2, m.group(3), m.group(4))
    seen, todo, end = set(), [run], run
    while todo:
        a = todo.pop()
        while a not in seen:
            if a not in ins:
                raise SystemExit(f"!! régulateur : instruction illisible en {a:#x}")
            seen.add(a)
            n, mn, ops = ins[a]
            end = max(end, a + n)
            if mn in ("rts", "rte") or mn.startswith("jmp"):
                break
            br = _BR.match(mn)
            if br and br.group(1) != "bsr":
                tgt = int(re.search(r"0x([0-9a-f]+)", ops).group(1), 16)
                if tgt < run:
                    raise SystemExit(f"!! régulateur : branchement avant le début de la fonction en {a:#x}")
                todo.append(tgt)
                if br.group(1) == "bra":
                    break
            a += n
    return end


def _parts(tweak):
    """[(adresse, octets modifiables)] des morceaux « hex » de la charge utile."""
    return [[int(p_["dest"], 16), bytearray.fromhex(p_["hex"]), p_] for p_ in tweak["append"]["parts"] if "hex" in p_]


def add_to(tweak, tg_syms=None):
    """Le tweak (dictionnaire) avec son régulateur remplacé, et une ligne de description. tg_syms : symboles de
    Model-TG (champ « symbols » de 30-model-tg-st.json) pour la version combinée."""
    import gen_syntakt_engines as gs
    gov = {k: int(v, 16) for k, v in tweak["gov"].items()}
    tg = "model-tg-st" in tweak.get("requires", [])
    if tg and not tg_syms:
        raise SystemExit("!! régulateur : version combinée sans les symboles de Model-TG")
    pay = int(tweak["append"]["dest"], 16)
    parts = _parts(tweak)

    def where(run):
        """(morceau, décalage dans ses octets) de l'adresse d'exécution run."""
        a = run
        for off, base, n in SRAM_BANKS:
            if base <= run < base + n:
                a = pay + off + run - base
        for p_ in parts:
            if p_[0] <= a < p_[0] + len(p_[1]):
                return p_, a - p_[0]
        raise SystemExit(f"!! régulateur : {run:#x} hors des morceaux de la charge utile")

    # constantes : variables de la passerelle par rapport à la plus basse (adressage d8(An,Xi) : sous 128 o)
    G = gs.GOV
    gb = min(v for k, v in gov.items() if k.startswith("gov_"))
    equ = {"O_" + k[4:].upper(): v - gb for k, v in gov.items() if k.startswith("gov_")}
    if max(equ.get("O_" + k, 0) for k in ("FADING", "STOLEN", "QUIET", "AGE", "FLEN", "FREE", "ST")) > 0x7f:
        raise SystemExit("!! régulateur : tableaux de la passerelle trop éloignés (adressage d8(An,Xi))")
    if any(pay + X_CODE <= v < pay + X_VARS + 0x100 for v in gov.values()):
        raise SystemExit("!! régulateur : les variables de la passerelle débordent sur la place prévue")
    equ.update({"O_" + k: pay + X_VARS + v - gb for k, v in XV.items()})
    equ.update(GB=gb, TIMER=TIMER, TRACK_BASE=TRACK_BASE, RECENT=RECENT, PRESSURE=_pct(72), STEAL=_pct(G["steal"]),
               TARGET=_pct(G["target"]), PEAK=_pct(G["peak"]), PEAK_TO=_pct(G["peak"] - G["margin"]),
               SEVERE=_pct(G["severe"]), SLOW_SH=G["slow"], IDLE_THR=gs.IDLE_THR, IDLE_BLOCKS=gs.IDLE_BLOCKS,
               GOV_CUT=FAR, GOV_KEY=FAR, GOV_GAINS=FAR)
    if tg:
        equ.update(TG=1, TG_FIRST=gs.TG_FIRST, **{f"TG_{k.upper()}": int(tg_syms[k], 16)
                                                  for k in ("rs_state", "rs_src", "sle_run", "sle_trk")})
    # les fonctions remplacées, à leur place ; la place qui reste après elles
    fixed = [("audio_end", "audio_end.S")] + ([("voice_gate", "voice_gate_tg.S"), ("voice_after", "voice_after_tg.S")]
                                              if tg else [])
    free = []                                    # [adresse d'exécution, morceau, décalage, octets libres]
    sizes = {src: len(assemble(src, FAR, equ)[0]) for src in [s_ for _, s_ in fixed] + list(PIECES)}
    for name, src in fixed:
        p_, o = where(gov[name])
        n = extent(bytes(p_[1][o:]), gov[name]) - gov[name]
        size = sizes[src]
        if size > n:
            raise SystemExit(f"!! régulateur : {src} ({size} o) plus grand que {name} compilé ({n} o)")
        a = gov[name] + size                     # (le code est sur 2 octets ; une table se recale sur 4 ci-dessous)
        free.append([a, p_, o + a - gov[name], gov[name] + n - a])
    if not tg:                                   # charge utile recopiée en entier : une place libre en plus
        lo, hi = pay + X_CODE, pay + X_VARS
        for x in tweak["append"]["parts"]:
            a = int(x["dest"], 16)
            n = len(x["hex"]) // 2 if "hex" in x else x["size"] if "size" in x else (lambda r: int(r[1], 16) - int(r[0], 16))(x.get("syntakt") or x["cycles"])
            if a < hi and lo < a + n:
                raise SystemExit("!! régulateur : la place de la décision est prise")
        free.append([lo, None, 0, hi - lo])
    # la décision (rare) dans la place libre, la plus grande pièce d'abord
    where_ = {}
    for src in sorted(PIECES, key=lambda s_: -sizes[s_]):
        size, al = sizes[src], ALIGN.get(src, 2)
        spot = next((f for f in free if f[3] - (-f[0] % al) >= size), None)
        if spot is None:
            raise SystemExit(f"!! régulateur : pas de place pour {src} ({size} o)")
        pad = -spot[0] % al
        where_[src] = (spot[0] + pad, spot[1], spot[2] + pad)
        spot[0] += pad + size
        spot[2] += pad + size
        spot[3] -= pad + size
    equ.update(GOV_CUT=where_["gov_cut.S"][0], GOV_KEY=where_["gov_key.S"][0], GOV_GAINS=where_["gov_gains.S"][0])
    new_part = bytearray()
    for name, src in fixed:
        p_, o = where(gov[name])
        code = assemble(src, gov[name], equ)[0]
        if len(code) != sizes[src]:
            raise SystemExit(f"!! régulateur : {src} change de taille une fois placé")
        p_[1][o:o + len(code)] = code            # le reste de l'ancienne fonction n'est plus atteint
    for src, (a, p_, o) in where_.items():
        code = assemble(src, a, equ)[0]
        if len(code) != sizes[src]:
            raise SystemExit(f"!! régulateur : {src} change de taille une fois placé")
        if p_ is None:
            k = a - (pay + X_CODE)
            new_part[len(new_part):k] = bytes(max(0, k - len(new_part)))
            new_part[k:k + len(code)] = code
        else:
            p_[1][o:o + len(code)] = code
    for p_ in parts:
        p_[2]["hex"] = p_[1].hex()
    if new_part:
        tweak["append"]["parts"].append({"dest": f"{pay + X_CODE:#x}", "hex": new_part.hex()})
    tweak["description"] = tweak["description"] + [NOTE]
    return tweak
