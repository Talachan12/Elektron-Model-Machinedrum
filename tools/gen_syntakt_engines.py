#!/usr/bin/env python3
"""Génère les tweaks « syntakt-<moteurs> » : N vrais moteurs du Syntakt en machines ajoutées du Model:Cycles,
pour n'importe quel choix de moteurs du catalogue (notes/20). Le flasher web fait cocher les moteurs voulus.

Même méthode que gen_syntakt_machines.py (notes/19, testé : SDVtg + CPVtg), généralisée :
  - catalogue des moteurs (CATALOG) ; les machines ajoutées prennent les index 6, 7, 8… dans l'ordre du catalogue ;
  - passerelle bridge_engines.c (un moteur du Syntakt par machine) ; détours générés pour N machines ;
  - table machine -> moteur de l'OS (8 octets, 0x40118640) déplacée : plus de 2 machines ajoutées possibles ;
  - charge utile : moteurs du catalogue (réunion) et tables à adresses fixes, prévues pour 6 machines ajoutées.
Toutes les combinaisons sont générées ici, avec l'arrêt des voix muettes (notes/23) ; les anciens tweaks
sdvintage-7th et syntakt-vintage restent disponibles avec build.py.

    python3 tools/gen_syntakt_engines.py --cycles … --syntakt … --engines cp [--check]
    python3 tools/gen_syntakt_engines.py --cycles … --syntakt … --all [--check]   # toutes les autres combinaisons
"""
import argparse
import itertools
import json
import pathlib
import struct
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "emu"))

import gen_sdvintage_exact as gx   # noqa: E402
import gen_sdvintage_7th as g7     # noqa: E402
import gen_syntakt_machines as g8  # noqa: E402
import sprites                     # noqa: E402
import usb_steady                  # noqa: E402
import voice_loop                  # noqa: E402
import gov_asm                     # noqa: E402
import syntakt                     # noqa: E402

DEV = HERE.parent / "tweaks" / "model-cycles_OS1.13"
BASE = gx.BASE

# --- catalogue : moteurs de la boucle des voix du Syntakt, dans l'ordre des machines ajoutées ------------
# name : nom dans le menu MACHINES (5 lettres) ; engine : moteur du Syntakt (tables 0x40014920 / 0x400148f0) ;
# image : image de machine du Cycles montrée (l'OS n'en a que 6) ; knobs : COLOR, SHAPE, SWEEP, CONTOUR = p1..p4
# du Syntakt (nom long en mots de 8 lettres au plus, nom court, défaut[, min, max]), d'après les descripteurs de
# son interface. Ce que le moteur ajoute à la copie : code_end (fin de la plage de code), tables_high (tables
# placées à TABLES_AT), imm (immédiats « move.l #adr » qui sont des adresses, vérifiés à la main), roots
# (fonctions appelées par pointeur que la fermeture ne suit pas d'elle-même).
# punch_on / punch_off : valeur de l'emplacement 23 du Syntakt quand PUNCH est actif / inactif (défaut : celle
# du Cycles, PNCH 0..1 ; punch_off vaut 0 si absent).
CATALOG = {
    "sd": dict(label="SD VINTAGE", name="SDVtg", engine=6, update=0x40008074, render=0x4000847a, image=1, decay=33,
               knobs=(("Inharm", "INHM", 0), ("Freq Complex", "FCMP", 110), ("Pitch Sweep", "SWEP", 74),
                      ("Mod Envelope", "MENV", 80))),
    "cp": dict(label="CP VINTAGE", name="CPVtg", engine=7, update=0x40008580, render=0x40008988, image=3, decay=32,
               knobs=(("Body Char", "BODY", 24), ("Balance", "BAL", 25), ("Spacing Crunch", "SPCR", 46),
                      ("Body Envelope", "BENV", 37))),
    # type 36, descripteurs « TOY » 0x402302e8.. : Form, Impact, Brightness, Partial Decay (PNCH 0..1 : PUNCH)
    # imm : 0x800098ec = tampon SRAM rangé dans la voix (+412), suite de la série 0x8000945c, 0x80009580,
    # 0x800096a4, 0x800097c8 (pas de 0x124) déjà classée en adresses (gen_sdvintage_exact.py).
    "toy": dict(label="SY TOY", name="SYToy", engine=8, update=0x40008ae8, render=0x40008d58, image=4, decay=60,
                knobs=(("Form", "FORM", 24), ("Impact", "IMP", 60), ("Bright", "BRIG", 110),
                       ("Partial Decay", "PART", 64)),
                code_end=0x40008e0c, tables_high=((0x4003be38, 0x4003de38),), imm={0x800098ec}),
    # type 37, descripteurs « BITS » 0x40230488.. : Detune (40..88), Balance, Sample Rate Redux, Waveform.
    # L'emplacement 23 est Bit Redux (0..127), sans potard sur le Cycles : PUNCH actif = punch_on.
    # imm : 10 tables d'ondes de 0x804 o en SRAM (0x80004f74.. et 0x8000c888..), rangées dans la voix (+176,
    # +180) par 0x40006588 et l'update ; 0x8000a064 : tampon SRAM pris dans a4 (0x40006276).
    "bits": dict(label="SY BITS", name="SYBit", engine=9, update=0x40008e0c, render=0x400091e0, image=4, decay=60,
                 knobs=(("Detune", "DET", 52, 40, 88), ("Balance", "BAL", 102), ("Rate Redux", "SRR", 0),
                        ("Waveform", "WAVE", 21)), punch_on=80,
                 roots=(0x40006646,),           # appelée par pointeur (« lea 0x40006646,%fp » en 0x40008fd8)
                 code_end=0x400092ec, tables_high=((0x4003de38, 0x4003ee38),),
                 imm={0x80004f74, 0x80005778, 0x80005f7c, 0x80006780, 0x80006f84, 0x80007788, 0x8000c888,
                      0x8000d08c, 0x8000d890, 0x8000e094, 0x8000a064}),
    # type 38, descripteurs « SSAW » 0x40230628.. : Noise Modulation, Detune Animation, Detune, Oscillator Mix.
    # L'emplacement 23 est Fundamental Sub (0..2, défaut 2 = note jouée ; 1 et 0 : une et deux octaves plus bas),
    # sans potard sur le Cycles : PUNCH inactif = 2, actif = 1.
    # imm : 4 tampons SRAM (0x80009c58.., pas de 0x94) rangés dans la voix (+288, +416, +668).
    "swarm": dict(label="SY SWARM", name="SYSwm", engine=10, update=0x400092ec, render=0x400096e8, image=5, decay=75,
                  knobs=(("Noise Mod", "NMOD", 20), ("Detune Anim", "ANIM", 15), ("Detune", "DET", 70),
                         ("Osc Mix", "MIX", 127)), punch_off=2, punch_on=1,
                  code_end=0x400097dc, tables_high=((0x4003ee38, 0x40040038),),
                  imm={0x80009c58, 0x80009cec, 0x80009d80, 0x80009e14}),
}
# Combinaisons qui gardaient leur tweak d'origine (notes/18, notes/19). Depuis l'arrêt des voix muettes (notes/23),
# toutes passent par ce générateur ; sdvintage-7th et syntakt-vintage restent disponibles avec build.py.
LEGACY = {}
# Combinaisons testées sur un vrai Model:Cycles (affiché dans le flasher). Ajouter ici après un test réussi.
# Testés avant l'arrêt des voix muettes (30/09/2026) : SD, SD + CP, SY TOY, SD + CP + SY TOY, SY BITS, SY SWARM ;
# à retester avec lui.
HW_TESTED = set()
# Idem pour la version combinée avec Model-TG (notes/31) : firmware construit par le flasher et essayé sur la machine.
# 02/10/2026, Model-TG v1.0.0 : Model-TG + les 5 moteurs, avec l'audio USB 6 canaux, « tout marche » (retour de
# l'utilisateur). 03/10/2026, Model-TG v1.1.0 avec la retouche des mutes (notes/31 §10) : la même combinaison, avec
# l'arpégiateur, construite par build.py (même MAIN OS que le flasher), « c bon ça fonctionne nickel » ; l'utilisateur
# a demandé l'étiquette sans attendre un essai depuis le flasher.
HW_TESTED_TG = {("sd", "cp", "toy", "bits", "swarm")}
MAX_EXTRA = 6

# --- Syntakt : fermeture et plages copiées -----------------------------------------------------------------
# La copie dépend du DERNIER moteur coché (ordre du catalogue) : elle contient tout ce qu'il faut aux moteurs du
# catalogue jusqu'à lui, et au moins jusqu'à SY TOY. Ajouter un moteur au catalogue ne change donc pas, à
# l'octet près, les firmwares déjà testés sur la machine.
BASE_GEN = "toy"
CODE_START = 0x40002544                         # les fonctions (plage contiguë : le relatif au PC reste juste)
TABLES_LOW = (                                  # à la suite du code, sous la réplique de sa SRAM (0x43020000)
    (0x4000e488, 0x40010490),                   # table centrée sur 0x4000f48c (8 Ko), CP VINTAGE
    (0x40014980, 0x40016b90),                   # constantes + 2 tables de 4 Ko (0x40014b80, 0x40015b80)
    (0x40028438, 0x4003be38),                   # DEC x MENV, tables de 512 o de SD et CP VINTAGE
)
GX_IMM_ADDR = frozenset(gx.IMM_ADDR)             # immédiats-adresses de SD VINTAGE (gen_sdvintage_exact.py)

# --- SRAM interne du Cycles empruntée (notes/26) -------------------------------------------------------------
# Le cache de données du MCF54415 ne fait que 8 Ko : ce que les moteurs du Syntakt lisent et écrivent dans la
# réplique de leur SRAM (en SDRAM) passe par lui, à chaque bloc. Deux choses vont donc en SRAM interne :
#  - leurs tampons de travail, partagés par toutes les voix et écrits avant d'être lus à chaque calcul (comme sur le
#    Syntakt) : tableaux A et B de 7 éléments de 292 o (remise à zéro 0x40003f6c..0x4000402c : A + 292 k, B + 292 k)
#    et 4 tampons C de 148 o (SY SWARM). Seuls les 128 premiers octets de chaque élément servent (32 échantillons).
#    Ils prennent la zone de travail commune des machines d'origine, réécrite par chaque voix d'origine
#    (SCRATCH_POOL : leurs tableaux de 4 éléments de 292 o, 0x400a7b3e..0x400a7bd6, plus KICK et TONE), A et B
#    entrelacés pour garder le pas de 292 o (la somme des 7 voix de SY SWARM, 0x4000978a, lit B + 292 k) ;
#  - leur table de sinus (257 mots), identique à l'octet près à celle du Cycles (0x8000eee4, mêmes pointeurs dans
#    la remise à zéro des voix) : vérifié au build sur les deux fichiers.
SCRATCH_POOL = (0x8000beb8, 0x8000c8e8)
SRAM_MAP = (
    (0x80008c60, 0x8000945c, SCRATCH_POOL[0]),           # A_k -> zone + 292 k
    (0x8000945c, 0x80009c58, SCRATCH_POOL[0] + 128),     # B_k -> zone + 128 + 292 k
    (0x80009c58, 0x80009ea8, SCRATCH_POOL[0] + 2008),    # C_j -> zone + 2008 + 148 j
    (0x80004b70, 0x80004f74, 0x8000eee4),                # table de sinus
)
SCRATCH_HEADS = ((0x80008c60, 292, 7), (0x8000945c, 292, 7), (0x80009c58, 148, 4))   # (début, pas, éléments)
SINE = SRAM_MAP[3]


def sram_moved(a):
    """Adresse en SRAM du Cycles d'une adresse de la SRAM du Syntakt déplacée (SRAM_MAP), ou None."""
    for lo, hi, dst in SRAM_MAP:
        if lo <= a < hi:
            return a - lo + dst
    return None


def check_sram_map(img, st_img):
    """Les 128 premiers octets de chaque tampon tombent dans la zone empruntée, sans se chevaucher ; la table de
    sinus du Syntakt est celle du Cycles."""
    heads = sorted((sram_moved(s + k * step), s + k * step) for s, step, n in SCRATCH_HEADS for k in range(n))
    for (a, sa), (b, sb) in zip(heads, heads[1:]):
        if a + 128 > b:
            raise SystemExit(f"!! tampons {sa:#x} et {sb:#x} : chevauchement en SRAM")
    if heads[0][0] < SCRATCH_POOL[0] or heads[-1][0] + 128 > SCRATCH_POOL[1]:
        raise SystemExit("!! tampons hors de la zone de travail des machines d'origine")
    lo, hi, dst = SINE
    if sram_init(st_img, gx.ST_SRAM_INIT, lo, hi - lo) != sram_init(img, CY_SRAM_INIT, dst, hi - lo):
        raise SystemExit("!! table de sinus du Syntakt différente de celle du Cycles")


