# 58 — Machines du Machinedrum : TRX-B2, TRX-SD et TRX-CH en machines 7, 8 et 9

Trois machines du Machinedrum SPS-1 UW d'Elektron (OS 1.63), portées à l'échantillon près depuis le code de son DSP,
ajoutées au Model:Cycles après Chord : **TrxB2** (grosse caisse TRX-B2), **TrxSD** (caisse claire TRX-SD) et **TrxCH**
(charley fermé TRX-CH). Travail de Talachan12, d'abord publié dans son fork
([Talachan12/Elektron-Model-Machinedrum](https://github.com/Talachan12/Elektron-Model-Machinedrum)) avec sa propre page
de patch ; un membre de la communauté a demandé qu'elles soient une case du flasher (12/10/2026). Tweak
`26-md-machines.json`, générateur `tools/gen_md_machines.py`, sources `tools/machines/md/`, preuve
`tools/emu/test_md_machines.py`, données lues dans `Elektron_SPS1-1UW_OS1.63.syx` de l'utilisateur (`--md`).

Adresses : VA de l'OS 1.13 ; pour le Machinedrum, adresses du ColdFire (section 0, chargée à `0x200000`) et du DSP A
(section 1, mémoires P/X/Y du DSP56303).

## Réponse courte

- **Fidélité** `[FAIT en émulation]` : chaque cœur C donne, échantillon par échantillon, ce que donne le code d'origine
  du DSP du Machinedrum exécuté dans l'émulateur [dsp56300](https://github.com/dsp56300/dsp56300), nourri par une copie
  en Python de la fonction des potards du ColdFire : TRX-B2 sur 409 réglages, TRX-SD sur 304, TRX-CH sur 404 plus 12
  queues de 3 000 blocs (tous les potards, extrêmes, retrigs, silence). Le Machinedrum tourne à 44,1 kHz : les machines
  rendent comme lui à 44,1 kHz, puis un filtre polyphase ramène à 48 kHz.
- **Rien du Machinedrum dans le dépôt** : les tables des potards (OS du ColdFire), les coefficients des filtres et
  l'échantillon d'attaque de TRX-SD (programme du DSP) sont lus **au build** dans le fichier officiel de l'utilisateur
  (SHA-256 `a58cd61f…`, vérifié) ; le sinus de 32 768 points est recalculé par l'algorithme du DSP (`md_sine.py`). Le
  tweak porte notre code compilé, des recettes « md » et, comme tout tweak, les octets `old` de l'OS du Cycles qui
  vérifient le fichier de l'utilisateur.
- **Pas avec** Model-TG, MACRO ni les moteurs du Syntakt (mêmes places de machines ajoutées, même SRAM) ; se combine avec
  tous les autres mods.
- **Testé** : joué sur le Model:Cycles de l'auteur (les trois machines, versions de ce tweak) ; pas encore sur celui du
  projet. `"status": "experimental"`.

## 1. Le Machinedrum `[FAIT]`

L'OS (`Elektron_SPS1-1UW_OS1.63.syx`) est un flux de messages SysEx de 112 octets (`F0 00 20 3C 02 00 7E`, somme de
contrôle, adresse, 32 mots de 16 bits en paquets 2 + 7 + 7 bits) qui reconstituent une image à `0x4000` : des sections
compressées en aPLib. Section 0 : l'OS du ColdFire (chargé à `0x200000`). Section 1 : le programme du DSP A (mots de
24 bits petit-boutistes, 4 mots d'en-tête, puis des enregistrements [espace][adresse][nombre]).

| Quoi | Où | Rôle |
|---|---|---|
| tables init / trig / rendu des machines | P:`$145af5` / `$145bb6` / `$145c77` | indexées par l'id MIDI de la machine **+ 1** |
| TRX-B2 (id `0x1c`) | P:`$102c31` / `$102c4a` / `$102c5a` | potards : fonction ColdFire `0x201fd2` |
| TRX-SD (id `0x11`) | P:`$10074c` / `$10075b` / `$100776` | potards : fonction ColdFire `0x2013a6` |
| TRX-CH (id `0x16`) | P:`$10201f` / `$102034` / `$10204d` | potards : fonction ColdFire `0x201800` |
| fiches des machines | `0x24f4b4`, `0x24f102`, `0x24f2b0` | fonction des potards, id, nom, noms et défauts des paramètres |
| sinus | `$148000` (32 768 mots) | construit au démarrage par P:`$100068` |
| coefficients des filtres | x:`$140100`…`$142100` | K1 = x:`$140900`[f + x:`$140000`[q]], K2 = x:`$141900`[f + x:`$140080`[q]] |

Chaque machine lit ses paramètres en y:(r6 + k), envoyés à chaque bloc par la fonction des potards (TRX-CH : y9 et y10
seulement au trig). Piège rencontré : l'index est l'id MIDI **+ 1** ; la première version de TRX-CH portait l'entrée 22
(une autre machine) et donnait un clic à −44 dB : c'est la mesure du niveau, en émulation, qui l'a montré.

Les trois machines :

- **TRX-B2** : un sinus dont la hauteur descend (RAMP), une distorsion (DIST), une saleté (DIRT, réduction de
  résolution), un tic d'attaque (TICK), un bruit (NOIS), une enveloppe tenue (HOLD) puis décroissante (DEC).
- **TRX-SD** : deux sinus (TONE, TUNE) avec une bosse de hauteur (BUMP, BENV), une saturation qui décroît (CLIP), un bruit
  de Fibonacci par deux résonateurs accordés par PTCH, et l'échantillon d'attaque de 4 096 mots (SNAP).
- **TRX-CH** : un bruit de Fibonacci et six carrés de périodes fixes (114, 102, 86, 80, 58, 52 échantillons) dosés par
  MTAL, deux résonateurs en cascade (LPF), un passe-haut (HPF), un passe-haut fixe ; l'enveloppe tient un bloc,
  descend linéairement pendant 2 DEC blocs, puis décroît d'un facteur par échantillon (GAP).

## 2. Conception

### 2.1 Les cœurs `[FAIT en émulation]`

`trx_b2.c`, `trx_sd.c`, `trx_ch.c` : tout sur 32 bits, aucune multiplication 64 bits. `mdmath.h` donne les produits
exacts 24 × 24 bits du DSP (`mpy` = 2xy, troncature, saturation des `move`) : sur le ColdFire avec l'EMAC (`mac.l`,
MACSR `0xa0`, comme la boucle des voix de l'OS) et `muls.l` pour les bits bas ; sur l'ordinateur en C (Karatsuba sur
12 bits). Les phases sont un index de 15 bits et une fraction de 24 bits. TRX-SD a aussi une référence instruction par
instruction (`trx_sd_ref.c`, `dsp56.h` : accumulateurs de 56 bits, mémoires X/Y, adressage modulo), pour l'ordinateur
seulement.

### 2.2 Les potards

PITCH (plus la note du trig − 60) donne PTCH sur la même échelle 0..127 (LPF sur TrxCH, qui n'a pas de PTCH) ; DECAY
donne DEC. PUNCH éteint, les valeurs fixes sont les défauts du Machinedrum.

| Cycles | TrxB2 | TrxSD | TrxCH |
|---|---|---|---|
| COLOR | DIST | SNAP | MTAL |
| SHAPE | DIRT | TONE | HPF |
| SWEEP | RAMP | BUMP | résonance (q, `0x46` = 70 sur le Machinedrum) |
| CONTOUR | HOLD | BENV | GAP |
| PUNCH | TICK 0 / 64 | CLIP 0 / 64 | – |
| fixe | NOIS 0 | TUNE 64 | |

TrxCH : le Machinedrum envoie toujours y4 = y7 = `0x46`, l'index de la table qui règle la résonance de ses deux filtres.
SWEEP choisit cet index (0..127, défaut 70) : un ajout qui n'existe pas sur le Machinedrum ; à 70 c'est exactement lui,
et l'émulateur du DSP nourri avec d'autres valeurs de q donne les mêmes échantillons que le cœur (404/404).

### 2.3 Le pont et le rééchantillonnage

`bridge.c` : le contrat de la boucle des voix (`update(pmod, v, p)` puis `render(out, v)`, [14](14-machine-sd-vintage.md),
comme MACRO [43](43-machine-macro.md)), une entrée `update` par machine et un `render` commun. Le Machinedrum rend par
blocs de 32 échantillons à 44,1 kHz ; un filtre polyphase 160/147 (24 coefficients par phase, Q14, échantillons
arrondis à 16 bits pour `muls.w`) les ramène à 48 kHz : plat jusqu'à 20 kHz, ≥ 64 dB de réjection de ce qui se
replierait sous 20 kHz, erreur d'arrondi vers −100 dB sous la pleine échelle. Un bloc exactement nul est sauté.

### 2.4 Place `[FAIT]`

Même mécanique que les moteurs du Syntakt ([28](28-moteurs-syntakt-sram.md), [31](31-moteurs-syntakt-combinables.md)) :
charge utile à `gs.PAY_ALONE` (`0x43000000`), détours `gs.detours_asm` pour 3 machines, crochet de démarrage
(`stub.S`, PACK) qui recopie le début de la charge utile en SRAM interne, à la place des tables d'ondes de CHORD
(recopiées dans la charge utile, `CHORD_PTRS` réécrits).

| Zone | Contenu | Occupé |
|---|---|---|
| SRAM 1 | tout notre code, le filtre 44,1 → 48 kHz, les petites tables | 22 140 / 22 616 o |
| SRAM 2 | l'état des pistes | 1 752 / 8 224 o |
| SDRAM (charge utile) | sinus (128 Ko), échantillon d'attaque de TRX-SD (16 Ko), coefficients de TRX-CH | |
| image | ajout après l'OS | 224 760 o, fin à `0x401e0f38` (limite `0x40200000`) |

Les données de l'utilisateur sont des parts `{"dest", "md": nom, "size"}` de la charge utile, remplies par
`tools/build.py --md` (`headers.md_parts`) et, dans le flasher, par `docs/flasher/md.js` (`MDTables.mdParts`, portage
de `md_os.py` et `md_sine.py`) passé à `MCBuilder.build` (`opts.md`). Les bouche-trous `0x5a5a5a5a` sont dans une
unité de compilation à part (`trx_b2_md.c`) : le compilateur ne peut pas les replier ; `gen_md_machines.py --md`
vérifie que la recette remplie égale le code compilé avec les vraies données.

## 3. Incompatibilités

Le tweak déclare en `conflicts` tous les tweaks qui ajoutent une charge utile (mêmes places de machines ajoutées, même
SRAM) : dans le flasher, la carte exclut **Model-TG**, **MACRO** et les **moteurs du Syntakt**. `tools/check_overlaps.py`
passe avec toutes les autres cartes.

## 4. Le flasher

Carte `md-machines` (rubrique Sons et machines, `"needs": "machinedrum"`) : cochée, elle ouvre une 4e zone de dépôt à
l'étape 2 pour `Elektron_SPS1-1UW_OS1.63.syx` (lien vers elektron.se, Machinedrum UW). `REF_MODS` porte l'empreinte de
ses écritures et de sa charge utile, `REF_MAINOS` celles de la carte seule, de chaque paire et des plus grandes
combinaisons (`tools/ref_mainos.py --md`). La page donne octet pour octet le build Python (MAIN OS seul
`ecffe874…`).

## 5. Preuve en émulation `[FAIT en émulation]`

`tools/emu/test_md_machines.py` : le vrai code de l'OS (Unicorn).

1. Démarrage : le crochet reconstitue la charge utile, nos deux zones en SRAM, le reste intact, les 31 pointeurs de
   CHORD visent leur copie.
2. Interface : rangées de machines, descripteurs, écran MACHINES (9 noms, icônes KICK / SNARE / METAL), molette,
   enregistrements, changement de machine, potards.
3. Son : à chaque bloc, ce que l'OS passe à `update` est relu et ce que sort notre `render` est comparé à la référence
   compilée pour l'ordinateur (`host_ref.c` + les cœurs, eux-mêmes identiques au DSP émulé) : 19 cas par machine,
   identiques ; 6 pistes sur les machines d'origine identiques à l'OS d'origine ; 5 pistes d'origine identiques avec
   chacune de nos machines sur la 6e.
4. Charge (instructions par bloc, toute la boucle des voix, une piste à l'attaque) : KICK 8 629, TrxB2 9 993, TrxSD
   13 407, TrxCH 15 325. Six pistes, toutes frappées ensemble : 6 × stock 41 900 ; 4 stock + TrxB2 + TrxSD 48 646 ;
   3 stock + TrxB2 + TrxSD + TrxCH 56 302 ; 6 × TrxCH 85 700. Une machine muette ne coûte presque rien (TrxCH ne
   calcule plus ses filtres une fois sa queue exactement nulle : son prochain trig les remet à zéro).
5. Avec les autres mods (`--with`) : les deux plus grandes combinaisons du flasher (l'une avec le filtre par piste,
   l'autre avec LFO 2, 3, 4) : démarrage, son de nos machines identique à la référence, machines d'origine identiques
   aux mêmes mods sans les nôtres.

## 6. À vérifier sur la machine

- Flasher `md-machines` seul, puis avec `6ch-usbup`, le filtre par piste et LFO 2, 3, 4 : les trois machines dans
  MACHINES après Chord, avec les icônes KICK, SNARE et METAL ; chaque potard du tableau change le son.
- Six pistes qui jouent ensemble (par exemple 3 d'origine + TrxB2 + TrxSD + TrxCH) : pas de craquement ni de séquenceur
  qui ralentit.
- Un projet enregistré avec ces machines, rouvert après extinction.
