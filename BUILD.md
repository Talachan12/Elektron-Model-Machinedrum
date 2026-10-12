# Construire un firmware modifié

> ⚠️ Aucune image firmware Elektron n'est fournie ici. Tu apportes **ta propre** copie de l'OS officiel,
> téléchargée sur elektron.se. Flasher un firmware modifié se fait **à tes risques** (garantie, brick possible).
> Une **interface MIDI reliée au MIDI IN** de l'appareil (jack TRS : câble jack stéréo depuis une sortie TRS,
> ou adaptateur DIN fourni) est obligatoire pour pouvoir revenir en arrière (STARTUP MENU).

## Chaîne d'outils

Python 3 uniquement, aucune dépendance externe, aucun compilateur. Le moteur bas niveau
(`tools/mtlib/`, transport SysEx + codec aPLib + conteneur ELE3/HMAC) vient de
[`drumkilla/elektron-model-tweaks`](https://github.com/drumkilla/elektron-model-tweaks) (MIT, voir `tools/mtlib/LICENSE`).
L'orchestration (`tools/build.py`) et les tables de patchs (`tweaks/`) sont propres à ce dépôt.

## Étapes

1. Télécharge `model-cycles_OS1.13.zip` sur elektron.se, dézippe-le pour obtenir `model-cycles_OS1.13.syx`
   (SHA-256 attendu `44fe5862…9800640c`).
2. Liste les patchs disponibles :
   ```sh
   python3 tools/build.py --list
   ```
3. Construis l'image. Il y a deux variantes du 6 canaux, **incompatibles entre elles** :
   ```sh
   python3 tools/build.py -i model-cycles_OS1.13.syx -t 6ch-multiout   # référence (casse l'upgrade USB)
   python3 tools/build.py -i model-cycles_OS1.13.syx -t 6ch-usbup      # garde l'upgrade USB (celle du flasher web)
   ```
   Et la machine **SD VINTAGE** (à la place de SNARE, [note 14](notes/14-machine-sd-vintage.md)), seule ou avec un 6 canaux :
   ```sh
   python3 tools/build.py -i model-cycles_OS1.13.syx -t sdvintage-snare
   python3 tools/build.py -i model-cycles_OS1.13.syx -t 6ch-usbup,sdvintage-snare
   ```
   Et les trois tweaks de [drumkilla](https://github.com/drumkilla/elektron-model-tweaks) (fichiers `01`–`03` de `tweaks/`,
   MIT) : `latching-mute`, `trig-preview`, `browser-scroll`. Notre build donne le **même MAIN OS, octet pour octet**, que leur
   propre `tweak.py` (vérifié pour chacun et pour les trois ensemble), à une retouche près : depuis le 04/10/2026, `trig-preview`
   accepte aussi le séquenceur en pause (3 octets, [note 34](notes/34-ecoute-en-pause.md)).
   ```sh
   python3 tools/build.py -i model-cycles_OS1.13.syx -t 6ch-usbup,latching-mute,trig-preview,browser-scroll
   ```
   Et le **vrai moteur SD VINTAGE du Syntakt** ([note 17](notes/17-portage-exact-syntakt.md)), extrait au build de **ton** fichier Syntakt
   (aucun octet Elektron dans le dépôt : le tweak ne contient qu'une recette de copie et une table de relocalisation).
   L'OS Syntakt 1.42 ou 1.41 : même programme audio, donc même résultat ([note 16 §1](notes/16-moteur-syntakt.md#os-142--même-programme-audio)) :
   ```sh
   python3 tools/build.py -i model-cycles_OS1.13.syx -t 6ch-usbup,sdvintage-exact --syntakt Syntakt_OS1.42.syx
   ```
   Ou le même moteur en **7ᵉ machine « SDVtg »**, SNARE restant la SNARE d'origine ([note 18](notes/18-septieme-machine.md)) :
   ```sh
   python3 tools/build.py -i model-cycles_OS1.13.syx -t 6ch-usbup,sdvintage-7th --syntakt Syntakt_OS1.42.syx
   ```
   Ou n'importe quel choix de moteurs du Syntakt en machines ajoutées ([note 20](notes/20-moteurs-syntakt-a-cocher.md)) :
   `sdvintage-7th` (SD), `syntakt-vintage` (SD + CP), et `syntakt-<moteurs>` pour les autres choix parmi `sd`, `cp`, `toy`,
   `bits`, `swarm` (dans cet ordre : `syntakt-toy`, `syntakt-bits`, `syntakt-swarm`, `syntakt-sd-cp-toy-bits-swarm`…
   [notes 21](notes/21-sy-bits.md) et [22](notes/22-sy-swarm.md)). Un seul à la fois :
   ```sh
   python3 tools/build.py -i model-cycles_OS1.13.syx -t 6ch-usbup,syntakt-sd-cp-toy-bits-swarm --syntakt Syntakt_OS1.42.syx
   ```
   → écrit `model-cycles_OS1.13_mod.syx` à côté. `-t a,b` combine plusieurs patchs compatibles.
   `--all` applique tout, mais refuse si deux patchs sont incompatibles (c'est le cas de ces deux variantes).

Le build vérifie chaque octet `old` avant écriture, contrôle le SHA-256 de la section 3 d'origine,
et recalcule tous les checksums + le HMAC-SHA256. Seule la **section 3 (MAIN OS)** est touchée :
bootloader et updater sont conservés à l'identique.

Pour un patch qui écrit dans une zone `0xFF` (une « cave »), comme `6ch-usbup` ou `sdvintage-snare`, le build affiche la zone :
du début du bloc `0xFF` à la fin des octets écrits.
Il **refuse** si l'image d'origine contient un pointeur vers elle : `--force-cave` passe outre, après vérification à la main.
Exception : un pointeur que les patchs choisis réécrivent eux-mêmes, vers une adresse hors de la zone, est affiché « neutralisé » et ne bloque pas.
Autre exception, vérifiée à la main et listée dans `device.json` (`cave_refs_ok`) : une référence dont seule une partie de la
zone est lue. C'est le cas de `browser-scroll` : il écrit dans la table caractère → glyphe de la petite police de chiffres
(`0x401485ee`, 256 entrées de 16 bits, `0xFFFF` = pas de glyphe), aux entrées des caractères de contrôle 1 à 8, jamais dessinés.
La référence ne bloque plus tant que toutes les écritures restent dans la partie déclarée libre ; une écriture qui en sort est refusée.
C'est le cas des sprites dont on libère le masque `0xFF` en les redirigeant vers un masque identique
([note 14 §5](notes/14-machine-sd-vintage.md#5-place-libre--les-caves-0xff-étaient-des-masques-de-sprites), `tools/sprites.py`).
Les références relatives (`(d16,PC)`, branchements) sont seulement signalées, car une donnée peut les imiter.
Détails : [`notes/13-6ch-upgrade-usb.md`](notes/13-6ch-upgrade-usb.md) §4.

### Vérification de reproductibilité

Le patch 6 canaux doit produire un **MAIN OS décompressé** de SHA-256
`65e24b50dd457444e87daea79dd41b82f61098cb8ae5cd27cbe0d91742f29555`
(identique au résultat connu-bon de `ms-multi-output`). Pour l'exiger :
```sh
python3 tools/build.py -i model-cycles_OS1.13.syx -t 6ch-multiout \
    --expect-mainos 65e24b50dd457444e87daea79dd41b82f61098cb8ae5cd27cbe0d91742f29555
```
Le hash du `.syx` lui-même varie selon le packer ; c'est le MAIN OS décompressé qui fait foi.

Les autres patchs n'ont pas de résultat connu-bon extérieur. Voici ce que donne `build.py` sur l'OS 1.13 officiel
(le flasher web exige les mêmes valeurs pour celles qu'il propose) :

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `6ch-usbup` | `57fa258f209c10359f6888af79087f656e994930ff86ffcc1e2e2e48512d9530` |
| `sdvintage-snare` (v2, recalée sur le Syntakt) | `11049726efa102028f7365b0a672c8a244b98edcef5e7c8b5e0aafba369f60d3` |
| `6ch-multiout,sdvintage-snare` | `80d0d717c5054f9277c2ddadb588e3578968cc1427610c7367ee408fa8ffd2de` |
| `6ch-usbup,sdvintage-snare` | `9416ac0b7f0bffda6b91490aacf1b00f831196466f5f64dc87b3a3b63cbc9ccb` |
| `latching-mute,trig-preview,browser-scroll` | `c6aea7e51d1caf3e9be4553f3a0c5b033592d804cb25226ef9df3fd19add8c08` (`tweak.py` de drumkilla, sans la retouche de note 34 : `71fef138…`) |
| `6ch-usbup,latching-mute,trig-preview,browser-scroll` | `b8911cb1692476c266fdad6fae7bdabd824bd8976149cc5a2baae4dfb9252176` |

| `sdvintage-exact` (avec `--syntakt Syntakt_OS1.42.syx`) | `8e2290a79fb1406ce65b3af3c5d3d95faade666e98eb8ecce0c0fa25fe87b15d` |
| `6ch-usbup,sdvintage-exact` (idem) | `bd729d526c992fb5d678a1a2793d012fdcec47f6584631fc01afa896483fc061` |
| `syntakt-vintage` (idem) | `b4de3ec5f7eda7504bf03e7141f57bae6cf5bc137d39f6704da60881d56ed9b0` |
| `sdvintage-7th` (idem) | `c73ad4c796b94ab39d106d0798091eb39b5e3e31f66d7fe78e2db30db44daad3` |
| `syntakt-cp` (idem) | `e9e3a8c7aa438a00cc028574b78dac33a6b7a44cdf98623eaa1edcf4668ac1ee` |
| `syntakt-toy` (idem) | `a3d8fad221ed0920ec15ea0e791e3be3e869b04b147affefcda4108d0248796c` |
| `syntakt-sd-cp-toy` (idem) | `ea04669bbe10d83505cd9c2b4654f46c53dd1fc55d4d5229d2cad33c6e5f0a0e` |
| `syntakt-bits` (idem) | `0e73d4f76bb947db6392b7e1e1547f2951ec8fe1924668bec532ee9b531f93bd` |
| `syntakt-sd-cp-toy-bits` (idem) | `c6add70bea5a1f6d0d4bf6aa26ae454dc6f873c6ab55937edbd7d9ad7d96c86c` |
| `syntakt-swarm` (idem) | `b47c9d7d2fb8d9568503033a3d0f318396c4b52b8df34c081564005c92b69517` |
| `syntakt-sd-cp-toy-bits-swarm` (idem) | `c6cdfe22fe5a280c1e42ae1f11ae25156d86b36da1e9d0e83f1d6c3227117b7c` |

### Model-TG

`tweaks/model-cycles_OS1.13/30-model-tg.json` vient du build de [Model-TG](https://github.com/TinyGregAudio/Model-TG) lui-même (licence MIT),
au commit épinglé dans `tools/gen_model_tg.py`, avec les binutils m68k, depuis une copie de sa source avec deux retouches (`MC_PATCHES` : en
mode mute, chaque touche de piste mute tout de suite, [note 31 §10](notes/31-model-tg.md) ; sa copie de l'écoute d'un pas accepte le
séquenceur en pause, [note 34](notes/34-ecoute-en-pause.md) ; avec l'audio USB multipiste, une piste mutée n'est plus coupée net sur sa
piste USB, [note 35 §3](notes/35-glitches-usb-multipiste.md)), plus l'envoi à l'USB à heure fixe (`tools/usb_steady.py`) :
```sh
git clone https://github.com/TinyGregAudio/Model-TG vendor/Model-TG
git -C vendor/Model-TG checkout 70b39dd6787770ebefc7a2d78dea1678ec012679   # v1.1.0
python3 tools/gen_model_tg.py --cycles model-cycles_OS1.13.syx --model-tg vendor/Model-TG [--check]
```

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `model-tg` | `aa0740d714d502d440ec003cca8ca389c1ac9190de28395aef748ec9bf5c4c3a` (sans nos ajouts : `a049d724…`, celle annoncée par Model-TG pour sa v1.1.0) |
| `6ch-usbup,model-tg` | `96b6aec20df7c66f4a8d84c3ab4358a92b01d754c319923927d272aed0d34322` |

Le même script écrit `30-model-tg-st.json`, la base de la **version combinée avec les moteurs du Syntakt** : Model-TG construit par son
build depuis une copie de sa source, avec les mêmes ajouts et une retouche de plus (sa zone d'échantillons s'arrête 1 Mo plus bas). Les moteurs s'appliquent
par-dessus (`31-syntakt-tg-<moteurs>.json`, `requires`), voir [note 31 §4](notes/31-model-tg.md) :
```sh
python3 tools/gen_syntakt_engines.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx --all --tg [--check]
python3 tools/build.py -i model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx -t model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm
python3 tools/emu/test_model_tg_syntakt.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx
```

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `model-tg-st,syntakt-tg-sd` | `f09ab68d48b7cfb58604ce6dc31f0998def25390e0a02aa83ecd304754ef8321` |
| `model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm` | `d5e73e10a07042a85e9022e87e488b6ca4960ecef69f49652d5c3dc706a1f6fc` |
| `6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm` | `70354db7660a9ffc60956d523d2976299be4fa4813e483c1222abe26edae2b3c` |

Le flasher web vérifie chaque mod, à chaque build, contre l'outil Python ([note 49](notes/49-verification-mod-par-mod.md)) :
`REF_MODS` de `docs/flasher/app.js` donne l'empreinte des écritures et de la charge utile de chaque tweak, et `REF_MAINOS`
le MAIN OS d'un échantillon de combinaisons (chaque carte seule, chaque paire, les plus grandes : 464 aujourd'hui).
`tools/ref_mainos.py` réécrit les deux blocs (`--check` pour vérifier) ; `tools/check_overlaps.py` prouve, sans firmware,
que deux mods qu'on peut cocher ensemble n'écrivent jamais aux mêmes octets (sauf écriture identique ou mod posé
par-dessus l'autre par `requires`) ; `tools/registry.py` écrit `tweaks/model-cycles_OS1.13/REGISTRY.md`, le registre
de la place libre (masques de sprites pris et libres, caves, charges utiles) et des crochets posés sur l'OS
([note 52](notes/52-registre-place-libre.md)), à régénérer et commettre avec tout nouveau tweak ;
`tools/webflash_smoke.sh model-cycles_OS1.13.syx Syntakt_OS1.42.syx` reconstruit l'échantillon dans la page et le compare.
SD VINTAGE v1 (clean-room d'origine, **testée sur le matériel** le 29/09/2026, compilée par GCC 13.3) donnait `80b7b2bd…` seule et `38754937…` avec `6ch-usbup` ;
la v2 est compilée par `m68k-elf-gcc` 16.2 (Homebrew), voir [note 16 §6](notes/16-moteur-syntakt.md).

### Écoute des samples (Model-TG)

`tweaks/model-cycles_OS1.13/33-sample-preview.json` (sur `model-tg`) et `33-sample-preview-st.json` (sur `model-tg-st`,
mêmes écritures) sont produits par `tools/gen_sample_preview.py`, qui assemble `tools/machines/sample_preview/` et le lie
dans quatre masques de sprites 47×47 libérés, partagés avec `chord-keys`, qui exclut Model-TG (`conflicts`)
([note 46](notes/46-ecoute-des-samples.md)). Le code appelle celui de
Model-TG aux adresses des `symbols` de `30-model-tg*.json` ; le générateur vérifie ce code avant d'écrire. Le tweak
exige Model-TG (`requires`) : les builds de Model-TG sans lui ne changent pas. La preuve fait tourner le vrai code de
l'OS et de Model-TG, du navigateur à la boucle des voix (avec `--syntakt` seul, les deux versions) :
```sh
python3 tools/gen_sample_preview.py --cycles model-cycles_OS1.13.syx [--check]
python3 tools/build.py -i model-cycles_OS1.13.syx -t model-tg,sample-preview
python3 tools/build.py -i model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx \
    -t model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,sample-preview-st
python3 tools/emu/test_sample_preview.py --cycles model-cycles_OS1.13.syx \
    [--with 6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,arp,trig-hold,tempo-max,boot-anim] \
    [--syntakt Syntakt_OS1.42.syx]
```

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `model-tg,sample-preview` | `b73428049e2779ff8c73d91787c6bbaffe0a97b4f77e6b2e3819f09e035d9353` |
| `6ch-usbup,model-tg,sample-preview` | `4671f7b80784249d8e8c533d4546297fda2ff52b97c993fab7de83cbb5c60867` |
| `model-tg,arp,trig-hold,tempo-max,boot-anim,sample-preview` | `1d90726905d583347dc8cdaf359ad4fb25c1b907e659fa665cecdada35c1c585` |
| `model-tg-st,syntakt-tg-sd,sample-preview-st` (avec `--syntakt`) | `2557d21b5d2f20cdd909e727ae458fa71ce59ed864ab701c43d1f86730c31d17` |
| `model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,sample-preview-st` (idem) | `cde4365ff392e68b373afe9fa2004dc5e275c7c15f8a3c732549478ca2d36ca4` |
| `6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,sample-preview-st` (idem) | `7b142604f35d11c63e3c22a0f1a4426c6630e2d184c5f680ed5f47125e2e891e` |
| `6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,trig-hold,arp,tempo-max,boot-anim,sample-preview-st` (idem) | `20a116b1dbbc05e84dfc32df2f269f5c23df2d54fcb39d9b4a7c577c5916a432` |
| `model-tg-st,macro-tg,sample-preview-st` (avec la machine MACRO) | `9da219fbb5bccd19e496e880c00af5192d08d2d2a11995f209db09f9697dc9f4` |

### Arpégiateur

`tweaks/model-cycles_OS1.13/40-arp.json` est produit par `tools/gen_arp.py`, qui compile `tools/machines/arp/` (`m68k-elf-gcc`)
et le lie dans quatre masques de sprites libérés ([note 32](notes/32-arpegiateur.md)). La preuve fait tourner le code du tweak
et celui de l'OS, jusqu'à la vraie boucle d'événements de l'interruption audio, et le live rec par les vraies fonctions
d'envoi de note de l'OS :
```sh
python3 tools/gen_arp.py --cycles model-cycles_OS1.13.syx [--check]
python3 tools/emu/test_arp.py --cycles model-cycles_OS1.13.syx \
    [--with 6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm --syntakt Syntakt_OS1.42.syx]
```

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `arp` | `e445bf895123d3fc94762a65739558b579ec8df3000c9bdf5747a3d73287e6a6` |
| `model-tg,arp` | `062f16db10bae6d9d3c6fda89aff382bf2896b531a6b511c236bb07c632247be` |
| `6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,arp` | `f933b2b99cf4d525e9529c0c6c445f2f45b94b5f479d3157a0821f566a3ac592` |

L'arpégiateur et les moteurs du Syntakt libèrent le même masque (`0x4016cae8`) : les deux constructeurs (`tools/build.py`,
`docs/flasher/builder.js`) acceptent une écriture déjà faite à l'identique par un autre tweak.

### Effacer un trig

`tweaks/model-cycles_OS1.13/41-trig-hold.json` est produit par `tools/gen_trig_hold.py`, qui assemble
`tools/machines/trig_hold/trig_hold.S` (166 o avec l'heure d'appui des 16 touches de pas) au début du masque de sprite libéré
`0x4015c044`, devant les stubs de `6ch-usbup` ([note 33](notes/33-effacer-un-trig.md)). La preuve fait tourner la vraie chaîne de
l'OS, de la lecture des touches (anti-rebond, horloge de maintien à 120 Hz) au mode grille, à la milliseconde :
```sh
python3 tools/gen_trig_hold.py --cycles model-cycles_OS1.13.syx [--check]
python3 tools/emu/test_trig_hold.py --cycles model-cycles_OS1.13.syx \
    [--with 6ch-usbup,model-tg-st,arp,syntakt-tg-sd-cp-toy-bits-swarm --syntakt Syntakt_OS1.42.syx]
```

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `trig-hold` | `bbb8a4217a888c46a60cfb17ae444bec9cf21d6ff2d2d36bf8d1f1cdb81d1ef4` |
| `6ch-usbup,trig-hold` | `5be28240875818efd2b912680bb589300cd51a2c0aa4a86ae289b3241fbf7f44` |
| `model-tg,trig-hold` | `f71e6ea6d7bc530e3ad255b161babbfa388a93595d74c671a4ed9793bde5c87c` |
| `6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,trig-hold,arp` | `ea715e19eec998366c2c8e4ef40c354060dd3550fc42a89b46e77b71256f4ba2` |

Avec `6ch-usbup`, les deux tweaks réécrivent de la même façon le pointeur du sprite dont le masque est libéré.

### Tempo jusqu'à 546 BPM

`tweaks/model-cycles_OS1.13/42-tempo-max.json` est produit par `tools/gen_tempo_max.py` : les six bornes à 300 BPM (moteur,
horloge MIDI reçue, projet, pattern, menu Tempo) passent à 546,0 BPM, plafond du champ 16 bits du projet, ainsi que les deux
contrôles au chargement ; la remise dans le cycle de la phase du LFO devient une boucle (au-delà de 351,6 BPM, le pas peut
dépasser un cycle). 12 écritures, aucune place libre ([note 38](notes/38-tempo-546-bpm.md)). La preuve fait tourner le vrai
code de l'OS, d'origine et modifié, jusqu'aux 6 LFO (EMAC exacte) :
```sh
python3 tools/gen_tempo_max.py --cycles model-cycles_OS1.13.syx [--check]
python3 tools/emu/test_tempo_max.py --cycles model-cycles_OS1.13.syx
```

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `tempo-max` | `5d6417b175e89b68c76743bbcad45306ba210969ad049fc1bfa6da46e432eaef` |
| `6ch-usbup,tempo-max` | `0f7a47738be9a70aa3c8e586d28636c535d787693ddf6cc756c92b5824717d42` |
| `model-tg,tempo-max` | `97cc13b34d3f4b3440d42bdb1c692e64bf0aa8b2de54b806b14320914936ef4f` |
| `6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,trig-hold,arp,tempo-max` | `c8214dc5fe88a5ff346d8554f05753bb25acec448cb0eb23140236b10a9404d4` |

### OS Cycles pour Model:Samples (et retour par USB)

Pas un tweak : `tools/crossflash.py` met l'OS Cycles officiel dans le conteneur officiel du Model:Samples, en changeant les
32 octets de la constante de sa clé de vérification (`0x401296b2`) pour qu'il accepte la signature du Samples ; le retour
est l'OS Samples officiel, inchangé, dans le transport SysEx du Cycles ([note 41](notes/41-os-cycles-sur-samples.md)).
La clé vient du `.syx` officiel du Samples, jamais du dépôt. La preuve fait tourner les vérifications de mise à jour des
deux OS sur les deux fichiers :
```sh
python3 tools/crossflash.py --cycles model-cycles_OS1.13.syx --samples model-samples_OS1.13.syx --to samples
python3 tools/crossflash.py --cycles model-cycles_OS1.13.syx --samples model-samples_OS1.13.syx --back-samples
python3 tools/emu/test_crossflash_samples.py --cycles model-cycles_OS1.13.syx --samples model-samples_OS1.13.syx
```

| Fichier | SHA-256 |
|---|---|
| `model-cycles_OS1.13_for-model-samples.syx` | `c06c23f31e50fac6ad40cd0f633acd4a7da4f63c929dff563dae887b93105dd4` |
| son MAIN OS | `b6fbc48f7d7d07cecae3859e07270fa2298f393e8afa2643144bdb4efc317aad` |
| `model-samples_OS1.13_back-from-cycles-os.syx` | `d63ce13dd1a5039d11b60d3f69d4e88e9d0f56fb2e7350c105ec641d32083680` |

### OS Cycles avec mods pour Model:Samples

Le firmware est **toujours l'OS du Model:Cycles**, avec les mods choisis, quelle que soit la machine
([note 57](notes/57-os-cycles-quelle-que-soit-la-machine.md)) : sur un Model:Samples, le sampling vient de Model-TG. On
construit les mods comme pour un Model:Cycles, puis `tools/mods_for_samples.py` met ce MAIN OS dans le conteneur officiel
du Samples avec le même correctif de 32 octets que `crossflash.py --to samples` (toujours appliqué), et écrit deux
fichiers : `_smp-os` pour un Model:Samples sous son OS (transport `0x0F`), `_cyc-os` pour un Model:Samples déjà sous un
OS Cycles de la page ou de ce script (transport `0x11`, pour changer de mods). La page fait la même chose
(`MCBuilder.modsForSamples`, choix de la machine dans l'onglet Mods).
```sh
python3 tools/build.py -i model-cycles_OS1.13.syx -t model-tg,arp -o mods.syx
python3 tools/mods_for_samples.py --cycles model-cycles_OS1.13.syx --samples model-samples_OS1.13.syx --mods mods.syx
python3 tools/emu/test_mods_for_samples.py --cycles model-cycles_OS1.13.syx --samples model-samples_OS1.13.syx \
    --syntakt Syntakt_OS1.42.syx
```

Sans mods (l'OS Cycles officiel en `--mods`), le fichier `_smp-os` est octet pour octet celui de
`crossflash.py --to samples`. Empreintes de la preuve (le MAIN OS installé est celui de `REF_MAINOS` sauf les 32 octets
de la clé) :

| Combinaison | `_smp-os` (SHA-256) | `_cyc-os` (SHA-256) |
|---|---|---|
| `model-tg` | `1985e8e703092b768d32aa2c9b446cb0f95c1f944dc3e206f75973337469f686` | `1317199fbc625c38700344b69ce00496cdee0c8be6fae305843e6373e6394d19` |
| `6ch-usbup,model-tg` | `fdbf4621e291618a98de64c561a39de59852d5a4dfdb58c927e312467557a839` | `a5a21ac6dfe5697b9e39fa80518a53989af4be8edac3cf9cbe6f1ebddb00ce79` |
| `model-tg-st,sample-preview-st,macro-tg` | `4b069c69c47c6ef55ab6e50d067b2a8ced067fe3ed1b883419f5731db4044f5f` | `156ef6c22544de9873ed2119b30d4619354848cd27ca429e79bd1d628c586ffd` |
| `6ch-usbup,model-tg-st,sample-preview-st,trig-hold,arp,tempo-max,boot-anim,syntakt-tg-sd-cp-toy-bits-swarm` | `f030b1a210c3ed9e5e2026dd0ac00daa99ca2a99cb963133f27d7e160f36fbcc` | `62d70e2bac0b22af70a56f71dc24791c52f79bda105c6375b9a3561a7e6b8a96` |

### Animation de démarrage modded-cycles

`tweaks/model-cycles_OS1.13/43-boot-anim.json` est produit par `tools/gen_boot_anim.py` : le corps de la tâche d'animation de
démarrage de l'OS (`0x40053a6c`) est réécrit à sa place, assemblé depuis `tools/machines/boot_anim/` (690 o sur 1 032, aucune
place libre). Mêmes 80 images de 20 ms, même fin ; les carrés du logo puis « modded-cycles » ([note 39](notes/39-animation-demarrage.md)).
La preuve fait tourner la tâche d'origine et la nouvelle avec le vrai code de l'écran de l'OS, jusqu'au registre du DSPI1, et
compare chaque image vue sur l'écran au modèle du générateur ; le modèle de l'écran est d'abord validé par un « 7 » des grands
chiffres de l'OS, écrit par son code de texte (l'OS compte les lignes depuis le bas, note 39 §2) ; `--gif` écrit l'animation vue :
```sh
python3 tools/gen_boot_anim.py --cycles model-cycles_OS1.13.syx [--check]
python3 tools/emu/test_boot_anim.py --cycles model-cycles_OS1.13.syx [--gif anim.gif] \
    [--with 6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,arp,trig-hold,tempo-max]
```

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `boot-anim` | `388ed6c6ee65529e2dc2d2c93aadb37c6878324acf90ad931d5ca3f7c6b68b27` |
| `6ch-usbup,boot-anim` | `76b1a532c8119ce222a3545b8a21b4cf0b2e12887e40c32f9a80b0d70975533e` |
| `model-tg,boot-anim` | `cbec181684805bf37dd07c62dc47f7daf35e6abab530a3f3b06ec5db590278ec` |
| `6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,trig-hold,arp,tempo-max,boot-anim` | `d468a729f32780870dbd591e52e8c782a5cdd347459ac1c61ef35473e26c9323` |

### Accords de gamme sur TRIG 1–16

Contribution de Nico Heuser ([PR #46](https://github.com/18nelli18/Modded-Cycles/pull/46)).
`45-chord-keys.json` est généré depuis `tools/machines/chord_keys/` par `tools/gen_chord_keys.py`
(GCC m68k-elf 16.2.0, binutils 2.47 : ceux de Homebrew, ou compilés depuis les sources d'Ubuntu comme au
[§16 de la note 42](notes/42-clavier-accords-diatoniques.md)). Le générateur refuse `m68k-linux-gnu-gcc` : son ABI lit
dans `a0` les pointeurs que l'OS rend dans `d0`, ce qui fausserait les appels à l'OS ([note 42 §6](notes/42-clavier-accords-diatoniques.md)).
**Testé** sur la machine par Maxime, seul et avec six autres mods (07/10/2026), puis la correction de la note
bloquée (note 42 §16, 10/10/2026). Sélectionnez une piste CHORD,
puis activez **Keys** dans **FUNC + RETRIG**. Root, Scale et I–VII choisissent la tonique, le mode
et les extensions diatoniques ; le majeur s'affiche **MAJ**. Hors édition des pas, TRIG 1–7 jouent I–VII,
8–14 les mêmes degrés une octave plus haut, 15–16 I–II deux octaves plus haut. Les grands pads T1–T6
conservent leur sélection et leur jeu stock ; les accords des TRIG ne déclenchent pas le retrig/arpège.
Réglages par piste, enregistrés avec le pattern. **I–VII** seuls choisissent les extensions ; **SHAPE** règle
la disposition (**BASE**, **CLS0–3**, **OPN0–3**) et **COLOR** les niveaux, sans changement d'octave.
Model-TG est explicitement incompatible.

Quatorze masques identiques sont redirigés avant d'y placer les 5 063 octets de code, constantes et état ; seule la section 3 change. Aucun firmware
n'est distribué dans le dépôt. Génération, preuve autonome, puis preuve avec tous les mods compatibles :

```sh
python3 tools/test_chord_keys.py
python3 tools/gen_chord_keys.py --cycles firmware/model-cycles_OS1.13.syx --check
python3 tools/emu/test_chord_keys.py --cycles firmware/model-cycles_OS1.13.syx
python3 tools/emu/test_chord_keys.py --cycles firmware/model-cycles_OS1.13.syx \
  --with 6ch-usbup,latching-mute,trig-preview,browser-scroll,trig-hold,arp,tempo-max,boot-anim,syntakt-sd-cp-toy-bits-swarm \
  --syntakt firmware/Syntakt_OS1.42.syx
python3 tools/emu/test_chord_keys_release.py --cycles firmware/model-cycles_OS1.13.syx
python3 tools/build.py -i firmware/model-cycles_OS1.13.syx -t chord-keys \
  -o build/model-cycles_OS1.13_chord-keys.syx
```

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `chord-keys` | `901675f5b8291f3b91d134208236e83431d6a079c73c2d5f1e4e54ebc334321f` |
| `6ch-usbup,chord-keys` | `d6e43f0ca6a8df953df7a12da7458c70552f1b3a8de1bb39213f0c52168f0352` |
| `6ch-usbup,arp,trig-hold,tempo-max,boot-anim,chord-keys` | `0922d3967c6d29ea86c14ffe41a5555cfb5346ecffb6298fe84c8ba3e3c51c43` |
| `macro,chord-keys` | `80a12bae5cbd3a541d3e093223fe5305684193063e2d3be8cee9d1858e805133` |
| `6ch-usbup,latching-mute,trig-preview,browser-scroll,trig-hold,arp,tempo-max,boot-anim,chord-keys,syntakt-sd-cp-toy-bits-swarm` | `569e6bb39b628ebbd8a8f1ef64e43f0097f4c3d4bb8430974f01dab6d82ca110` |

La preuve exécute les touches, pads, menus, sauvegardes et calculs CHORD du véritable OS ; 14 000 accords
BASE, 2 205 combinaisons SHAPE et les chemins inactifs sont comparés à la référence. COLOR, les frontières de
SHAPE, les libellés et le plafond aigu du premier opérateur sont contrôlés. Les frontières simulées, le coût en instructions et
les vérifications restantes sur la machine sont détaillés dans [la note 42](notes/42-clavier-accords-diatoniques.md).
Les accords étendus restent limités à quatre notes ; l'enregistrement conserve la fondamentale et le réglage
du degré s'applique à la relecture, sans enregistrer une extension différente par trig.

### Machine MACRO (les modèles de Braids)

`tweaks/model-cycles_OS1.13/25-macro.json` (7e machine) et `32-macro-tg.json` (avec Model-TG : 8e machine, par-dessus
`model-tg-st`) sont produits par `tools/gen_macro.py` : le code de Braids d'Émilie Gillet (MIT,
[pichenettes/eurorack](https://github.com/pichenettes/eurorack) au commit `08460a6`, stmlib `e3bd7c9`) compilé tel quel
avec la passerelle `tools/machines/macro/macro.cc`, en charge utile rangée après l'image et reconstituée au démarrage à
`0x43000000` (`0x46700000` avec Model-TG), avec la mécanique des machines ajoutées des moteurs du Syntakt
([note 43](notes/43-machine-macro.md)) ; 13 modèles rendus à 48 kHz et le lo-fi RATE/BITS sur FINE
([note 55](notes/55-macro-allegee-et-lofi.md)). Le générateur a besoin du clone d'eurorack (sous `vendor/`, ignoré par git) et de
`m68k-linux-gnu-g++` (les JSON versionnés viennent du GCC 13.3 d'Ubuntu 24.04 : un autre GCC donne d'autres octets) ; la
preuve, de `g++` pour Braids compilé pour l'ordinateur, la référence :
```sh
git clone https://github.com/pichenettes/eurorack vendor/eurorack
git -C vendor/eurorack checkout 08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4
git -C vendor/eurorack submodule update --init stmlib
python3 tools/gen_macro.py --cycles model-cycles_OS1.13.syx --eurorack vendor/eurorack [--check]
python3 tools/emu/test_macro.py --cycles model-cycles_OS1.13.syx --eurorack vendor/eurorack [--quick] \
    [--with 6ch-usbup,model-tg-st,sample-preview-st,trig-hold,arp,tempo-max,boot-anim]
python3 tools/emu/test_macro.py --cycles model-cycles_OS1.13.syx --eurorack vendor/eurorack --spectres   # notes/55 §2
```
Avec les moteurs du Syntakt : les tweaks combinés de la section suivante. Incompatible avec SD VINTAGE (même mécanique,
même place).

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `macro` | `f39223c286166b1d018d215b36e3fbd3dedaba9ed05681a2784c407c92f6d7c6` |
| `6ch-usbup,macro` | `bf83bbf3c61495114e427dd70f46fb84270617476afd5309456adb4c9fe21bc0` |
| `model-tg-st,macro-tg` | `606b7e5673bd47d4b9bfa7d2816e4c29bbe9b42883108950b0a42067eb4f94be` |
| `6ch-usbup,model-tg-st,macro-tg,trig-hold,arp,tempo-max,boot-anim` | `b787bc07164bb4cd70f755e1bb498ca28cc1a587205d902f8c95ced09b88f5a2` |

### Machines du Machinedrum (TrxB2, TrxSD, TrxCH)

`tweaks/model-cycles_OS1.13/26-md-machines.json` (machines 7, 8 et 9) est produit par `tools/gen_md_machines.py` : les
cœurs `tools/machines/md/` (TRX-B2, TRX-SD, TRX-CH du Machinedrum UW 1.63, portés à l'échantillon près depuis son DSP) et
le pont 44,1 → 48 kHz, en charge utile à `0x43000000` avec la mécanique des machines ajoutées des moteurs du Syntakt, le
code en SRAM à la place des tables d'ondes de CHORD ([note 58](notes/58-machines-machinedrum.md)). Les tables du
Machinedrum ne sont pas dans le JSON : des recettes « md », remplies au build depuis TON `Elektron_SPS1-1UW_OS1.63.syx`
(`--md`, vérifié par son SHA-256). Le générateur a besoin de `m68k-elf-gcc` ou `m68k-linux-gnu-gcc` (`M68K_CROSS`) ; la
preuve, de `cc` pour la référence :
```sh
M68K_CROSS=m68k-elf- python3 tools/gen_md_machines.py --cycles model-cycles_OS1.13.syx \
    --md Elektron_SPS1-1UW_OS1.63.syx [--check]
python3 tools/build.py -i model-cycles_OS1.13.syx -t md-machines --md Elektron_SPS1-1UW_OS1.63.syx
python3 tools/emu/test_md_machines.py --cycles model-cycles_OS1.13.syx --md Elektron_SPS1-1UW_OS1.63.syx \
    [--with 6ch-usbup,latching-mute,trig-preview,browser-scroll,trig-hold,arp,tempo-max,boot-anim,multiline-browser,level-pan-values,trigless-dim,midi-both,chord-keys,track-filter]
```
Incompatible avec Model-TG, MACRO, les moteurs du Syntakt et SD VINTAGE (même mécanique, même place).

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `md-machines` | `ecffe87484d7254f87e4526a1eb506a3d9a9b699e1c2719d535b0cec0309ed27` |
| `6ch-usbup,md-machines` | `1e21715409d61b4ceb965eed8893f6e257961d21d5e8980d4487891cbe8445ae` |
| `6ch-usbup,latching-mute,trig-preview,browser-scroll,trig-hold,arp,tempo-max,boot-anim,multiline-browser,level-pan-values,trigless-dim,midi-both,chord-keys,track-filter,md-machines` | `1c522b9a970f994b8e9ae2902c1b5c7935229ef5b7b02c7d33ae3f13fac1d822` |

### MACRO avec les moteurs du Syntakt

`tweaks/model-cycles_OS1.13/24-syntakt-<moteurs>-macro.json` et `31-syntakt-tg-<moteurs>-macro.json` (avec Model-TG,
par-dessus `model-tg-st`) sont produits par `tools/gen_macro_syntakt.py` : les moteurs exactement comme dans leur tweak
(passerelle reprise octet pour octet, pas recompilée), MACRO en dernière machine, après eux ; la charge utile commune
(476 128 o) est rangée compressée et décompressée au démarrage ([note 50](notes/50-macro-avec-moteurs-syntakt.md)).
Mêmes besoins que les deux mods (fichier Syntakt, clone d'eurorack, `m68k-linux-gnu-g++` 13.3) :
```sh
python3 tools/gen_macro_syntakt.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx \
    --eurorack vendor/eurorack [--engines sd,cp] [--tg] [--check]
python3 tools/emu/test_macro_syntakt.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx \
    --eurorack vendor/eurorack [--engines sd,cp] [--only alone|tg] [--with 6ch-usbup,trig-hold,arp,tempo-max,boot-anim]
```

| `-t` (avec `--syntakt Syntakt_OS1.42.syx`) | MAIN OS patché (SHA-256) |
|---|---|
| `syntakt-sd-macro` | `db0cf81eb99790a7da888cd220386dd93b4ad9f5d88495b4948d22e1e791d1f3` |
| `syntakt-sd-cp-toy-bits-swarm-macro` | `10f4e481090ec12bdb73760f89cc307f9fc755060758173c24de15820217cb9f` |
| `6ch-usbup,syntakt-sd-cp-toy-bits-swarm-macro,trig-hold,arp,tempo-max,boot-anim` | `89370adafa0491712dc2d710d85a6d3bf6b60d19f6a0702ac950bde24e387b32` |
| `model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm-macro` | `9ffb2ef0b3e48350919684a58bbee24bce89af619e0eec07c5975cb9eee47b3a` |
| `6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm-macro,trig-hold,arp,tempo-max,boot-anim` | `40dcf89b6cf5822118ab1b4a27567f5b9a30451676289f5d59e606adb1832c11` |
| `6ch-usbup,model-tg-st,sample-preview-st,syntakt-tg-sd-cp-toy-bits-swarm-macro,trig-hold,arp,tempo-max,boot-anim` | `a96d9fd6927d87de6a82ecca35b92d8e3036dfa7e61ecb72ecc45e8a3f1df5aa` |

### Navigateur sur plusieurs lignes

`tweaks/model-cycles_OS1.13/44-multiline-browser.json` est produit par `tools/gen_multiline_browser.py`, qui assemble
`tools/machines/multiline_browser/multiline_browser.S` (370 o) dans le masque de sprite 47×47 libéré `0x401904b4`
(`tools/sprites.py`) : le navigateur de presets (sons, dossiers, échantillons de Model-TG) montre 3 lignes en petite police au
lieu d'une, « > » devant la ligne du curseur, le son chargé inversé, un repère de 7 px pour les dossiers. Quatre accroches dans
le dessin `0x400a539c`, huit constantes, et deux retouches de la liste dans un sous-dossier de +Drive (`0x4003f622`,
`0x400406a8`) pour que le curseur y descende sur les 3 lignes au lieu de rester sur la 1ʳᵉ ; l'accroche du défilement des noms longs (`0x400a55a1`, browser-scroll et Model-TG)
n'est pas touchée et ne sert qu'à la ligne du curseur ([note 40](notes/40-navigateur-multiligne.md)). La preuve fait tourner le
vrai dessin, avec les vraies polices, dans un vrai écran de l'OS ; `--png` écrit l'écran d'origine et le modifié :
```sh
python3 tools/gen_multiline_browser.py --cycles model-cycles_OS1.13.syx [--check]
python3 tools/emu/test_multiline_browser.py --cycles model-cycles_OS1.13.syx [--png dossier] \
    [--with 6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,trig-hold,arp,tempo-max --syntakt Syntakt_OS1.42.syx]
```

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `multiline-browser` | `75a5054403de65968e07bed84f3fcb183719b965626fd0c042b29bc963f8af31` |
| `6ch-usbup,multiline-browser` | `ce1681cd208f4ca812f25b9386ad64fd0c4aa5957314cde5ba6f77a302d2c49f` |
| `browser-scroll,multiline-browser` | `32e4a6b8e3897a1faa8ab12b33cd8e82b5a214cd3e91b80824ab17bc9d6042c1` |
| `model-tg,multiline-browser` | `428e7bc4f18fde071a201544266d97012dd41556220867b60b59df193d861221` |
| `boot-anim,multiline-browser` | `120860e74d59d207951128ed926d8e0196d9d16142c6a67b004d64510bed339e` |
| `6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,trig-hold,arp,tempo-max,boot-anim,multiline-browser` | `0787cf23a48549870bb9580b3b99e284c72056c677986671659e7f949d67d1e2` |

### Volume et pan en chiffres sur l'écran principal

`tweaks/model-cycles_OS1.13/46-level-pan-values.json` est produit par `tools/gen_level_pan.py` : d'après le mod de djd_oz,
LEVEL/DATA affiche le volume de la piste sélectionnée (0 à 127) à la place du haut-parleur, FUNC + LEVEL/DATA son pan (-64 à
63) à la place du « R », 3 s après le dernier mouvement ; LEVEL/DATA avance de 1 au lieu de 2 sur l'écran principal. Assemblé
depuis `tools/machines/level_pan/` dans deux masques de sprites libérés ([note 44](notes/44-volume-pan-en-chiffres.md)). La
preuve passe par le vrai tick de la tâche de l'interface, le pas de LEVEL/DATA, le gestionnaire des encodeurs et le dessin de
l'écran principal, compare chaque pixel au modèle pour les 256 valeurs, et, avec `--djd`, au fichier de djd_oz ; `--show`
dessine l'écran avec les barres de l'OS :
```sh
python3 tools/gen_level_pan.py --cycles model-cycles_OS1.13.syx [--check]
python3 tools/emu/test_level_pan.py --cycles model-cycles_OS1.13.syx [--show] \
    [--djd model-cycles_OS1.13_PAN-Level-values-3s-turn-only.syx] \
    [--with 6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,arp,trig-hold,tempo-max,boot-anim,trigless-dim \
     --syntakt Syntakt_OS1.42.syx]
```

### Trigless trigs atténués

`tweaks/model-cycles_OS1.13/47-trigless-dim.json` est produit par `tools/gen_trigless_dim.py` : d'après le mod de djd_oz, en
mode grille, une touche qui porte un trigless trig prend l'état de LED 260 (traité comme 4 par l'OS) ; l'interruption du
panneau, qui charge les verrous des LED, ne l'allume qu'une milliseconde sur trois (333 Hz) en rechargeant sa rangée en plus
du tour d'origine. Assemblé depuis `tools/machines/trigless_dim/` dans deux masques de sprites libérés
([note 45](notes/45-trigless-trigs-attenues.md)). La preuve fait tourner le vrai code de l'interruption du panneau, du tick des
LED et de l'image de l'interface sur une même ligne de temps, d'origine contre modifié, avec un modèle des verrous ; `--defsym`
construit les variantes d'essai (jamais versionnées, `--out` hors de `tweaks/`) :
```sh
python3 tools/gen_trigless_dim.py --cycles model-cycles_OS1.13.syx [--check]
python3 tools/gen_trigless_dim.py --cycles model-cycles_OS1.13.syx --defsym WAIT=68 --out essai-0p5us.json
python3 tools/emu/test_trigless_dim.py --cycles model-cycles_OS1.13.syx \
    [--with 6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,arp,trig-hold,tempo-max,boot-anim,level-pan-values \
     --syntakt Syntakt_OS1.42.syx]
```

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `level-pan-values` | `7fb415147e8605ab035e3fc064986b1c640cddc7ced972ad5b6ff6fcaa9f5eb7` |
| `trigless-dim` | `ff47b71399d7ab72a53f73e2e0ff0f5759e4ef20fe1da1780eb0c28e85ed4631` |
| `level-pan-values,trigless-dim` | `c4a547df87f681e27e5f7d0b04d9e08d601017577f810e2dced51eb4a68797e6` |
| `model-tg,level-pan-values,trigless-dim` | `551e86a8aa2a0288440a8e620ff1cdf11da34676489a5895f4f9a031021efd07` |
| `6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,trig-hold,arp,tempo-max,boot-anim,level-pan-values,trigless-dim` | `366aebfc88b31a9f6d8206e53fa94b76897ef7fc929ff0237aa57578e3fe7540` |

### THRU qui envoie aussi le MIDI du Cycles (d'AveyCole)

Deux tweaks d'AveyCole ([AveyCole/Modded-Cycles](https://github.com/AveyCole/Modded-Cycles), commit `ba5f8bb`), produits par
`tools/gen_midi_thru.py`, qui s'excluent ([note 53](notes/53-midi-thru-aveycole.md)) :

- `50-midi-both.json` (`midi-both`) : avec THR choisi dans CONFIG › MIDI › PORTS › OUT/THRU, le Cycles relaie le MIDI reçu et
  envoie aussi son horloge, ses notes et ses paramètres. Les trois portes de sortie (`0x4000154a`, `0x4000156a`, `0x40001590`)
  ne lisent plus le réglage. Aucune place libre.
- `51-midi-live-both.json` (`midi-live-both`) : sur la ligne OUT/THRU qui affiche THR, FUNC + appui sur LEVEL/DATA alterne THR
  seul et THR + MIDI du Cycles (valeur 2 du réglage `0x404e9b50`). `tools/machines/midi_thru/midi_thru.S` (132 o) est assemblé
  dans le masque de sprite 34×34 libéré `0x40192ba4` (`tools/sprites.py`) ; le fork le mettait en `0x40167c50`.

La preuve fait tourner les vraies portes de sortie, le vrai relais, la vraie touche de la ligne et son affichage, d'origine et
modifiés, et compare avec la version du fork :
```sh
python3 tools/gen_midi_thru.py --cycles model-cycles_OS1.13.syx [--check]
python3 tools/emu/test_midi_thru.py --cycles model-cycles_OS1.13.syx \
    [--with 6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,trig-hold,arp,tempo-max --syntakt Syntakt_OS1.42.syx]
```

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `midi-both` | `5d0755ef0bd34617bcd5adbb54f09c77cd066e7439d26cc460bbadb0090bb75f` |
| `midi-live-both` | `ca439a48cb8d818c8c09a8bfc8fa1ac391ffa5f9263e971db39ff602afce6742` |
| `6ch-usbup,midi-both` | `efc0f1c328f8b65eedd45bc20dd68b513eb091ea1c67d8d3fba0d0e60081b17a` |
| `6ch-usbup,midi-live-both` | `09f5b51061b2d387c897824984618f7f8b92d2d5028750115b3f6cb3eb2748dc` |
| `model-tg,midi-live-both` | `29e4b13b5cf8a995c163ddfd8040c7e41567f687fde27bd6985d3bf2042ca048` |
| `6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,trig-hold,arp,tempo-max,boot-anim,multiline-browser,midi-both` | `705302a9ddf03d02dc2dae40422796b476d1583261e2971560a195dd033d18a8` |
| `6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,trig-hold,arp,tempo-max,boot-anim,multiline-browser,midi-live-both` | `a00ac9d50ce7e11a92737ee54ddf782ac94ce29bdd9f40caf29cb4be434319ad` |

### Filtre par piste

`tweaks/model-cycles_OS1.13/48-track-filter.json` est produit par `tools/gen_track_filter.py` : le filtre (`track_filter.S`), les
potards, l'affichage et la sauvegarde (`tf_ui.S`) sont assemblés depuis `tools/machines/track_filter/` et liés par
`track_filter.ld` dans quinze masques de sprites 35×35 libérés (3 001 o) ; les tables sont calculées par le générateur. Quatre
paramètres de toutes les machines sur les descripteurs « Error » 1 à 4, accroche après Volume + Dist ([note 47](notes/47-filtre-piste.md)).
Incompatible avec Model-TG pour l'instant. La preuve fait tourner la vraie boucle des voix et le vrai site de l'accroche, l'OS sans
le filtre à côté, puis l'interface et la sauvegarde fonction par fonction :
```sh
python3 tools/gen_track_filter.py --cycles model-cycles_OS1.13.syx [--check]
python3 tools/emu/test_track_filter.py --cycles model-cycles_OS1.13.syx [--quick] \
    [--with 6ch-usbup,syntakt-sd-cp-toy-bits-swarm,arp,trig-hold,tempo-max,boot-anim --syntakt Syntakt_OS1.42.syx]
    [--with syntakt-sd-cp-toy-bits-swarm-macro,6ch-usbup,chord-keys,level-pan-values,trigless-dim,multiline-browser,… --syntakt Syntakt_OS1.42.syx]
```

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `track-filter` | `f5db01334779499fc0932cfdc4a23c899319d333fed98fc5169972080b662967` |
| `6ch-usbup,track-filter` | `340fb353bacb25fc2923f836b7d685a704c710e43988258cdc2d21f42b997016` |
| `6ch-usbup,syntakt-sd-cp-toy-bits-swarm,trig-hold,arp,tempo-max,boot-anim,track-filter` | `5493f878652f5050a75ed0aab4aba9b19671764455943c5dd525484465c3f5ac` |
| `macro,track-filter` | `cdbbe9725eec0ca135e4ae17bdb653b864553beb452c9eb72224e8219391a7d1` |

### LFO 2, 3, 4 (d'après DavidCaruso)

LFO 2, 3, 4 du firmware `Model-TG-VA-DR-v1` de DavidCaruso, réécrits sans ses octets ([note 56](notes/56-ajouts-davidcaruso.md)).
`60-lfo-plus.json` (`lfo-plus`, avec ou sans Model-TG) : `tools/machines/lfo_plus/lfo_plus.S` (1 844 o) dans sept
masques 34×34 libérés, mémoire de travail `0x4233f000..0x4233f49b` (§3). Son fichier n'est jamais nécessaire : la
preuve accepte `--david Model-TG-VA-DR-v1.syx` pour comparer à son binaire, sans l'exiger. Incompatible avec
`track-filter` (mêmes emplacements du son, §3.6) : `build.py` refuse les deux ensemble.

```sh
python3 tools/gen_lfo_plus.py --cycles model-cycles_OS1.13.syx [--check]
python3 tools/emu/test_lfo_plus.py --cycles model-cycles_OS1.13.syx [--with model-tg,arp] [--david Model-TG-VA-DR-v1.syx]
```

| `-t` | MAIN OS patché (SHA-256) |
|---|---|
| `lfo-plus` | `61c48e85f74bca0387871df4bd82cd8bfa770759fbfab9dc629ec62e4b9dd26c` |
| `model-tg,lfo-plus` | `32a8bbfe233fb0440f9ef622b9ee5ede0eaf7e8258d63c10aa5fcc70aad07a61` |
| `model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,lfo-plus` | `b9d7de91dfa89e973359556098dd6d94eac1e8a60517d8d7a7cfd4135971d881` |
| `macro,lfo-plus` | `213c8d74850a611f342da8fb414b142415ec0645ec86a3e80f5627b3e8c3d908` |
| `6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,trig-hold,arp,tempo-max,boot-anim,multiline-browser,lfo-plus` | `7717f596492bf1eb375e9800f7901e1769e9d1d51b0036cd8a5f28c57f5de975` |

### Écoute d'un pas en pause

`trig-preview` (et sa copie dans Model-TG) accepte le séquenceur en pause, où le met un Stop MIDI reçu même à l'arrêt : 3 octets
retouchés en `0x40148a30` ([note 34](notes/34-ecoute-en-pause.md)). La preuve passe par le vrai gestionnaire du Stop MIDI de l'OS,
puis par le mode grille :
```sh
python3 tools/emu/test_trig_preview.py --cycles model-cycles_OS1.13.syx \
    [--with 6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,arp,trig-hold --syntakt Syntakt_OS1.42.syx]
```

### Variante `6ch-usbup`

`tweaks/model-cycles_OS1.13/11-6ch-usbup.json` n'est pas écrit à la main : `tools/relocate_6ch.py` le dérive du patch 6 canaux
(stubs déplacés dans une cave ; descripteurs et table des modes USB laissés d'origine), sans l'image firmware, avec les binutils m68k.
Depuis la [note 35](notes/35-glitches-usb-multipiste.md), il rend aussi le flux USB robuste : envoi de chaque bloc au début de
l'interruption suivante (`tools/machines/usb6/feed.S`, écritures dans `tools/usb_steady.py`, les mêmes que dans Model-TG et les moteurs
du Syntakt), file alignée au démarrage, ring de 9 cases de 168 o au lieu de 8 de 192 o, copie des 6 pistes déroulée
(`tools/machines/usb6/tracks6.S`). La preuve fait tourner le vrai pilote USB de l'OS avec un contrôleur modélisé :
```sh
python3 tools/relocate_6ch.py --check                  # le fichier versionné est-il à jour ?
python3 tools/emu/test_usb_in.py --cycles model-cycles_OS1.13.syx [--seconds 2] [--long 60]   # ~15 min
```

### Machine SD VINTAGE

`tweaks/model-cycles_OS1.13/20-sdvintage-snare.json` est produit par `tools/gen_sdvintage.py`, qui compile
`tools/machines/sdvintage/sdvintage.c` pour le ColdFire du M:C (paquet `gcc-m68k-linux-gnu`, testé avec GCC 13.3).
La validation rejoue le vrai moteur de l'OS dans un émulateur (paquets Python `unicorn` et `numpy`, plus `binutils-m68k-linux-gnu`) :
```sh
python3 tools/gen_sdvintage.py --check                               # le JSON versionné correspond-il au source ?
python3 tools/emu/test_sdvintage.py -i model-cycles_OS1.13.syx       # ~2 min ; --wav dossier/ pour écouter les rendus
```
Le vrai moteur du Syntakt, à la place de SNARE ([note 17](notes/17-portage-exact-syntakt.md)) ou en 7ᵉ machine SDVtg
([note 18](notes/18-septieme-machine.md)), a ses générateurs et ses preuves (`m68k-elf-gcc` / `m68k-elf-objdump`) :
```sh
python3 tools/gen_sdvintage_exact.py --syntakt Syntakt_OS1.42.syx --check
python3 tools/gen_sdvintage_7th.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx --check
python3 tools/emu/test_sdvintage_exact.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx
python3 tools/emu/test_sdvintage_7th.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx
python3 tools/gen_syntakt_machines.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx --check
python3 tools/emu/test_syntakt_machines.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx
python3 tools/gen_syntakt_engines.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx --all --check
python3 tools/emu/test_syntakt_machines.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx \
    --tweak tweaks/model-cycles_OS1.13/24-syntakt-sd-cp-toy.json
python3 tools/emu/test_sram_scratch.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx \
    --tweak tweaks/model-cycles_OS1.13/24-syntakt-sd-cp-toy-bits-swarm.json   # SRAM empruntée (notes/26)
python3 tools/emu/test_sram_code.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx \
    --tweak tweaks/model-cycles_OS1.13/24-syntakt-sd-cp-toy-bits-swarm.json   # code du Syntakt en SRAM (notes/28)
python3 tools/emu/test_model_tg.py --cycles model-cycles_OS1.13.syx                                  # Model-TG seul (notes/31, notes/35 §3)
python3 tools/emu/test_model_tg_syntakt.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx   # version combinée
python3 tools/ref_mainos.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx --check
```
Pour ajouter un moteur : l'ajouter à `CATALOG` de `tools/gen_syntakt_engines.py` (et ses plages copiées), puis relancer
`gen_syntakt_engines.py --all` et `--all --tg`, `gen_flasher_tweaks.py`, `check_overlaps.py` et `ref_mainos.py`, et tester chaque
nouveau tweak en émulation.

## Flasher (rappel)

1. **STARTUP MENU** : éteindre, maintenir **[FUNC]**, allumer, **[TRIG 4]** (OS UPGRADE).
2. Envoyer le `.syx` modifié sur le **MIDI IN** de l'appareil (`flash.sh` / `flash.bat`, SysEx Librarian ou C6),
   par câble jack stéréo depuis une interface à sortie TRS, ou par l'adaptateur DIN fourni.
   L'upgrade par le menu de démarrage **ne marche pas en USB MIDI** — MIDI IN obligatoire.
3. Détails, tests et récupération : [`notes/06-flash-et-recuperation.md`](notes/06-flash-et-recuperation.md).

## Autre chaîne d'outils

Le C [`mischa85/elektron-firmware-tool`](https://github.com/mischa85/elektron-firmware-tool) fait le même travail
de conteneur ; voir [`notes/02-format-os-syx.md`](notes/02-format-os-syx.md).