# contenu initial de la SRAM du Cycles, recopié au démarrage (0x4000045c) : (source, fin, destination)
CY_SRAM_INIT = ((0x4019b590, 0x401a2a50, 0x80000000), (0x401a2a50, 0x401aa140, 0x80008000))


def sram_init(image, init, a, n):
    """n octets de la SRAM à l'adresse a, tels que le démarrage les y recopie depuis l'image."""
    for lo, hi, dst in init:
        if dst <= a and a + n <= dst + hi - lo:
            return bytes(image[lo - BASE + a - dst:][:n])
    return None

# --- charge utile (adresses fixes, jusqu'à 6 machines ajoutées) --------------------------------------------
# Adresse d'exécution PAY : seule, au-dessus du BSS du Cycles (notes/17) ; avec Model-TG, le haut de sa zone
# d'échantillons, qu'il nous laisse (notes/31). Tout le reste est à un décalage fixe de PAY.
PAY_ALONE = 0x43000000
PAY_TG = 0x46700000
STUB_END = 0x4016cba8        # le crochet de démarrage (gx.CAVE) s'arrête là : l'arpégiateur a la suite (gen_arp.py)
LAYOUT = dict(
    DST_SRAM=0x20000,        # réplique de la SRAM du Syntakt
    ST_BSS_AT=0x30000,       # fenêtre de son BSS
    DST_BRIDGE=0x31000,      # passerelle, puis ses données (+0x1000)
    DST_END=0x33000,
    STUBS=0x33000,
    DATA=0x33800,            # noms, update/render, VEC, table machine -> moteur, chaînes
    DESCN=0x34000,           # 76 + 5 x N descripteurs (au plus 106 x 0x38 = 0x1730)
    ROWSN=0x35800,           # (6 + N) x 32 o, (7 + N) avec Model-TG
    CCROWSN=0x35a00,         # idem
    RECS=0x35c00,            # enregistrement par machine ajoutée : 0x60 o chacun (76 o + drapeau)
    REC_ATK=0x35f00,         # avec Model-TG : copie d'un enregistrement, Attack sur le potard DECAY (76 o)
    TABLES_AT=0x36000,       # tables_high des moteurs
)


def set_base(pay):
    """Place la charge utile à pay (constantes de ce module et de gen_sdvintage_exact.py)."""
    global PAY
    PAY = pay
    for k, off in LAYOUT.items():
        globals()[k] = pay + off
    gx.DST_CODE, gx.DST_SRAM, gx.DST_BRIDGE, gx.DST_END = pay, DST_SRAM, DST_BRIDGE, DST_END


set_base(PAY_ALONE)


def generation(codes):
    """Moteurs du catalogue dont la copie contient le code et les tables : jusqu'au dernier coché, au moins
    jusqu'à BASE_GEN."""
    order = list(CATALOG)
    return tuple(order[:max(order.index(BASE_GEN), max(order.index(c) for c in codes)) + 1])


# --- code du Syntakt en SRAM interne (notes/28) --------------------------------------------------------------
# Avec plusieurs moteurs différents, leur code ne tient pas dans le cache d'instructions (8 Ko) : il est relu en
# SDRAM à chaque bloc (notes/27). Environ 30 Ko de la SRAM ne servent qu'aux 30 tables d'ondes de CHORD, que seule
# son update lit, par la table de 32 pointeurs 0x40118590 (0x400a8060). Ces tables passent dans la charge utile
# (copiées au build depuis le MAIN OS de l'utilisateur ; l'OS réutilise leur copie de démarrage comme BSS) et
# CHORD_PTRS pointe dessus. La 1re zone libérée reçoit les fonctions atteintes du Syntakt (blocs tassés dans
# l'ordre : les sauts relatifs entre blocs sont recalculés, ils ne peuvent que raccourcir) et ses tables les plus
# lues ; le crochet de démarrage (stub.S) les y recopie depuis la charge utile, après l'initialisation de la SRAM.
CHORD_PTRS = 0x40118594      # 31 pointeurs (le 1er des 32, 0x40118590, vise une table de l'OS en SDRAM)
CHORD_BANKS = ((0x80001c5c, 0x800074b4), (0x8000cac0, 0x8000eae0))     # 22 + 8 tables de 1 028 o
SRAM_RUN = CHORD_BANKS[0]    # où s'exécute le code du Syntakt ; la 2e zone reçoit des états de voix (notes/29)
SRAM_TABLES = (                                  # tables de la SRAM du Syntakt, lues à chaque bloc, en lecture seule
    (0x8000a080, 0x8000a888),                   # SD VINTAGE : 2 tables (0x8000a080, 0x8000a484)
    (0x80006f84, 0x80007788),                   # SY SWARM (forme d'onde, aussi l'une des 10 de SY BITS)
)
GUARD = 16                   # octets voisins recopiés de part et d'autre (lectures juste avant ou après une table)
VOICES = 6                   # états des voix du Syntakt en SRAM (1 par piste ; ses voix 6 et 7 restent dans la réplique)
ST_VSTRIDE = 1800            # taille de l'état d'une voix du Syntakt (bridge_engines.c)


def code_blocks(ins, insns):
    """Plages contiguës du code atteint (écarts de remplissage de 2 o au plus compris)."""
    runs = []
    for a in sorted(insns):
        if runs and a - runs[-1][1] <= 2:
            runs[-1][1] = a + ins[a][0]
        else:
            runs.append([a, a + ins[a][0]])
    return [tuple(r) for r in runs]


def st_sram_src(a):
    """Adresse, dans l'image du Syntakt, du contenu initial de l'adresse a de sa SRAM."""
    for lo, hi, dst in gx.ST_SRAM_INIT:
        if dst <= a < dst + hi - lo:
            return lo + a - dst
    raise SystemExit(f"!! {a:#x} hors de la SRAM initialisée du Syntakt")


def layout(gen, blocks):
    """Disposition de la charge utile pour une génération. Zone de transit (DST_CODE..) : l'image des deux zones
    de SRAM libérées, que le crochet de démarrage y recopie (SRAM_BANKS) ; la 1re reçoit les blocs de code, les
    SRAM_TABLES (avec leurs gardes) puis des voix du Syntakt ; la 2e, les autres voix (VOICES en tout, contenu
    initial de leur SRAM). Puis les tables du bas (sous la réplique de la SRAM), les tables du haut (TABLES_AT) et
    les tables de CHORD. Rend copies (source Syntakt, fin, destination), move (plages pour gx.move : adresses
    d'EXÉCUTION), stage (code : source, fin, transit), run(transit) -> exécution, voices (adresses d'exécution
    des voix 0..VOICES-1), et la fin de la charge utile. Le code et les tables gardent l'alignement de leur source
    modulo 4 (en SRAM) ou 8 (en SDRAM) ; les voix sont alignées sur 8, comme dans la SRAM du Syntakt."""
    banks, at = [], gx.DST_CODE
    for lo, hi in CHORD_BANKS:
        banks.append((at, lo, hi - lo))
        at += hi - lo
    stage_end = at
    stage, pads, at = [], [], gx.DST_CODE
    for lo, hi in blocks:
        if (lo - at) % 4:                          # 2 o (code aligné sur 2) : un nop, pour un désassemblage suivi
            pads.append(at)
            at += 2
        stage.append((lo, hi, at))
        at += hi - lo
    tabs = []
    for lo, hi in SRAM_TABLES:
        at += (lo - GUARD - at) % 4
        tabs.append((lo, hi, at + GUARD))
        at += hi - lo + 2 * GUARD
    voices = []
    for b0, _, n in banks:
        at = max(at, b0)
        while len(voices) < VOICES and (at + 7) // 8 * 8 + ST_VSTRIDE <= b0 + n:
            at = (at + 7) // 8 * 8
            voices.append(at)
            at += ST_VSTRIDE
        if at > b0 + n:
            raise SystemExit(f"!! code et tables pour la SRAM : {at - b0} o, plus de place")
    if len(voices) < VOICES:
        raise SystemExit(f"!! {len(voices)} voix du Syntakt seulement en SRAM")

    def run(x):
        for b0, r0, n in banks:
            if b0 <= x < b0 + n:
                return x - b0 + r0
        return x
    copies = (list(stage) + [(st_sram_src(lo - GUARD), st_sram_src(hi + GUARD), dst - GUARD) for lo, hi, dst in tabs]
              + [(st_sram_src(0x80000000 + ST_VSTRIDE * i), st_sram_src(0x80000000 + ST_VSTRIDE * (i + 1)), v)
                 for i, v in enumerate(voices)])
    high = tuple(t for c in gen for t in CATALOG[c].get("tables_high", ()))
    sdram, at = [], stage_end
    for group, limit in ((TABLES_LOW, gx.DST_SRAM), (high, None)):
        if limit is None:
            at = TABLES_AT
        for lo, hi in group:
            at += (lo - at) % 8
            sdram.append((lo, hi, at))
            at += hi - lo
        if limit is not None and at > limit:
            raise SystemExit(f"!! tables du bas jusqu'à {at:#x} : plus de place sous {limit:#x}")
    copies += sdram
    chord_at = (at + 0xff) & ~0xff
    end = chord_at + sum(hi - lo for lo, hi in CHORD_BANKS)
    # gx.move prend la 1re plage qui contient l'adresse : code et tables en SRAM du Cycles, tables en SDRAM, puis la
    # SRAM du Syntakt (tampons et table de sinus dans la SRAM du Cycles, SRAM_MAP ; le reste dans sa réplique)
    move = ([(lo, hi, run(dst)) for lo, hi, dst in stage] + [(lo, hi, run(dst)) for lo, hi, dst in tabs] + sdram
            + [*SRAM_MAP, (0x80000000, 0x80010000, gx.DST_SRAM), (*gx.ST_BSS, ST_BSS_AT)])
    # fin libre de chaque zone (transit, exécution, taille) : avec Model-TG, le code le plus appelé de la passerelle
    used = [(dst, dst + hi - lo) for lo, hi, dst in stage] + [(dst - GUARD, dst + hi - lo + GUARD) for lo, hi, dst in tabs] \
        + [(v, v + ST_VSTRIDE) for v in voices]
    tails = []
    for b0, r0, n in banks:
        top = max([e for a, e in used if b0 <= a < b0 + n] + [b0])
        top = (top + 3) & ~3
        tails.append((top, top - b0 + r0, b0 + n - top))
    return dict(copies=copies, move=tuple(move), stage=stage, pads=pads, stage_end=stage_end, run=run, banks=banks,
                voices=[run(v) for v in voices], chord_at=chord_at, end=(end + 0xff) & ~0xff, tails=tails)


def code_patches(st_img, ins, insns, lay, relocs):
    """Zone de transit corrigée : relocalisations des adresses absolues, et déplacements relatifs au PC recalculés
    pour les blocs tassés. Rend [(adresse dans la charge utile, 4 octets d'origine, 4 octets corrigés)] sans
    chevauchement, et le nombre de déplacements changés."""
    lo0, hi0 = gx.DST_CODE, lay["stage_end"]
    orig = bytearray(hi0 - lo0)
    for lo, hi, dst in lay["copies"]:
        if lo0 <= dst < hi0:
            orig[dst - lo0:dst - lo0 + hi - lo] = st_img[lo - BASE:hi - BASE]
    for a in lay["pads"]:
        orig[a - lo0:a - lo0 + 2] = b"\x4e\x71"
    new = bytearray(orig)

    def stage_of(va):
        return next(dst + va - lo for lo, hi, dst in lay["stage"] if lo <= va < hi)

    def run_of(va):
        return lay["run"](stage_of(va))
    for va, old, nv in relocs:
        at = stage_of(va) - lo0
        if new[at:at + 4] != old.to_bytes(4, "big"):
            raise SystemExit(f"!! relocalisation {va:#x}")
        new[at:at + 4] = nv.to_bytes(4, "big")
    moved = 0
    for a in sorted(insns):
        size, mn, ops = ins[a]
        branch = bool(gx.BRANCH.match(mn))
        if not branch and "%pc@" not in ops:
            continue
        t = gx.values(ops, immediates=False)[0]
        raw = st_img[a - BASE:a - BASE + size]
        if branch:                                   # déplacement 8 bits dans l'opcode, ou 16 / 32 bits ensuite
            k, n = (1, 1) if size == 2 else (2, 2) if size == 4 else (2, 4)
            base = 2
        else:                                        # (d16,PC) : mot d'extension, base = son adresse
            k = next((k for k in range(2, size - 1, 2)
                      if int.from_bytes(raw[k:k + 2], "big", signed=True) == t - (a + k)), None)
            if k is None:
                raise SystemExit(f"!! {a:#x} {mn} {ops} : déplacement relatif au PC introuvable")
            n, base = 2, k
        if int.from_bytes(raw[k:k + n], "big", signed=True) != t - (a + base):
            raise SystemExit(f"!! {a:#x} {mn} {ops} : déplacement inattendu")
        d = run_of(t) - (run_of(a) + base)
        if not -(1 << (8 * n - 1)) <= d < 1 << (8 * n - 1) or (n == 1 and d in (0, -1)):
            raise SystemExit(f"!! {a:#x} {mn} {ops} : nouveau déplacement {d} hors du champ")
        if d != t - (a + base):
            moved += 1
            at = stage_of(a) + k - lo0
            new[at:at + n] = d.to_bytes(n, "big", signed=True)
    patches, p = [], 0
    while p < len(new):
        if new[p] != orig[p]:
            if p + 4 > len(new):
                raise SystemExit("!! correction en fin de zone de transit")
            patches.append((lo0 + p, bytes(orig[p:p + 4]), bytes(new[p:p + 4])))
            p += 4
        else:
            p += 1
    return patches, moved


def chord_moved(a, lay):
    """Nouvelle adresse (charge utile) d'une adresse des tables d'ondes de CHORD en SRAM."""
    at = lay["chord_at"]
    for lo, hi in CHORD_BANKS:
        if lo <= a < hi:
            return at + a - lo
        at += hi - lo
    raise SystemExit(f"!! {a:#x} : pas une table d'ondes de CHORD")


MAP = g7.ENGINE_MAP          # table machine -> entrée des tables update/render (8 octets, 0x40118640)

# --- régulateur de charge (notes/23, notes/25) : dans la boucle des voix, l'appel update/render de chaque piste
# (0x400a7dfe..0x400a7e24) passe par un détour qui demande à la passerelle (voice_gate, voice_after) s'il faut la
# calculer ; la sonde de l'appel de la fonction audio (0x40059382) mesure la charge de chaque bloc (audio_end).
# D'ordinaire, une voix restée sous IDLE_THR (valeur absolue, échelle 32 bits de la sortie de render) pendant
# IDLE_BLOCKS blocs, sans trig, n'est plus calculée ; sous forte charge, le seuil monte et la voix la plus faible
# s'éteint par un fondu (bridge_engines.c). Vaut pour les 6 machines d'origine comme pour les machines ajoutées.
DISPATCH = (0x400a7dfe, 0x400a7e24)
TG_AFTER = (0x400a7e24, 0x400a7e2a)    # avec Model-TG : fin commune de la piste (3 instructions, 6 o)
TG_FIRST = 7                 # avec Model-TG : index de la 1re machine ajoutée (6 est son Sampler)
AMP_ROW = 0x4005a31a         # avec Model-TG : rangée d'un Amp Decay propre à une machine (constructeur 0x4005a274)
AUDIO_CALL = 0x40059382      # jsr 0x4005979e : fonction audio, appelée par l'interruption à chaque bloc
IDLE_BLOCKS = 64             # 43 ms
IDLE_THR = 1 << 13           # -108 dB sous la pleine échelle
# Régulateur (notes/25, notes/30), en % de la durée d'un bloc : coupures quand la charge SOUTENUE (moyenne lente,
# 1/2^slow par bloc, environ 170 ms) dépasse steal, jusqu'à revenir à target ; ou quand un bloc dépasse peak, jusqu'à
# revenir sous peak - margin ; fondus courts au-dessus de severe.
GOV = dict(steal=86, target=82, peak=93, margin=4, severe=96, slow=8)
# Firmware de profilage (--profile, avec --tg) : où passe le temps de l'interruption audio (notes/31 §7). Sondes
# autour de la boucle des voix et de l'étage de sortie : (site du jsr, sonde, retour, heure avant, heure après).
PROFILE = False
PROF_SITES = ((0x4005981e, "vl_probe", "prof_ret_vl", "prof_t_v0", "prof_t_v1"),
              (0x40059872, "out_probe", "prof_ret_out", "prof_t_o0", "prof_t_o1"))


def prof_sites(tg):
    """{sonde : (fonction appelée à son site dans l'image avec Model-TG, retour, heure avant, heure après)}"""
    return {name: (struct.unpack_from(">I", tg["img"], va + 2 - BASE)[0], ret, t0, t1)
            for va, name, ret, t0, t1 in PROF_SITES}
# Firmware de diagnostic (--meter) : noms des machines « pic/moyenne » (False, notes/23, notes/29) ou
# « moyenne/voix » (True : coût de la voix de chaque machine, diagnostics v6 et v7, notes/27)
METER_VOICE = False


def subset_id(codes, generic=False):
    return (not generic and LEGACY.get(tuple(codes))) or "syntakt-" + "-".join(codes)


def subsets():
    """Toutes les combinaisons de moteurs du catalogue, dans l'ordre du catalogue."""
    for r in range(1, len(CATALOG) + 1):
        yield from (list(c) for c in itertools.combinations(CATALOG, r))


# Écran MACHINES : un repère (carré de 4 px) par machine, tous les 7 px, sur une ligne en haut de la moitié droite
# (0x400a26a2..0x400a26f2 : le dernier à x = 80 + 7 k, y = 8..12). Au-delà de 7 machines, la ligne débordait sur la
# moitié gauche (image et nom de la machine). Les repères passent alors sur 2 lignes de MARKS_ROW au plus, aux mêmes
# x que les 7 d'origine, à y = 11..15 puis 4..8, entre le bord et la petite image (et son cadre, y = 17..50).
# L'axe y de cet écran monte (essai de l'utilisateur, 02/10/2026 : la 1re version, 4..8 puis 11..15, montrait les
# machines 8 et suivantes au-dessus des 7 premières) : la 1re ligne est celle du plus grand y.
MARKS_ROW = 7
MARKS = dict(x=80, dx=7, y=(11, 4), w=4, h=4)


def marks_asm(a, ins, lab, nm):
    """Repères de l'écran MACHINES sur 2 lignes (à la place de la boucle 0x400a26a2..0x400a26f2). Registres de la
    fonction : d2 = contexte de dessin, d3 = machine choisie ; d4, d5, a2, a3 sont rendus par sa fin (moveml)."""
    a.append("\t.globl\tmarks"); lab("marks")
    ins("lea 0x40070c4e, %a2"); ins("lea 0x40070efc, %a3"); ins("clr.l %d5")                 # creux, plein
    lab("1"); ins("move.l %d5, %d4"); ins(f"moveq #{MARKS['y'][0]}, %d1")
    ins(f"moveq #{MARKS_ROW}, %d0"); ins("cmp.l %d0, %d4"); ins("blt.s 2f")
    ins("sub.l %d0, %d4"); ins(f"moveq #{MARKS['y'][1]}, %d1")
    lab("2"); ins("move.l %d4, %d0"); ins("lsl.l #3, %d0"); ins("sub.l %d4, %d0")             # 7 x colonne
    ins(f"add.l #{MARKS['x']}, %d0")
    ins("move.l %d1, %d4"); ins(f"addq.l #{MARKS['h']}, %d4")
    ins("pea 0x1"); ins("move.l %d4, -(%sp)"); ins("move.l %d0, -(%sp)"); ins("move.l %d1, -(%sp)")
    ins(f"subq.l #{MARKS['w']}, %d0"); ins("move.l %d0, -(%sp)"); ins("move.l %d2, -(%sp)")
    ins("cmp.l %d5, %d3"); ins("bne.s 3f"); ins("jsr (%a3)"); ins("bra.s 4f")
    lab("3"); ins("jsr (%a2)")
    lab("4"); ins("lea 24(%sp), %sp"); ins("addq.l #1, %d5"); ins(f"moveq #{nm}, %d0"); ins("cmp.l %d5, %d0")
    ins("bne.s 1b"); ins("jmp 0x400a26f2")


def detours_asm(n, images, firsts, tg=None):
    """Détours pour n machines ajoutées (index 6..5+n), descripteurs firsts[i]..firsts[i]+4 (5 par machine).
    Avec Model-TG (tg : ses symboles), les machines ajoutées vont de 7 à 6+n (6 est son Sampler) et nos détours
    passent la main aux siens pour le reste (notes/31)."""
    last = 76 + 5 * n                                    # 1er descripteur après ceux des machines ajoutées
    first = TG_FIRST if tg else 6                        # index de la 1re machine ajoutée
    top = first + n - 1                                  # plus grand index de machine
    a = [".text"]

    def lab(s):
        a.append(s + ":")

    def ins(s):
        a.append("\t" + s)
    # état par descripteur : descripteurs ajoutés -> objets de SNARE 51..55
    lab("map_state")
    ins("moveq #76, %d1"); ins("cmp.l %d1, %d0"); ins("bcs.w 9f")
    ins(f"cmp.l #{last}, %d0"); ins("bcs.s 1f"); ins("moveq #0, %d0"); ins("rts")
    lab("1")
    ins("moveq #76, %d1"); ins("sub.l %d1, %d0")
    lab("2")
    ins("moveq #5, %d1"); ins("cmp.l %d1, %d0"); ins("bcs.s 3f"); ins("sub.l %d1, %d0"); ins("bra.s 2b")
    lab("3")
    ins("moveq #51, %d1"); ins("add.l %d1, %d0")
    lab("9"); ins("rts")
    for name, off in (("state_at", "0x40a71754"), ("state_connect", "0x40a71768")):
        a.append(f"\t.globl\t{name}"); lab(name)
        ins("move.l 4(%sp), %d0"); ins("bsr.w map_state"); ins("moveq #100, %d1"); ins("muls.l %d1, %d0")
        ins(f"add.l #{off}, %d0")
        if name == "state_at":
            ins("rts")
        else:
            ins("pea 0x40a71500"); ins("move.l 12(%sp), -(%sp)"); ins("move.l %d0, -(%sp)"); ins("jsr 0x400ddf60")
            ins("lea 12(%sp), %sp"); ins("move.l #0x40a71500, %d0"); ins("rts")
    # CC reçu -> descripteur
    a.append("\t.globl\tcc_bounds"); lab("cc_bounds")
    ins("moveq #5, %d2"); ins("cmp.l %d1, %d2"); ins("bcs.s 1f")
    if tg:                                               # le Sampler : comme Model-TG (paramètres communs)
        ins("moveq #6, %d2"); ins("cmp.l %d0, %d2"); ins("beq.s 2f")
    ins(f"moveq #{top}, %d2"); ins("cmp.l %d0, %d2"); ins("bcs.s 2f"); ins("jmp 0x4005a8fa")
    lab("1"); ins("jmp 0x4005a928")
    lab("2"); ins("jmp 0x4005a91c")
    # image montrée pour une machine
    lab("shown")
    for i in range(n):
        ins(f"moveq #{first + i}, %d1"); ins("cmp.l %d1, %d0"); ins(f"bne.s 8{i}f"); ins(f"moveq #{images[i]}, %d0"); ins("rts")
        lab(f"8{i}")
    ins("rts")
    a.append("\t.globl\tdrum_icons"); lab("drum_icons")
    ins("move.l %d3, %d0"); ins("bsr.w shown"); ins("move.l %d0, %d4"); ins("lsl.l #2, %d0"); ins("lsl.l #5, %d4")
    ins("sub.l %d0, %d4"); ins("pea 0x1"); ins("pea 0x17"); ins("pea 0x20"); ins("lea 0x40071da4, %a2")
    ins("movea.l 0x40fe32cc, %a1"); ins("adda.l %d4, %a1"); ins("move.l %a1, -(%sp)"); ins("move.l %d2, -(%sp)")
    ins("jsr (%a2)"); ins("lea 48(%sp), %sp"); ins("pea 0x1"); ins("pea 0x22"); ins("add.l 0x40fe384c, %d4")
    ins("pea 0x60"); ins("move.l %d4, -(%sp)"); ins("move.l %d2, -(%sp)"); ins("jsr (%a2)"); ins("lea 20(%sp), %sp")
    ins("jmp 0x400a2680")
    a.append("\t.globl\tsmall_icon"); lab("small_icon")
    ins("lea 10(%a0), %a0"); ins("move.l %a0, -(%sp)"); ins("move.l 16(%fp), -(%sp)"); ins("move.l %d2, %d0")
    ins("bpl.s 1f"); ins("moveq #0, %d0")
    lab("1"); ins("moveq #5, %d1"); ins("cmp.l %d0, %d1"); ins("bge.s 3f"); ins("bsr.w shown")
    ins("moveq #5, %d1"); ins("cmp.l %d0, %d1"); ins("bge.s 3f"); ins("moveq #5, %d0")
    lab("3"); ins("jmp 0x400a4dde")
    # enregistrements par machine. Une machine ou un index hors limites (piste réglée sur une machine ajoutée
    # par un autre choix de moteurs, notes/20 §5) donne celui de KICK : l'OS lirait sinon 76 o avant le tableau.
    a.append("#define REC_BASE 0x40a71540")
    a.append("#define REC_SNARE (REC_BASE + 2 * 76)")
    if tg:
        tg_records(a, ins, lab, n, firsts, first, top, tg)
    else:
        a.append("\t.globl\trecord_at"); lab("record_at")
        ins("move.l 4(%sp), %d0")
        for i in range(n):
            ins(f"moveq #{7 + i}, %d1"); ins("cmp.l %d1, %d0"); ins(f"beq.w rec_{i}")
        ins("moveq #6, %d1"); ins("cmp.l %d0, %d1"); ins("bcc.s 1f"); ins("moveq #1, %d0")
        lab("1"); ins("moveq #76, %d1"); ins("muls.l %d1, %d0"); ins("add.l #REC_BASE, %d0"); ins("rts")
        a.append("\t.globl\trecord_of"); lab("record_of")
        ins("move.l 4(%sp), %d0")
        for i in range(n):
            ins(f"moveq #{6 + i}, %d1"); ins("cmp.l %d1, %d0"); ins(f"beq.w rec_{i}")
        ins("moveq #5, %d1"); ins("cmp.l %d0, %d1"); ins("bcs.s 2f"); ins("lea 0x401091b4, %a0")
        ins("mvs.b (%a0,%d0.l), %d0"); ins("moveq #6, %d1"); ins("cmp.l %d0, %d1"); ins("bcc.s 3f")
        lab("2"); ins("moveq #1, %d0")
        lab("3"); ins("moveq #76, %d1"); ins("muls.l %d1, %d0"); ins("add.l #REC_BASE, %d0"); ins("rts")
        for i in range(n):
            lab(f"rec_{i}"); ins(f"lea {RECS + 0x60 * i:#x}, %a0"); ins(f"moveq #{firsts[i] - 51}, %d0"); ins("bra.w rec_build")
    lab("rec_build")
    ins("tst.b 76(%a0)"); ins("bne.w 9f"); ins("move.l %d2, -(%sp)"); ins("move.l %a2, -(%sp)"); ins("movea.l %a0, %a2")
    ins("move.l %d0, %d2"); ins("pea REC_SNARE"); ins("move.l %a2, -(%sp)"); ins("jsr 0x400f8f02"); ins("addq.l #8, %sp")
    ins("pea REC_SNARE + 4"); ins("pea 4(%a2)"); ins("jsr 0x400f8f02"); ins("addq.l #8, %sp")
    ins("lea REC_SNARE + 8, %a0"); ins("lea 8(%a2), %a1"); ins("moveq #16, %d1"); ins("move.l %d1, -(%sp)")
    lab("1"); ins("move.l (%a0)+, %d0"); ins("moveq #51, %d1"); ins("cmp.l %d1, %d0"); ins("blt.s 2f")
    ins("moveq #55, %d1"); ins("cmp.l %d0, %d1"); ins("blt.s 2f"); ins("add.l %d2, %d0")
    lab("2"); ins("move.l %d0, (%a1)+"); ins("subq.l #1, (%sp)"); ins("bpl.s 1b"); ins("addq.l #4, %sp")
    ins("moveq #1, %d0"); ins("move.b %d0, 76(%a2)"); ins("movea.l %a2, %a0"); ins("move.l (%sp)+, %a2")
    ins("move.l (%sp)+, %d2")
    lab("9"); ins("move.l %a0, %d0"); ins("rts")
    # potard -> descripteur : table machine -> enregistrement [1..6+n]
    if first + n > MARKS_ROW:
        marks_asm(a, ins, lab, first + n)
    a.append("\t.globl\tknob_vec"); lab("knob_vec")
    ins("move.l 36(%sp), %d0"); ins("movea.l 104(%a2), %a1"); ins(f"moveq #{top}, %d1"); ins("cmp.l %d0, %d1")
    ins("bcc.s 1f"); ins("moveq #0, %d0"); ins("rts")                    # hors limites : les potards de KICK
    lab("1"); ins(f"moveq #{first}, %d1"); ins("cmp.l %d1, %d0")
    ins("blt.s 2f"); ins(f"lea {DATA + 12 * (first + n):#x}, %a1")
    lab("2"); ins("rts")
    # machine d'un descripteur (applicabilité) et rangée du constructeur : descripteurs ajoutés -> leur machine
    a.append("\t.globl\tdesc_machine"); lab("desc_machine")
    ins("move.l 4(%sp), %d0")
    for i in range(n):
        ins(f"cmp.l #{firsts[i]}, %d0"); ins(f"bcs.s 7{i}f"); ins(f"cmp.l #{firsts[i] + 3}, %d0"); ins(f"bhi.s 7{i}f")
        ins(f"moveq #{first + i}, %d0"); ins("rts")
        lab(f"7{i}")
    ins(f"cmp.l #{last}, %d0"); ins("bcs.s 2f"); ins("moveq #0, %d0")
    lab("2"); ins("move.l %d0, %d1"); ins("lsl.l #3, %d1"); ins("lsl.l #6, %d0"); ins("sub.l %d1, %d0")
    ins(f"lea {DESCN:#x}, %a0"); ins("move.l (%a0,%d0.l), %d0"); ins("rts")
    a.append("\t.globl\tbuilder_row"); lab("builder_row")
    ins("moveq #6, %d0"); ins("cmp.l %d5, %d0"); ins("bcs.w 1f")
    for i in range(n):
        ins(f"cmp.l #{firsts[i]}, %d2"); ins(f"bcs.s 6{i}f"); ins(f"cmp.l #{firsts[i] + 3}, %d2"); ins(f"bhi.s 6{i}f")
        ins(f"moveq #{first + i}, %d5"); ins("bra.w 2f")
        lab(f"6{i}")
    lab("2"); ins("jmp 0x4005a384")
    lab("1"); ins("jmp 0x4005a346")
    if tg:
        # paramIdFor (0x4005a692) : Model-TG remplace la borne de machine (0x4005a6a6) et la branche d'Amp Decay
        # (0x4005a6b6) par ses détours pour le Sampler ; les machines ajoutées passent par le chemin d'origine,
        # avec les rangées ROWSN.
        a.append("\t.globl\tlfo_gate"); lab("lfo_gate")
        ins(f"cmpi.l #{first}, %d2"); ins("bcs.s 1f"); ins(f"cmpi.l #{top}, %d2"); ins("bhi.s 1f"); ins("jmp 0x4005a6dc")
        lab("1"); ins(f"jmp {tg['sampler_lfo_gate']:#x}")
        # constructeur des rangées (0x4005a274) : les Amp Decay propres à une machine (long[1] = 18) remplissent
        # la colonne 0 des rangées dans l'ordre des descripteurs, avec un compteur (d6) ; le Sampler n'en a pas, sa
        # rangée (6) est sautée pour que les nôtres tombent sur leurs machines (7..)
        a.append("\t.globl\tamp_row"); lab("amp_row")
        ins("moveq #6, %d0"); ins("cmp.l %d0, %d6"); ins("bne.s 1f"); ins("addq.l #1, %d6")
        lab("1"); ins("move.l %d6, %d0"); ins("addq.l #1, %d6"); ins("lsl.l #5, %d0"); ins("jmp 0x4005a320")
        a.append("\t.globl\tamp_gate"); lab("amp_gate")
        ins("cmpi.l #6, %d2"); ins("beq.s 1f")
        ins("lsl.l #5, %d2"); ins(f"lea {ROWSN:#x}, %a0"); ins("move.l (%a0,%d2.l), %d0"); ins("jmp 0x4005a6fc")
        lab("1"); ins(f"jmp {tg['sampler_amp_gate']:#x}")
    return "\n".join(a) + "\n"


def tg_records(a, ins, lab, n, firsts, first, top, tg):
    """Avec Model-TG : enregistrements par machine (0x4004df5c : index machine + 1 ; 0x4004df76 : index machine).
    Les machines ajoutées ont les leurs (construits comme seuls, rec_build) ; les autres passent par les détours de
    Model-TG (descr_hook, descr_b_hook : le Sampler, et Attack sur le potard DECAY tant que la touche est tenue).
    Comme lui, a0 et a1 sont gardés ; et comme lui, Attack, Filtre et Résonance prennent les potards DECAY, SWEEP et
    CONTOUR des machines ajoutées tant que la touche est tenue (mod_held). Ses libellés propres au Sampler sont
    écrits par apply_names dans la table d'origine (param_table) : recopiés ensuite dans DESCN, que l'OS lit."""
    for name, hook, base, oob in (("record_at", "descr_hook", first + 1, (top + 1, 1)),
                                  ("record_of", "descr_b_hook", first, (top, 0))):
        a.append(f"\t.globl\t{name}"); lab(name)
        ins("move.l 4(%sp), %d0")
        for i in range(n):
            ins(f"moveq #{base + i}, %d1"); ins("cmp.l %d1, %d0"); ins(f"beq.w tg_rec_{i}")
        ins(f"moveq #{oob[0]}, %d1"); ins("cmp.l %d0, %d1"); ins("bcc.s 1f")
        ins(f"moveq #{oob[1]}, %d0"); ins("move.l %d0, 4(%sp)")              # hors limites : KICK
        lab("1"); ins("move.l %a0, -(%sp)"); ins("move.l %a1, -(%sp)"); ins("move.l 12(%sp), -(%sp)")
        ins(f"jsr {tg[hook]:#x}"); ins("addq.l #4, %sp"); ins("bra.w tg_sync")
    for i in range(n):
        lab(f"tg_rec_{i}"); ins("move.l %a0, -(%sp)"); ins("move.l %a1, -(%sp)")
        ins(f"lea {RECS + 0x60 * i:#x}, %a0"); ins(f"moveq #{firsts[i] - 51}, %d0"); ins("bra.w tg_ours")
    lab("tg_ours")
    ins("move.l %a0, -(%sp)"); ins("move.l %d0, -(%sp)")
    ins("moveq #0, %d1"); ins(f"jsr {tg['apply_names']:#x}")              # libellés d'origine
    ins("move.l (%sp)+, %d0"); ins("movea.l (%sp)+, %a0"); ins("bsr.w rec_build")
    ins(f"tst.l {tg['mod_held']:#x}"); ins("beq.s tg_sync")
    ins("movea.l %d0, %a0"); ins(f"lea {REC_ATK:#x}, %a1"); ins("moveq #18, %d1")
    lab("1"); ins("move.l (%a0)+, (%a1)+"); ins("subq.l #1, %d1"); ins("bpl.s 1b")
    ins(f"lea {REC_ATK:#x}, %a0"); ins("moveq #0x0d, %d1"); ins("move.l %d1, 12(%a0)")      # Attack
    ins("moveq #0x0c, %d1"); ins("move.l %d1, 24(%a0)"); ins("moveq #0x0b, %d1"); ins("move.l %d1, 28(%a0)")
    ins("move.l %a0, %d0")
    lab("tg_sync")
    ins(f"lea {tg['param_table'] + 44:#x}, %a0"); ins(f"lea {DESCN + 44:#x}, %a1"); ins(f"moveq #{g7.NDESC - 1}, %d1")
    lab("2"); ins("move.l (%a0), (%a1)"); ins("move.l 4(%a0), 4(%a1)"); ins("move.l 8(%a0), 8(%a1)")
    ins(f"lea {g7.DSTRIDE}(%a0), %a0"); ins(f"lea {g7.DSTRIDE}(%a1), %a1"); ins("subq.l #1, %d1"); ins("bpl.s 2b")
    ins("movea.l (%sp)+, %a1"); ins("movea.l (%sp)+, %a0"); ins("rts")


def probe_asm(syms, prof=None):
    """Sonde de l'appel de la fonction audio par l'interruption (0x40059382) : met de côté l'adresse de retour
    (la fonction appelée voit la pile exactement comme avant), note l'heure, appelle la fonction, puis
    audio_end() (régulateur de charge, compteur du firmware de diagnostic). prof : firmware de profilage
    (PROFILE) : {site : fonction appelée} de la boucle des voix et de l'étage de sortie, entourées de la même façon."""
    g = lambda n: f"{syms[n]:#x}"
    extra = ""
    if prof:
        stamp = "\tmove.l\t0xfc07800c, %d1\n\tmove.l\t%d1, {}\n"
        extra = stamp.format(g("prof_t_fn"))
    out = f"""
	.globl	audio_probe
audio_probe:
	move.l	(%sp)+, {g('gov_ret_audio')}
	move.l	0xfc07000c, %d1
	move.l	%d1, {g('gov_t0_audio')}
{extra}	jsr	0x4005979e
	move.l	%d0, -(%sp)
	jsr	{g('audio_end')}
	move.l	(%sp)+, %d0
	move.l	{g('gov_ret_audio')}, -(%sp)
	rts
"""
    for name, (target, ret, t0, t1) in (prof or {}).items():
        out += f"""
	.globl	{name}
{name}:
	move.l	(%sp)+, {g(ret)}
	move.l	0xfc07800c, %d1
	move.l	%d1, {g(t0)}
	jsr	{target:#x}
	move.l	%d0, -(%sp)
	move.l	0xfc07800c, %d0
	move.l	%d0, {g(t1)}
	move.l	(%sp)+, %d0
	move.l	{g(ret)}, -(%sp)
	rts
"""
    return out


def dispatch_asm(syms, rnd_at):
    """Détour de l'appel update/render d'une piste dans la boucle des voix (0x400a7dfe). Registres de la boucle à
    l'entrée : d0 = borne des machines, d4 = entrée des tables, d1 = modulation de note, d6 = table update,
    d3 = sortie de la piste (32 x int32), d2 = numéro de piste, a2 = paramètres, fp = voix, a5 = voix + 0x34
    (trig de ce bloc), a3 = voix + 0x38 (trig du bloc précédent). Seuls d0, d1, a0 et a1 sont modifiés, comme
    par les appels d'origine ; voice_gate et voice_after (C) préservent les autres."""
    g = lambda n: f"{syms[n]:#x}"
    return f"""
	.globl	dispatch
dispatch:
	cmp.l	%d4, %d0
	bcs.w	9f			/* machine hors borne : rien, comme l'OS */
	move.l	%d1, -(%sp)		/* modulation de note, pour update */
	move.l	%d4, -(%sp)		/* voice_gate(piste, trig, moteur) */
	move.l	(%a5), %d0
	or.l	(%a3), %d0
	move.l	%d0, -(%sp)
	move.l	%d2, -(%sp)
	jsr	{g('voice_gate')}
	lea	12(%sp), %sp
	move.l	(%sp)+, %d1
	tst.l	%d0
	beq.s	3f
	movea.l	%d3, %a0		/* pas calculée : sortie à zéro */
	moveq	#31, %d0
2:	clr.l	(%a0)+
	subq.l	#1, %d0
	bpl.s	2b
	bra.w	9f
3:	movea.l	%d6, %a0		/* update puis render, exactement comme l'OS */
	movea.l	(%a0,%d4.l*4), %a1
	move.l	%a2, -(%sp)
	move.l	%fp, -(%sp)
	move.l	%d1, -(%sp)
	jsr	(%a1)
	move.l	%fp, -(%sp)
	move.l	%d3, -(%sp)
	lea	{rnd_at:#x}, %a0
	movea.l	(%a0,%d4.l*4), %a1
	jsr	(%a1)
	lea	20(%sp), %sp
	move.l	%d3, -(%sp)		/* voice_after(piste, sortie) */
	move.l	%d2, -(%sp)
	jsr	{g('voice_after')}
	addq.l	#8, %sp
9:	jmp	{DISPATCH[1]:#x}
"""


# comme machines/syntakt_bridge/link.ld, à l'adresse de la charge utile
LINK = """SECTIONS
{{
  .stub {stub:#x} : {{ *(.text) }}
{sram}  .bridge {bridge:#x} : {{ *(.text.bridge_update) *(.text.bridge_render) *(.text*) . = ALIGN(4); *(.rodata*) }}
  .bridge_data {data:#x} : {{ *(.data*) *(.bss*) *(COMMON) }}
  /DISCARD/ : {{ *(.comment) *(.note*) *(.eh_frame*) }}
}}
"""


def dispatch_tg_asm(syms, rnd_at, tg):
    """Avec Model-TG : le même détour (0x400a7dfe), mais les machines d'origine et le Sampler (index < 7) passent
    par le dispatch de Model-TG (sampler_dispatch : ses voix muettes, sa mesure par piste, son Sampler), qui finit
    en 0x400a7e24 ; nos moteurs passent par la passerelle, puis par la fin de son étage d'amplitude (ah_noenv :
    Attack, Filtre/Résonance, rééchantillonnage de la piste), et leur temps va sur sa page System (prof_trk).
    Toutes les pistes finissent en 0x400a7e24, où tg_after appelle voice_done (régulateur) puis refait les trois
    instructions remplacées."""
    g = lambda n: f"{syms[n]:#x}"
    return f"""
	.globl	dispatch
dispatch:
	cmp.l	%d4, %d0
	bcs.w	9f			/* machine hors borne : rien, comme l'OS */
	move.l	%d1, -(%sp)		/* modulation de note, pour update */
	move.l	%d4, -(%sp)		/* voice_gate(piste, trig, entrée) */
	move.l	(%a5), %d0
	or.l	(%a3), %d0
	move.l	%d0, -(%sp)
	move.l	%d2, -(%sp)
	jsr	{g('voice_gate')}
	lea	12(%sp), %sp
	move.l	(%sp)+, %d1
	tst.l	%d0
	beq.s	3f
	movea.l	%d3, %a0		/* pas calculée : sortie à zéro */
	moveq	#31, %d0
2:	clr.l	(%a0)+
	subq.l	#1, %d0
	bpl.s	2b
	bra.w	9f
3:	moveq	#{TG_FIRST}, %d0
	cmp.l	%d0, %d4
	bcc.s	4f
	jmp	{tg['sampler_dispatch']:#x}	/* machines d'origine, Sampler */
4:	move.l	0xfc07800c, %d0		/* minuteur de la page System de Model-TG */
	move.l	%d0, {tg['prof_ta']:#x}
	movea.l	%d6, %a0		/* update puis render, comme l'OS */
	movea.l	(%a0,%d4.l*4), %a1
	move.l	%a2, -(%sp)
	move.l	%fp, -(%sp)
	move.l	%d1, -(%sp)
	jsr	(%a1)
	move.l	%fp, -(%sp)
	move.l	%d3, -(%sp)
	lea	{rnd_at:#x}, %a0
	movea.l	(%a0,%d4.l*4), %a1
	jsr	(%a1)
	jsr	{tg['ah_noenv']:#x}		/* (sortie, voix) */
	lea	20(%sp), %sp
	move.l	0xfc07800c, %d0
	sub.l	{tg['prof_ta']:#x}, %d0
	bmi.s	9f
	lea	{tg['prof_trk']:#x}, %a0
	add.l	%d0, (%a0,%d2.l*4)
9:	jmp	{DISPATCH[1]:#x}

	.globl	tg_after
tg_after:
	move.l	%d3, -(%sp)		/* voice_done(piste, sortie) */
	move.l	%d2, -(%sp)
	jsr	{g('voice_done')}
	addq.l	#8, %sp
	move.l	(%a5), (%a3)		/* instructions remplacées en 0x400a7e24 */
	movea.l	%d3, %a1
	clr.l	%d0
	jmp	{TG_AFTER[1]:#x}
"""


def segments(parts, size):
    """Morceaux de la charge utile à ranger dans l'image (pack) : réunion des parts (adresses d'exécution), à 64 o
    près, alignée sur 4. Le reste est à zéro : le crochet de démarrage met tout à zéro puis recopie les morceaux."""
    rs = []
    for p_ in parts:
        a = int(p_["dest"], 16)
        n = len(p_["hex"]) // 2 if "hex" in p_ else p_["size"] if "size" in p_ else (lambda r: int(r[1], 16) - int(r[0], 16))(p_.get("syntakt") or p_["cycles"])
        rs.append((a & ~3, (a + n + 3) & ~3))
    out = []
    for lo, hi in sorted(rs):
        if out and lo <= out[-1][1] + 64:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    if out[0][0] < PAY or out[-1][1] > PAY + size:
        raise SystemExit("!! morceaux hors de la charge utile")
    return [(lo, hi - lo) for lo, hi in out]


# Avec Model-TG (notes/31 §7) : fonctions de la passerelle appelées à chaque bloc pour chaque piste, placées dans la
# fin libre des zones de SRAM (lay["tails"]), que le crochet de démarrage y recopie avec le reste : hors du cache
# d'instructions, qui ne les recharge plus à chaque bloc. Les plus grandes d'abord, tant qu'elles tiennent.
SRAM_HOT = ("update", "voice_after", "voice_gate", "audio_end", "govern", "render", "st_voice", "tg_keep", "voice_done")


def sram_sections(elf, tails):
    """[(transit, exécution, [fonctions])] : SRAM_HOT réparties dans les fins de zones, d'après leurs tailles."""
    size = {}
    for line in gx.run([gx.CROSS + "nm", "-S", str(elf)]).splitlines():
        p_ = line.split()
        if len(p_) == 4 and p_[3] in SRAM_HOT and p_[2] in "tT":
            size[p_[3]] = (int(p_[1], 16) + 3) & ~3
    free = [list(t) for t in tails]
    out = [[t[0], t[1], []] for t in tails]
    for f in sorted(size, key=lambda f: (-size[f], f)):
        k = next((k for k, t in enumerate(free) if t[2] >= size[f]), None)
        if k is not None:
            out[k][2].append(f)
            free[k][2] -= size[f]
    return [tuple(o) for o in out if o[2]]


def compile_code(tmp, machines, payload_longs, meter=None, rnd_at=None, nm=0, run=None, lay=None, tg=None, segs=None):
    """run : adresse d'exécution d'une fonction du Syntakt ; lay : disposition (layout()) : zones de SRAM que le
    crochet de démarrage remplit (stub.S), adresses des états de voix."""
    defs = [f"-DST_VINIT_AT={run(0x40002544):#x}", f"-DST_RESET_AT={run(0x40003ee0):#x}",
            f"-DST_PREP_AT={run(0x4000255e):#x}"] + [f"-DST_VOICE_{i}={v:#x}" for i, v in enumerate(lay["voices"])]
    for m in machines:
        defs += [f"-DUPD_{m['engine']}={run(m['update']):#x}", f"-DRND_{m['engine']}={run(m['render']):#x}"]
        if "punch_on" in m:
            defs.append(f"-DPUNCH_ON_{m['engine']}={m['punch_on']}")
        if "punch_off" in m:
            defs.append(f"-DPUNCH_OFF_{m['engine']}={m['punch_off']}")
    defs += [f"-DIDLE_THR={IDLE_THR}", f"-DIDLE_BLOCKS={IDLE_BLOCKS}"] + [f"-DGOV_{k.upper()}={v}" for k, v in GOV.items()]
    if meter:                                   # noms des machines (écran MACHINES) : « moyenne/voix »
        defs += ["-DLOAD_METER", f"-DMETER_BUF={meter:#x}", f"-DMETER_N={nm}"] + (["-DMETER_VOICE"] if METER_VOICE else [])
        if PROFILE and tg:                      # firmware de profilage (notes/31 §7)
            defs += ["-DPROFILE", f"-DTG_PROF_T0={tg['prof_t0']:#x}", "-DPROF_GOV=6"]
    defs.append(f"-DST_SRAM={gx.DST_SRAM:#x}")
    if tg:                                      # avec Model-TG (notes/31) : voir voice_gate
        defs += [f"-DTG_FIRST={TG_FIRST}"] + [f"-DTG_{k.upper()}={tg[k]:#x}" for k in ("rs_state", "rs_src", "sle_run", "sle_trk")]
    obj, stub, elf, ld = tmp / "bridge.o", tmp / "stub.o", tmp / "bridge.elf", tmp / "link.ld"
    gx.run([gx.CROSS + "gcc", *gx.CFLAGS, *defs, "-c", str(gx.SRC / "bridge_engines.c"), "-o", str(obj)])
    (s0, r0, n0), (s1, r1, n1) = lay["banks"]
    if s0 != gx.DST_CODE or s1 != s0 + n0 or n0 % 4 or n1 % 4:
        raise SystemExit("!! zones de SRAM : transit au début de la charge utile, à la suite, en mots")
    sdefs = []
    if tg:                                      # ajout rangé en morceaux après celui de Model-TG ; puis son crochet
        (tmp / "segs.inc").write_text("".join(f"\t.long\t{a:#x}, {n // 4}\n" for a, n in segs or [(PAY, 4)]))
        sdefs = ["-DPACK", f"-I{tmp}", f"-DCHAIN_TO={tg['boot_extra_hook']:#x}"]
    gx.run([gx.CROSS + "gcc", "-mcpu=54418", "-c", str(gx.SRC / "stub.S"), "-o", str(stub),
            f"-DPAYLOAD_SRC={(tg['at'] if tg else BASE + gx.IMAGE_LEN):#x}", f"-DPAYLOAD_DST={gx.DST_CODE:#x}",
            f"-DPAYLOAD_LONGS={payload_longs}",
            f"-DSRAM_RUN_AT={r0:#x}", f"-DSRAM_LONGS={n0 // 4}", f"-DSRAM2_RUN_AT={r1:#x}", f"-DSRAM2_LONGS={n1 // 4}",
            *sdefs])
    ld.write_text(LINK.format(stub=gx.CAVE, bridge=DST_BRIDGE, data=DST_BRIDGE + 0x1000, sram=""))
    gx.run([gx.CROSS + "ld", "-T", str(ld), "-o", str(elf), str(stub), str(obj)])
    hot = []
    if tg:                                      # le code le plus appelé dans la fin libre des zones de SRAM (notes/31 §7)
        hot = sram_sections(elf, lay["tails"])
        ld.write_text(LINK.format(stub=gx.CAVE, bridge=DST_BRIDGE, data=DST_BRIDGE + 0x1000, sram="".join(
            f"  .sram{k} {run_:#x} : AT({stage:#x}) {{ {' '.join(f'*(.text.{f})' for f in fns)} }}\n"
            for k, (stage, run_, fns) in enumerate(hot))))
        gx.run([gx.CROSS + "ld", "-T", str(ld), "-o", str(elf), str(stub), str(obj)])
    blobs = {}
    for sec in (".stub", ".bridge") + tuple(f".sram{k}" for k in range(len(hot))):
        out = tmp / (sec.strip(".") + ".bin")
        gx.run([gx.CROSS + "objcopy", "-O", "binary", "-j", sec, str(elf), str(out)])
        blobs[sec] = out.read_bytes()
    syms, data_end = {}, DST_BRIDGE + 0x1000
    for line in gx.run([gx.CROSS + "nm", "-S", str(elf)]).splitlines():
        parts = line.split()
        syms[parts[-1]] = int(parts[0], 16)
        if len(parts) == 4 and DST_BRIDGE + 0x1000 <= int(parts[0], 16) < 0x80000000:      # pas la SRAM
            data_end = max(data_end, int(parts[0], 16) + int(parts[1], 16))
    if len(blobs[".bridge"]) > 0x1000 or data_end > gx.DST_END:
        raise SystemExit("!! passerelle trop grande")
    # la charge utile ne recopie que le code (et les constantes) de la passerelle : ses variables doivent être en
    # BSS, donc à zéro au démarrage ; une section .data non vide y serait perdue
    for line in gx.run([gx.CROSS + "objdump", "-h", str(obj)]).splitlines():
        f = line.split()
        if len(f) > 2 and f[1].startswith(".data") and int(f[2], 16):
            raise SystemExit(f"!! passerelle : données initialisées ({f[1]}), non recopiées dans la charge utile")
    src, o, e, b = tmp / "det.S", tmp / "det.o", tmp / "det.elf", tmp / "det.bin"
    src.write_text(detours_asm(len(machines), [m["image"] for m in machines], [76 + 5 * i for i in range(len(machines))], tg)
                   + probe_asm(syms, prof_sites(tg) if PROFILE and tg and meter else None)
                   + (dispatch_tg_asm(syms, rnd_at, tg) if tg else dispatch_asm(syms, rnd_at)))
    gx.run([gx.CROSS + "gcc", "-mcpu=54418", "-c", str(src), "-o", str(o)])
    gx.run([gx.CROSS + "ld", "-Ttext", f"{STUBS:#x}", "-o", str(e), str(o)])
    gx.run([gx.CROSS + "objcopy", "-O", "binary", "-j", ".text", str(e), str(b)])
    ssyms = {p[-1]: int(p[0], 16) for p in (l.split() for l in gx.run([gx.CROSS + "nm", str(e)]).splitlines()) if len(p) == 3}
    stubs = b.read_bytes()
    if STUBS + len(stubs) > DATA:
        raise SystemExit("!! détours trop grands")
    blobs["hot"] = [(stage, blobs[f".sram{k}"], fns) for k, (stage, _, fns) in enumerate(hot)]
    return blobs, syms, stubs, ssyms


def own_code(tmp, machines, rnd_at, lay, tg, own):
    """Avec des machines à nous après les moteurs (own, build_tweak) : la passerelle n'est pas recompilée, ses octets
    et ses symboles viennent du tweak versionné des mêmes moteurs (own["bridge"] : compilée par m68k-elf-gcc 16.2,
    régulateur en assembleur, testée sur la machine) ; seuls le crochet de démarrage et les détours, pour toutes les
    machines, sont assemblés ici. Le crochet (stub.S, APLIB) décompresse la charge utile puis appelle son 2e étage
    (BOOT2, rangé dans la charge utile en own["boot2"] : tables d'ondes de CHORD reprises en SRAM, CHORD_AT, puis
    code du Syntakt en SRAM) : il ne tiendrait pas en entier devant l'arpégiateur (STUB_END). Rend (blobs, syms, stubs,
    ssyms) comme compile_code, plus blobs[".boot2"]."""
    (s0, r0, n0), (s1, r1, n1) = lay["banks"]
    if s0 != gx.DST_CODE or s1 != s0 + n0 or n0 % 4 or n1 % 4:
        raise SystemExit("!! zones de SRAM : transit au début de la charge utile, à la suite, en mots")
    lo, hi = own["boot2"]
    blobs = {}
    for name, at, defs in ((".stub", gx.CAVE, ["-DAPLIB", f"-DAFTER={lo:#x}",
                                              f"-DPAYLOAD_SRC={(tg['at'] if tg else BASE + gx.IMAGE_LEN):#x}",
                                              *([f"-DCHAIN_TO={tg['boot_extra_hook']:#x}"] if tg else [])]),
                           (".boot2", lo, ["-DBOOT2", f"-DCHORD_AT={lay['chord_at']:#x}", f"-DSRAM_RUN_AT={r0:#x}",
                                           f"-DSRAM_LONGS={n0 // 4}", f"-DSRAM2_RUN_AT={r1:#x}",
                                           f"-DSRAM2_LONGS={n1 // 4}"])):
        o, elf, b = tmp / f"{name[1:]}.o", tmp / f"{name[1:]}.elf", tmp / f"{name[1:]}.bin"
        gx.run([gx.CROSS + "gcc", "-mcpu=54418", "-c", str(gx.SRC / "stub.S"), "-o", str(o),
                f"-DPAYLOAD_DST={gx.DST_CODE:#x}", *defs])
        gx.run([gx.CROSS + "ld", "-Ttext", f"{at:#x}", "-o", str(elf), str(o)])
        gx.run([gx.CROSS + "objcopy", "-O", "binary", "-j", ".text", str(elf), str(b)])
        blobs[name] = b.read_bytes()
    if lo % 4 or lo + len(blobs[".boot2"]) > hi:
        raise SystemExit(f"!! 2e étage du crochet : {len(blobs['.boot2'])} o, place {lo:#x}..{hi:#x}")
    br = own["bridge"]
    blobs.update({".bridge": br["bridge"], "hot": br["hot"]})
    stubs, ssyms = assemble_detours(tmp, machines, br["syms"], rnd_at, tg)
    return blobs, br["syms"], stubs, ssyms


def detours_text(machines, syms, rnd_at, tg):
    """Texte des détours (à STUBS) pour ces machines ajoutées, comme compile_code."""
    return (detours_asm(len(machines), [m["image"] for m in machines], [76 + 5 * i for i in range(len(machines))], tg)
            + probe_asm(syms) + (dispatch_tg_asm(syms, rnd_at, tg) if tg else dispatch_asm(syms, rnd_at)))


def assemble_detours(tmp, machines, syms, rnd_at, tg, text=None):
    """Détours assemblés à STUBS : (octets, symboles)."""
    src, o, e, b = tmp / "det.S", tmp / "det.o", tmp / "det.elf", tmp / "det.bin"
    src.write_text(text or detours_text(machines, syms, rnd_at, tg))
    gx.run([gx.CROSS + "gcc", "-mcpu=54418", "-c", str(src), "-o", str(o)])
    gx.run([gx.CROSS + "ld", "-Ttext", f"{STUBS:#x}", "-o", str(e), str(o)])
    gx.run([gx.CROSS + "objcopy", "-O", "binary", "-j", ".text", str(e), str(b)])
    ssyms = {p[-1]: int(p[0], 16) for p in (l.split() for l in gx.run([gx.CROSS + "nm", str(e)]).splitlines()) if len(p) == 3}
    stubs = b.read_bytes()
    if STUBS + len(stubs) > DATA:
        raise SystemExit("!! détours trop grands")
    return stubs, ssyms


GX_ROOTS = tuple(gx.ROOTS)
_ANALYSIS = {}


def analyse(st_img, gen):
    """Pour une génération (moteurs dont la copie contient le code) : fermeture, blocs, disposition et corrections
    du code du Syntakt copié. Laisse gx.SEGMENTS sur cette disposition (gx.move : adresses d'exécution)."""
    gx.ROOTS = GX_ROOTS + tuple(x for c in gen for x in (CATALOG[c]["update"], CATALOG[c]["render"],
                                                        *CATALOG[c].get("roots", ())))
    gx.IMM_ADDR = set(GX_IMM_ADDR) | g8.IMM_ADDR | {a for c in gen for a in CATALOG[c].get("imm", ())}
    key = (gen, PAY)
    if key not in _ANALYSIS:
        with tempfile.TemporaryDirectory() as d:
            ins = gx.disasm(st_img, pathlib.Path(d))
        funcs, insns = gx.closure(ins)
        code = (CODE_START, max(CATALOG[c].get("code_end", 0) for c in gen))
        if not all(code[0] <= a < code[1] for a in insns):
            raise SystemExit(f"!! code hors de la plage prévue : {[hex(a) for a in sorted(insns) if not code[0] <= a < code[1]][:4]}")
        # Garde-fou : une adresse de code prise par « lea » (pointeur de fonction) doit être dans la fermeture,
        # sinon ses adresses ne sont pas relocalisées (SY BITS : « lea 0x40006646,%fp », notes/21).
        missed = sorted({v for a in insns if ins[a][1] == "lea" for v in gx.values(ins[a][2], immediates=False)
                         if gx.ST_CODE[0] <= v < code[1] and v in ins and v not in insns})
        if missed:
            raise SystemExit(f"!! pointeurs de fonction non suivis (à ajouter à roots) : {[hex(v) for v in missed]}")
        blocks = code_blocks(ins, insns)
        lay = layout(gen, blocks)
        gx.SEGMENTS, gx.PC_OK = lay["move"], blocks
        relocs = gx.relocations(st_img, ins, insns)
        patches, moved = code_patches(st_img, ins, insns, lay, relocs)
        _ANALYSIS[key] = dict(lay=lay, blocks=blocks, patches=patches, moved=moved, relocs=len(relocs),
                              funcs=len(funcs), code_bytes=sum(ins[a][0] for a in insns))
    an = _ANALYSIS[key]
    gx.SEGMENTS, gx.PC_OK = an["lay"]["move"], an["blocks"]
    return an


# --- version combinée avec Model-TG (notes/31) -------------------------------------------------------------------
TG_TWEAK = DEV / "30-model-tg-st.json"   # Model-TG pour la combinaison (tools/gen_model_tg.py) : appliqué avant nous
BOOT_CALL = 0x40000530       # jsr 0x400004b2 (remise à zéro du BSS) ; Model-TG en fait « jsr boot_extra_hook »
END_LIMIT = 0x40200000       # l'image décompressée doit finir sous la zone de travail du bootstrap


def tg_context(img):
    """Model-TG pour la combinaison : son tweak, l'image après ses écritures, son bloc de code et ses symboles."""
    import build                                 # tools/build.py
    tw = json.loads(TG_TWEAK.read_text(encoding="utf-8"))
    ap_ = tw["append"]
    if len(ap_["parts"]) != 1 or ap_["dest"] != ap_["at"] or int(ap_["at"], 16) != BASE + len(img):
        raise SystemExit("!! ajout de Model-TG inattendu (un seul morceau, en place, juste après l'OS)")
    cur, _ = build.apply_writes(img, [tw])
    tg = {k: int(v, 16) for k, v in tw["symbols"].items()}
    tg.update(img=bytes(cur), blob=bytes.fromhex(ap_["parts"][0]["hex"]), blob_at=int(ap_["at"], 16),
              at=int(ap_["at"], 16) + ap_["size"], id=tw["id"], symbols_hex=tw["symbols"])
    if tg["at"] != tg["reserved_end"] or tg["REGION_END"] - 0x08000000 > PAY_TG:
        raise SystemExit("!! Model-TG : fin de son bloc ou de sa zone d'échantillons inattendue")
    return tg


def tweak_id(codes, generic=False, meter=False, tg=False):
    if tg:
        if meter:
            return "syntakt-tg-profile" if PROFILE else "syntakt-tg-meter"
        return "syntakt-tg-" + "-".join(codes)
    return "syntakt-meter" if meter else subset_id(codes, generic)


def build_tweak(img, st_img, codes, generic=False, meter=False, tg=None, own=None):
    """Tweak pour ces moteurs. tg : Model-TG (tg_context) pour la version combinée, à construire avec set_base(PAY_TG).
    own : nos machines après les moteurs (machine MACRO, tools/gen_macro_syntakt.py, notes/50) : dict(machines=[comme
    CATALOG, avec update et render : adresses], bridge=passerelle reprise (own_code), parts=[morceaux de la charge
    utile], end=fin de la charge utile). La charge utile est alors rangée compressée (append.compress), et les tables
    d'ondes de CHORD reprises en SRAM au démarrage au lieu d'être recopiées de TON MAIN OS."""
    first = TG_FIRST if tg else 6
    machines = [dict(CATALOG[c], code=c, index=first + i) for i, c in enumerate(codes)]
    if own:
        machines += [dict(m, index=first + len(machines) + i) for i, m in enumerate(own["machines"])]
    n = len(machines)
    if not 1 <= n <= MAX_EXTRA:
        raise SystemExit("!! nombre de moteurs")
    cur = tg["img"] if tg else img              # l'image telle que nos écritures la trouvent
    u32 = lambda va: struct.unpack_from(">I", cur, va - BASE)[0]
    check_sram_map(img, st_img)
    an = analyse(st_img, generation(codes))
    lay = an["lay"]
    size = (own["end"] if own else lay["end"]) - gx.DST_CODE
    nm = first + n                              # machines : 6 d'origine, le Sampler avec Model-TG, puis les nôtres
    top = nm - 1                                # plus grand index de machine
    names_at, upd_at, rnd_at, vec_at, map_at = DATA, DATA + 4 * nm, DATA + 8 * nm, DATA + 12 * nm, DATA + 16 * nm
    strings = [m["name"] for m in machines] + [k[i] for m in machines for k in m["knobs"] for i in (0, 1)]
    at, addr = map_at + ((nm + 3) & ~3), {}
    for s_ in strings:
        if s_ not in addr:
            addr[s_] = at
            at += len(s_) + 1
    meter_at = at                               # compteur : un nom de 8 o par machine (5 caractères au plus)
    if meter:
        at += 8 * nm

    def compile_(d, segs=None):
        if own:
            return own_code(pathlib.Path(d), machines, rnd_at, lay, tg, own)
        return compile_code(pathlib.Path(d), machines, size // 4, meter_at if meter else None, rnd_at, nm, gx.move,
                            lay, tg, segs)
    with tempfile.TemporaryDirectory() as d:
        blobs, syms, stubs, ssyms = compile_(d)

    if tg:                                      # noms : ceux de Model-TG (le Sampler montre son échantillon)
        blob_u32 = lambda va: struct.unpack_from(">I", tg["blob"], va - tg["blob_at"])[0]
        names = [blob_u32(tg["sampler_name_table"] + 4 * i) for i in range(7)] + [addr[m["name"]] for m in machines]
    else:
        names = [u32(g7.NAMES + 4 * i) for i in range(6)] + [addr[m["name"]] for m in machines]
    if meter:
        names = [meter_at + 8 * m for m in range(nm)]
    pad = [u32(g7.UPDATE_TAB)] * (first - 6), [u32(g7.RENDER_TAB)] * (first - 6)   # entrée 6 du Sampler : jamais lue
    upd = [u32(g7.UPDATE_TAB + 4 * i) for i in range(6)] + pad[0] + [m["update"] if "code" not in m else
                                                                      syms[f"bridge_update_{m['engine']}"] for m in machines]
    rnd = [u32(g7.RENDER_TAB + 4 * i) for i in range(6)] + pad[1] + [m["render"] if "code" not in m else
                                                                      syms[f"bridge_render_{m['engine']}"] for m in machines]
    data = bytearray()
    for t in (names, upd, rnd, range(1, nm + 1)):
        data += b"".join(g7.be32(x) for x in t)
    data += cur[MAP - BASE:MAP - BASE + 6] + bytes(range(6, nm)) + bytes(((nm + 3) & ~3) - nm)   # machine -> entrée
    for s_ in addr:
        data += s_.encode("ascii") + b"\0"
    if meter:
        data += b"--/--\0\0\0" * nm
    if DATA + len(data) > DESCN:
        raise SystemExit("!! données")

    new = bytearray()
    for m in machines:
        for k, (long_, short, default, *rng) in enumerate(m["knobs"]):
            e = bytearray(img[g7.DESC + (g7.SNARE_DESC + k) * g7.DSTRIDE - BASE:][:g7.DSTRIDE])
            e[0x00:0x04] = g7.be32(6)                 # « propre à une machine » ; rattaché à la sienne par les détours
            if rng:                                    # plage propre (sinon 0..127, comme SNARE)
                e[0x08:0x0c], e[0x0c:0x10] = g7.be32(rng[0] << 8), g7.be32(rng[1] << 8)
            e[0x10:0x14] = g7.be32(default << 8)
            e[0x2c:0x30] = g7.be32(addr[long_])
            e[0x34:0x38] = g7.be32(addr[short])
            new += e
        e = bytearray(img[g7.DESC + (g7.SNARE_DESC + 4) * g7.DSTRIDE - BASE:][:g7.DSTRIDE])
        e[0x10:0x14] = g7.be32(m["decay"] << 8)
        new += e
    ndesc = g7.NDESC + 5 * n

    writes = []

    def w(va, old, new_):
        if cur[va - BASE:va - BASE + len(old)] != old:
            raise SystemExit(f"!! {va:#x} : {old.hex()} attendu, {cur[va - BASE:va - BASE + len(old)].hex()} trouvé")
        writes.append({"off": va - BASE, "old": old.hex(), "new": new_.hex()})

    def moveq(va, old, new_, reg_byte):
        w(va, bytes([reg_byte, old]), bytes([reg_byte, new_]))

    def jmp(va):
        return bytes.fromhex("4ef9") + g7.be32(va)

    stub = blobs[".stub"]                       # (avec Model-TG, recompilé plus bas avec la liste des morceaux)
    w(gx.CAVE, b"\xff" * len(stub), stub)
    red = sprites.redirect_write(gx.CAVE)
    w(BASE + red["off"], bytes.fromhex(red["old"]), bytes.fromhex(red["new"]))
    if tg:                                      # notre crochet, puis le sien (stub.S, CHAIN_TO)
        w(BOOT_CALL + 2, g7.be32(tg["boot_extra_hook"]), g7.be32(gx.CAVE))
    else:
        w(gx.HOOK, bytes.fromhex(gx.HOOK_OLD), bytes.fromhex("4ef9") + g7.be32(gx.CAVE) + bytes.fromhex("4e71"))
    # Avec Model-TG, la table des noms est la sienne (0x400a2614) ; la table render d'origine n'est plus lue que par
    # son dispatch (ses 6 entrées), et sa branche d'Amp Decay (0x4005a6b6) remplace l'une des 5 lectures de ROWS.
    names_src = tg["sampler_name_table"] if tg else g7.NAMES
    moved = {g7.DESC: DESCN, g7.DESC + 8: DESCN + 8, g7.DESC + 0x20: DESCN + 0x20, g7.ROWS: ROWSN, g7.CCROWS: CCROWSN,
             names_src: names_at, g7.UPDATE_TAB: upd_at, g7.RENDER_TAB: rnd_at, MAP: map_at}
    want = {g7.DESC: 34, g7.DESC + 8: 1, g7.DESC + 0x20: 2, g7.ROWS: 4 if tg else 5, g7.CCROWS: 2, MAP: 1,
            g7.RENDER_TAB: 0 if tg else 1}
    for old, new_ in moved.items():
        rs = g7.refs32(cur, old)
        if len(rs) != want.get(old, 1):
            raise SystemExit(f"!! références à {old:#x} : {len(rs)}")
        for va in rs:
            if DISPATCH[0] <= va < DISPATCH[1]:
                continue                        # dans le code remplacé par le détour des voix muettes
            w(va, g7.be32(old), g7.be32(new_))
    w(DISPATCH[0], cur[DISPATCH[0] - BASE:DISPATCH[0] - BASE + 6], jmp(ssyms["dispatch"]))
    if tg:
        w(TG_AFTER[0], bytes.fromhex("269522434280"), jmp(ssyms["tg_after"]))
    jumps = g7.JUMPS + g8.JUMPS8
    for va in g7.BOUNDS:
        if va in {j[0] for j in jumps}:
            continue
        b0, b1 = cur[va - BASE], cur[va - BASE + 1]
        if b0 & 0xf1 != 0x70 or b1 not in (75, 76):
            raise SystemExit(f"!! {va:#x}")
        moveq(va, b1, b1 + 5 * n, b0)
    # bornes « machine <= 5 » (Model-TG en a déjà mis certaines à 6)
    for va, reg in ((0x400a7dba, 0x72), (0x400a7df4, 0x70), (0x4005a6a6, 0x72), (0x400147a4, 0x70),
                    (0x400148aa, 0x72), (0x400148b2, 0x70), (0x400a25e0, 0x70)):
        if tg and va == 0x4005a6a6:
            continue                            # son détour sampler_lfo_gate : chaîné par lfo_gate (plus bas)
        if cur[va - BASE] != reg or cur[va - BASE + 1] not in (5, 6):
            raise SystemExit(f"!! borne {va:#x}")
        moveq(va, cur[va - BASE + 1], top, reg)
    moveq(0x4005a572, 5, 6, 0x72)                           # champ machine « propre à une machine » : <= 6
    w(0x4005a2b8, bytes.fromhex("487800c0"), bytes.fromhex("4878") + (32 * nm).to_bytes(2, "big"))
    if nm > MARKS_ROW:                                      # repères sur 2 lignes (marks_asm)
        w(0x400a26a2, bytes.fromhex("7850428545f9"), jmp(ssyms["marks"]))
    else:
        moveq(0x400a26e8, cur[0x400a26e8 - BASE + 1], nm, 0x70)
    if not tg:                                  # icônes bornées : SNARE au-delà de 5 (avec Model-TG, CHORD, comme lui)
        for va in (0x4001b69c, 0x400a40a6, 0x400a4fb0):
            moveq(va, 5, 1, 0x70)
    chained = {0x4004df5c: "descr_hook", 0x4004df76: "descr_b_hook"}
    for va, old, sym in jumps:
        old = bytes.fromhex(old)
        if tg and va in chained:                # ses détours, appelés par les nôtres
            old = jmp(tg[chained[va]])
        w(va, old, jmp(ssyms[sym]))
    if tg:
        w(AMP_ROW, bytes.fromhex("20065286eb88"), jmp(ssyms["amp_row"]))     # move.l d6,d0 ; addq #1,d6 ; lsl #5,d0
        w(0x4005a6a6, jmp(tg["sampler_lfo_gate"]), jmp(ssyms["lfo_gate"]))
        w(0x4005a6b6, jmp(tg["sampler_amp_gate"]), jmp(ssyms["amp_gate"]))
    for va, old, sym in g7.CALLS:
        w(va, bytes.fromhex(old), bytes.fromhex("4eb9") + g7.be32(ssyms[sym]) + bytes.fromhex("4e71"))
    # sonde du régulateur de charge autour de l'appel de la fonction audio (jsr abs.l)
    w(AUDIO_CALL, bytes.fromhex("4eb94005979e"), bytes.fromhex("4eb9") + g7.be32(ssyms["audio_probe"]))
    if PROFILE and tg and meter:                # firmware de profilage : sondes de la boucle des voix et de la sortie
        for va, name, *_ in PROF_SITES:
            w(va, cur[va - BASE:va - BASE + 6], bytes.fromhex("4eb9") + g7.be32(ssyms[name]))
    # tables d'ondes de CHORD : lues dans la charge utile, leur place en SRAM reçoit le code du Syntakt
    ptrs = [u32(CHORD_PTRS + 4 * i) for i in range(31)]
    w(CHORD_PTRS, b"".join(g7.be32(x) for x in ptrs), b"".join(g7.be32(chord_moved(x, lay)) for x in ptrs))

    parts = [{"dest": f"{dst:#x}", "syntakt": [f"{lo:#x}", f"{hi:#x}"]} for lo, hi, dst in lay["copies"]]
    for lo, hi, dst in gx.ST_SRAM_INIT:
        parts.append({"dest": f"{gx.move(dst):#x}", "syntakt": [f"{lo:#x}", f"{hi:#x}"]})
    parts += [{"dest": f"{a:#x}", "hex": "4e71"} for a in lay["pads"]]
    for lo, hi in CHORD_BANKS if not own else ():    # tables d'ondes de CHORD, depuis le MAIN OS de l'utilisateur
        src = next(s_ + lo - d_ for s_, e_, d_ in CY_SRAM_INIT if d_ <= lo and hi <= d_ + e_ - s_)
        parts.append({"dest": f"{chord_moved(lo, lay):#x}", "cycles": [f"{src:#x}", f"{src + hi - lo:#x}"]})
    parts += [{"dest": f"{stage:#x}", "hex": code.hex()} for stage, code, _ in blobs["hot"]]   # avec Model-TG
    parts += [
        {"dest": f"{DST_BRIDGE:#x}", "hex": blobs[".bridge"].hex()},
        {"dest": f"{STUBS:#x}", "hex": stubs.hex()},
        {"dest": f"{DATA:#x}", "hex": bytes(data).hex()},
        {"dest": f"{DESCN:#x}", "cycles": [f"{g7.DESC:#x}", f"{g7.DESC + g7.NDESC * g7.DSTRIDE:#x}"]},
        {"dest": f"{DESCN + g7.NDESC * g7.DSTRIDE:#x}", "hex": bytes(new).hex()},
    ] + (own["parts"] + [{"dest": f"{own['boot2'][0]:#x}", "hex": blobs[".boot2"].hex()}] if own else [])
    reloc = [[f"{at_:#x}", old.hex(), new_.hex()] for at_, old, new_ in an["patches"]]
    # descripteurs : copie de ceux de TON MAIN OS, puis ce qui change (mots de 4 o) : le max d'Algorithm (choix de la
    # machine) et, avec Model-TG, ses retouches (Attack, Filtre, Résonance sur toutes les machines)
    lo_, hi_ = g7.DESC - BASE, g7.DESC - BASE + g7.NDESC * g7.DSTRIDE
    final, orig = bytearray(cur[lo_:hi_]), img[lo_:hi_]
    alg = g7.ALG_DESC * g7.DSTRIDE + 0x0c
    if struct.unpack_from(">I", final, alg)[0] != (first - 1) << 8:
        raise SystemExit("!! max du paramètre Algorithm")
    struct.pack_into(">I", final, alg, top << 8)
    reloc += [[f"{DESCN + k:#x}", orig[k:k + 4].hex(), final[k:k + 4].hex()]
              for k in range(0, len(final), 4) if final[k:k + 4] != orig[k:k + 4]]
    append = {
        "at": f"{(tg['at'] if tg else BASE + gx.IMAGE_LEN):#x}",
        "dest": f"{gx.DST_CODE:#x}",
        "size": size,
        "syntakt": {"os": dict(syntakt.OFFICIAL), "section": 7, "section_sha256": syntakt.DSP_SHA256},
        "parts": parts,
        "reloc": reloc,
    }
    if own:                                     # rangé compressé (stub.S, APLIB) : taille connue au build
        append["compress"] = "aplib"
    elif tg:                                    # rangé en morceaux (stub.S, PACK) : recompilé avec leur liste
        segs = segments(parts, size)
        append["pack"] = [[f"{a_:#x}", n_] for a_, n_ in segs]
        if tg["at"] + sum(n_ for _, n_ in segs) > END_LIMIT:
            raise SystemExit(f"!! ajout de {sum(n_ for _, n_ in segs)} o : l'image dépasserait {END_LIMIT:#x}")
        with tempfile.TemporaryDirectory() as d:
            blobs2, _, stubs2, _ = compile_(d, segs)
        if blobs2[".bridge"] != blobs[".bridge"] or stubs2 != stubs or blobs2["hot"] != blobs["hot"]:
            raise SystemExit("!! recompilation avec les morceaux : passerelle différente")
        stub = blobs2[".stub"]
        writes[0] = {"off": gx.CAVE - BASE, "old": (b"\xff" * len(stub)).hex(), "new": stub.hex()}
    if len(stub) > sprites.zone(gx.CAVE)[1] or gx.CAVE + len(stub) > STUB_END:
        raise SystemExit(f"!! crochet de démarrage trop grand pour sa place ({len(stub)} o)")
    writes.sort(key=lambda x: x["off"])
    for a_, b_ in zip(writes, writes[1:]):
        if a_["off"] + len(a_["new"]) // 2 > b_["off"]:
            raise SystemExit(f"!! écritures qui se chevauchent en {BASE + b_['off']:#x}")

    tid = tweak_id(codes, generic, meter, bool(tg))
    ids = ({"sdvintage-snare", "sdvintage-exact", "sdvintage-7th", "syntakt-vintage", "syntakt-meter", "model-tg"}
           | {subset_id(c) for c in subsets()})
    if tg:
        ids |= {"syntakt-tg-meter"} | {tweak_id(c, tg=True) for c in subsets()}
    which = ", ".join(f"{m['name']} = {m['label']} (machine {m['index'] + 1})" for m in machines)
    out = {
        "id": tid,
        "order": ((92 if PROFILE else 91) if meter else 31) if tg else (90 if meter else 24),
        "name": (("DIAGNOSTIC, profil de l'interruption audio. " if PROFILE and tg else "DIAGNOSTIC, compteur de charge. ")
                 if meter else "") + ("Model-TG + " if tg else "") +
                "Vrais moteurs du Syntakt en machines ajoutées : " + ", ".join(f"{m['name']} ({m['label']})" for m in machines),
        "description": ([
            "FIRMWARE DE PROFILAGE (notes/31 §7) : l'écran MACHINES affiche « pic/moyenne », en % de la durée d'un",
            "bloc, mis à jour toutes les 0,5 s : machine 1 tout (comme la page System de Model-TG), 2 début de",
            "l'interruption, 3 fonction audio avant les voix, 4 boucle des voix, 5 entre les voix et la sortie,",
            "6 sortie (mix, effets d'envoi et master), 7 notre compteur habituel. À n'utiliser que pour mesurer.",
        ] if meter and PROFILE and tg else [
            "FIRMWARE DE DIAGNOSTIC (notes/23, notes/27) : l'écran MACHINES affiche, pour chaque machine,",
            "« moyenne/voix » (charge moyenne, coût de la voix qui joue cette machine) ou « pic/moyenne » de la",
            "charge audio, en % de la durée d'un bloc de 32 échantillons, mis à jour toutes les 0,5 s.",
            "À n'utiliser que pour mesurer.",
        ] if meter else []) + ([
            "Version combinée avec Model-TG (notes/31) : s'ajoute après model-tg-st, le Sampler reste la 7e machine,",
            "les moteurs du Syntakt suivent : " + which + ".",
        ] if tg else [
            "Moteurs du Syntakt (OS 1.42 ou 1.41) extraits AU BUILD de TON Syntakt_OS1.42.syx, en machines ajoutées après",
            "les 6 d'origine (notes/20) : " + which + ".",
        ]) + [
            "Potards propres, noms et défauts du Syntakt. Généré par tools/gen_syntakt_engines.py" + (" --tg." if tg else "."),
            "Demande build.py --syntakt Syntakt_OS1.42.syx. Aucun octet Elektron dans ce fichier.",
        ],
        "gov": {k: f"{syms[k]:#x}" for k in sorted(syms) if k.startswith(("gov_", "prof_")) or k in ("audio_end", "voice_gate", "voice_after")},
        "device": "Model:Cycles",
        "os": "1.13",
        "section": 3,
    }
    if tg:
        out["requires"] = [tg["id"]]
    out.update({"conflicts": sorted(ids - {tid}), "writes": writes, "append": append})
    if not tg:                    # envoi à l'USB à heure fixe (notes/35), boucle des voix (notes/36) ; la version
        out = usb_steady.add_to(out)          # combinée les a par model-tg-st
        out = voice_loop.add_to(out)
    if own:                       # régulateur en assembleur : déjà dans la passerelle reprise (own_code)
        out["gov"] = own["bridge"]["gov"]
        out["description"].append(gov_asm.NOTE)
    elif not meter:               # régulateur en assembleur (notes/36) ; le compteur de diagnostic est dans audio_end
        out = gov_asm.add_to(out, tg and tg["symbols_hex"])
    return out, ndesc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="model-cycles_OS1.13.syx officiel")
    ap.add_argument("--syntakt", required=True, help="Syntakt_OS1.42.syx (ou 1.41) officiel")
    ap.add_argument("--engines", help="moteurs du catalogue, séparés par des virgules : " + ",".join(CATALOG))
    ap.add_argument("--all", action="store_true", help="toutes les combinaisons qui n'ont pas leur tweak d'origine")
    ap.add_argument("--generic", action="store_true", help="même pour une combinaison de LEGACY (vérification), avec --out")
    ap.add_argument("--out", help="fichier de sortie (sinon tweaks/…/24-<id>.json)")
    ap.add_argument("--check", action="store_true", help="vérifie que les JSON versionnés correspondent")
    ap.add_argument("--meter", action="store_true", help="firmware de diagnostic : compteur de charge (notes/23)")
    ap.add_argument("--tg", action="store_true", help="version combinée avec Model-TG (notes/31) : 31-syntakt-tg-….json")
    ap.add_argument("--profile", action="store_true", help="avec --tg --meter : profil de l'interruption audio (notes/31 §7)")
    args = ap.parse_args()
    global PROFILE
    PROFILE = args.profile
    img = g7.cycles_main(args.cycles)
    if len(img) != gx.IMAGE_LEN:
        raise SystemExit("!! ce n'est pas le MAIN OS 1.13 officiel")
    if args.all:
        todo = [c for c in subsets() if tuple(c) not in LEGACY]
    else:
        want = args.engines.split(",")
        if set(want) - set(CATALOG):
            raise SystemExit(f"!! moteurs inconnus : {set(want) - set(CATALOG)}")
        todo = [[c for c in CATALOG if c in want]]
    st_img = syntakt.dsp_image(args.syntakt)
    tg = None
    if args.tg:
        tg = tg_context(img)
        set_base(PAY_TG)
    bad = 0
    for codes in todo:
        if tuple(codes) in LEGACY and not args.generic and not args.meter:
            raise SystemExit(f"!! {codes} : tweak d'origine {LEGACY[tuple(codes)]} (ou --generic)")
        gen = generation(codes)
        if (gen, PAY) not in _ANALYSIS:
            an = analyse(st_img, gen)
            print(f"  Syntakt jusqu'à {CATALOG[gen[-1]]['label']} : {an['funcs']} fonctions, {an['code_bytes']} o de code,"
                  f" {len(an['blocks'])} blocs, {an['relocs']} relocalisations, {an['moved']} sauts recalculés")
        tweak, ndesc = build_tweak(img, st_img, codes, args.generic, args.meter, tg)
        path = pathlib.Path(args.out) if args.out else DEV / f"{tweak['order']}-{tweak['id']}.json"
        text = json.dumps(tweak, indent=1) + "\n"
        packed = f", rangée en {sum(n for _, n in tweak['append']['pack'])} o" if "pack" in tweak["append"] else ""
        print(f"  {tweak['id']} : {len(tweak['writes'])} écritures, {ndesc} descripteurs, charge utile "
              f"{tweak['append']['size']} o{packed}")
        if args.check:
            ok = path.exists() and path.read_text(encoding="utf-8") == text
            print(f"    {path.name} {'est à jour' if ok else 'NE CORRESPOND PAS (autre GCC ?)'}")
            bad += not ok
        else:
            path.write_text(text, encoding="utf-8")
            print(f"    écrit : {path}")
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
