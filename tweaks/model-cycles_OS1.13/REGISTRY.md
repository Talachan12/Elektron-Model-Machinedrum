# Registre de la place libre et des points d'accroche — Model:Cycles OS 1.13

Généré par `tools/registry.py` à partir des tweaks de ce dossier (notes/52) : ne pas éditer à la main. `python3 tools/registry.py` le régénère, `--check` vérifie qu'il est à jour, `--git <branche>` y ajoute à l'écran les mods d'autres branches, `--cycles <OS officiel>` vérifie le relevé des masques sur l'image.

Adresses : VA de l'OS 1.13 (la section 3 commence en `0x40000400`). Un mod qui veut de la place prend un masque marqué *libre* au §1 (`sprites.redirect_write`, voir `tools/AGENTS.md`), régénère ce fichier et le commet avec son tweak. `tools/check_overlaps.py` refuse deux mods installables ensemble aux mêmes octets ; ce registre refuse une écriture dans un masque dont le sprite n'est pas redirigé.

## En bref

- 153 tweaks, 16 402 écritures.
- Masques de sprites libérables : 164 (35 960 o), dont 25 pris (10 936 o) et **139 libres (25 024 o)**.
- Crochets sur l'OS : 85 adresses détournées, dont 56 à l'identique par des mods de familles différentes.
- Pointeurs réécrits : 54 adresses. Écritures dans des octets 0xFF hors masques : 14 zones.
- Charges utiles ajoutées après l'OS : 135 tweaks ; place restante au §3.

## 1. Masques de sprites libérés

Les masques d'un groupe sont identiques octet pour octet et chacun n'est désigné que par la constante 32 bits de son constructeur (notes/14 §5, notes/32 §11, notes/52). Faire pointer cette constante sur la copie gardée libère le masque : le rendu ne change pas et l'OS, chargé en SDRAM, n'y lit plus rien. Règles : un mod qui écrit dans un masque le redirige dans le même tweak (ou dans un tweak qu'il demande) ; personne n'écrit dans une copie gardée ; deux mods ne partagent un masque que s'ils ne s'installent jamais ensemble, ou l'un par-dessus l'autre.

### 47×47 : 21 masques de 376 o (copie gardée `0x40172220`) : 21 pris, 0 libres (0 o)

| masque | constante | état | mods (octets écrits) |
|---|---|---|---|
| `0x4016b6f8` | `0x400b133e` | pris (plein) | chord-keys (376 o) |
| `0x4016b9e8` | `0x400b131c` | pris (374/376 o) | chord-keys (374 o) |
| `0x40171f30` | `0x400b05a0` | pris (plein) | chord-keys (376 o) |
| `0x40172608` | `0x400b0544` | pris (362/376 o) | chord-keys (362 o) |
| `0x40179730` | `0x400af64a` | pris (373/376 o) | chord-keys (373 o) |
| `0x40182b38` | `0x400adfda` | pris (plein) | chord-keys (376 o) |
| `0x40182e28` | `0x400adfba` | pris (plein) | chord-keys (376 o) |
| `0x40183118` | `0x400adf9e` | pris (374/376 o) | chord-keys (374 o), sample-preview (292 o), sample-preview-st (292 o) |
| `0x40185018` | `0x400adba8` | pris (372/376 o) | chord-keys (372 o), sample-preview (300 o), sample-preview-st (300 o) |
| `0x40185968` | `0x400ada00` | pris (372/376 o) | chord-keys (372 o), sample-preview (332 o), sample-preview-st (332 o) |
| `0x40185c58` | `0x400ad9e0` | pris (374/376 o) | chord-keys (374 o), sample-preview (312 o), sample-preview-st (312 o) |
| `0x40189930` | `0x400ad328` | pris (354/376 o) | arp (354 o) |
| `0x4018a220` | `0x400ad202` | pris (359/376 o) | arp (359 o) |
| `0x4018cd48` | `0x400acdb2` | pris (plein) | chord-keys (376 o) |
| `0x4018d1b8` | `0x400acd76` | pris (372/376 o) | chord-keys (372 o) |
| `0x4018d4a8` | `0x400acd56` | pris (210/376 o) | chord-keys (210 o) |
| `0x4018dba8` | `0x400accfe` | pris (114/376 o) | trigless-dim (114 o) |
| `0x4018f4b4` | `0x400ac8d0` | pris (360/376 o) | level-pan-values (360 o) |
| `0x4018fc74` | `0x400ac81c` | pris (364/376 o) | level-pan-values (364 o) |
| `0x401904b4` | `0x400ac784` | pris (370/376 o) | multiline-browser (370 o) |
| `0x40192734` | `0x400ac2b2` | pris (318/376 o) | trigless-dim (318 o) |

### 48×22 : 42 masques de 192 o (copie gardée `0x4014b364`) : 0 pris, 42 libres (8 064 o)

| masque | constante | état | mods (octets écrits) |
|---|---|---|---|
| `0x40152d38` | `0x400b9726` | libre | |
| `0x401592bc` | `0x400b7404` | libre | |
| `0x4015943c` | `0x400b73e4` | libre | |
| `0x4015f38c` | `0x400b504a` | libre | |
| `0x40165fec` | `0x400b28b4` | libre | |
| `0x40168a84` | `0x400b1bc0` | libre | |
| `0x40168da4` | `0x400b1b32` | libre | |
| `0x4016bcd8` | `0x400b12fe` | libre | |
| `0x4016dab8` | `0x400b0f78` | libre | |
| `0x4016fae8` | `0x400b0b20` | libre | |
| `0x40170c48` | `0x400b08da` | libre | |
| `0x40171a48` | `0x400b06ec` | libre | |
| `0x40172a68` | `0x400b0508` | libre | |
| `0x40172be8` | `0x400b04ec` | libre | |
| `0x401736c8` | `0x400b036c` | libre | |
| `0x40177f28` | `0x400af962` | libre | |
| `0x40178708` | `0x400af812` | libre | |
| `0x40178fc0` | `0x400af6e2` | libre | |
| `0x401792b0` | `0x400af6a6` | libre | |
| `0x40179430` | `0x400af686` | libre | |
| `0x401795b0` | `0x400af66a` | libre | |
| `0x40179b18` | `0x400af60e` | libre | |
| `0x4017c97c` | `0x400aee4e` | libre | |
| `0x401829b8` | `0x400adff6` | libre | |
| `0x40183408` | `0x400adf7e` | libre | |
| `0x40184808` | `0x400adc40` | libre | |
| `0x40184af8` | `0x400adc04` | libre | |
| `0x40184c78` | `0x400adbe4` | libre | |
| `0x40187528` | `0x400ad742` | libre | |
| `0x401876a8` | `0x400ad726` | libre | |
| `0x40188f98` | `0x400ad3a0` | libre | |
| `0x4018a608` | `0x400ad1c6` | libre | |
| `0x4018b9c8` | `0x400ad048` | libre | |
| `0x4018bb48` | `0x400ad028` | libre | |
| `0x4018cbc8` | `0x400acdce` | libre | |
| `0x4018d038` | `0x400acd92` | libre | |
| `0x4018d798` | `0x400acd3a` | libre | |
| `0x4018f80c` | `0x400ac894` | libre | |
| `0x40190184` | `0x400ac7e0` | libre | |
| `0x40190334` | `0x400ac7a4` | libre | |
| `0x4019089c` | `0x400ac748` | libre | |
| `0x40192a24` | `0x400ac292` | libre | |

### 35×35 : 19 masques de 280 o (copie gardée `0x4014a660`) : 0 pris, 19 libres (5 320 o)

| masque | constante | état | mods (octets écrits) |
|---|---|---|---|
| `0x4014ab5c` | `0x400bb120` | libre | |
| `0x4014b85c` | `0x400bae4e` | libre | |
| `0x4014d74c` | `0x400bac28` | libre | |
| `0x401542f8` | `0x400b91d8` | libre | |
| `0x401548b4` | `0x400b903a` | libre | |
| `0x4015b8f8` | `0x400b668c` | libre | |
| `0x4015f50c` | `0x400b5028` | libre | |
| `0x401601fc` | `0x400b4b4a` | libre | |
| `0x40160864` | `0x400b48ac` | libre | |
| `0x40160b6c` | `0x400b4870` | libre | |
| `0x40160e6c` | `0x400b482e` | libre | |
| `0x401625bc` | `0x400b3e2a` | libre | |
| `0x40163fb8` | `0x400b34c8` | libre | |
| `0x4016616c` | `0x400b2898` | libre | |
| `0x40166760` | `0x400b272e` | libre | |
| `0x40167c50` | `0x400b211e` | libre | |
| `0x401696a0` | `0x400b1540` | libre | |
| `0x401699a8` | `0x400b1500` | libre | |
| `0x4016aa28` | `0x400b1480` | libre | |

### 34×34 : 14 masques de 272 o (copie gardée `0x4016bfc8`) : 1 pris, 13 libres (3 536 o)

| masque | constante | état | mods (octets écrits) |
|---|---|---|---|
| `0x4016f8c8` | `0x400b0b3c` | libre | |
| `0x40173848` | `0x400b0350` | libre | |
| `0x401780a8` | `0x400af946` | libre | |
| `0x401784e8` | `0x400af832` | libre | |
| `0x401835b8` | `0x400adedc` | libre | |
| `0x40184df8` | `0x400adbc8` | libre | |
| `0x40185308` | `0x400adb8c` | libre | |
| `0x40185f48` | `0x400ad9c4` | libre | |
| `0x40186238` | `0x400ad988` | libre | |
| `0x40189618` | `0x400ad364` | libre | |
| `0x4018af88` | `0x400ad18a` | libre | |
| `0x4018b1a8` | `0x400ad16e` | libre | |
| `0x4018ff64` | `0x400ac7fc` | libre | |
| `0x40192ba4` | `0x400ac276` | pris (132/272 o) | midi-live-both (132 o) |

### 27×27 : 24 masques de 108 o (copie gardée `0x4014a550`) : 0 pris, 24 libres (2 592 o)

| masque | constante | état | mods (octets écrits) |
|---|---|---|---|
| `0x4014a890` | `0x400bb1fc` | libre | |
| `0x4014aa34` | `0x400bb178` | libre | |
| `0x4014af84` | `0x400bb044` | libre | |
| `0x4014b05c` | `0x400bb028` | libre | |
| `0x4014b5b4` | `0x400baf2e` | libre | |
| `0x4014b784` | `0x400bae6e` | libre | |
| `0x4014e608` | `0x400ba8f2` | libre | |
| `0x40152f88` | `0x400b96ce` | libre | |
| `0x40159a04` | `0x400b71ea` | libre | |
| `0x40159adc` | `0x400b71ce` | libre | |
| `0x4015b820` | `0x400b66a8` | libre | |
| `0x4015bf24` | `0x400b6476` | libre | |
| `0x4015c9a4` | `0x400b6232` | libre | |
| `0x4015fb6c` | `0x400b4e5a` | libre | |
| `0x40160a94` | `0x400b488c` | libre | |
| `0x401617a8` | `0x400b4386` | libre | |
| `0x40161880` | `0x400b4366` | libre | |
| `0x401629dc` | `0x400b3d96` | libre | |
| `0x40163a60` | `0x400b362e` | libre | |
| `0x40167900` | `0x400b21ac` | libre | |
| `0x40167aa8` | `0x400b216c` | libre | |
| `0x40168440` | `0x400b1d7c` | libre | |
| `0x401688b4` | `0x400b1c5e` | libre | |
| `0x401698d0` | `0x400b1522` | libre | |

### 31×22 : 18 masques de 124 o (copie gardée `0x4016e980`) : 0 pris, 18 libres (2 232 o)

| masque | constante | état | mods (octets écrits) |
|---|---|---|---|
| `0x4016f7d0` | `0x400b0b5c` | libre | |
| `0x4016fd60` | `0x400b0ae4` | libre | |
| `0x40172510` | `0x400b0564` | libre | |
| `0x40178888` | `0x400af7f6` | libre | |
| `0x40179a20` | `0x400af62e` | libre | |
| `0x4017a4d4` | `0x400af43c` | libre | |
| `0x401837d8` | `0x400adeba` | libre | |
| `0x401871a0` | `0x400ad77e` | libre | |
| `0x40189838` | `0x400ad344` | libre | |
| `0x4018a510` | `0x400ad1e6` | libre | |
| `0x4018bcc8` | `0x400ad00c` | libre | |
| `0x4018f98c` | `0x400ac874` | libre | |
| `0x4018fa84` | `0x400ac858` | libre | |
| `0x4018fb7c` | `0x400ac838` | libre | |
| `0x401907a4` | `0x400ac768` | libre | |
| `0x40190a1c` | `0x400ac72c` | libre | |
| `0x40194ad4` | `0x400abeaa` | libre | |
| `0x40195a7c` | `0x400abc76` | libre | |

### 26×26 : 14 masques de 104 o (copie gardée `0x4014b4e4`) : 0 pris, 14 libres (1 456 o)

| masque | constante | état | mods (octets écrits) |
|---|---|---|---|
| `0x401573cc` | `0x400b83da` | libre | |
| `0x40160d9c` | `0x400b4850` | libre | |
| `0x40162ab4` | `0x400b3d76` | libre | |
| `0x401630e4` | `0x400b3b2e` | libre | |
| `0x401638c0` | `0x400b366a` | libre | |
| `0x40163990` | `0x400b364a` | libre | |
| `0x40163b38` | `0x400b360e` | libre | |
| `0x40166690` | `0x400b274c` | libre | |
| `0x401679d8` | `0x400b218a` | libre | |
| `0x40167b80` | `0x400b2144` | libre | |
| `0x40168c4c` | `0x400b1b80` | libre | |
| `0x40168fb4` | `0x400b1a72` | libre | |
| `0x40179c98` | `0x400af5f2` | libre | |
| `0x40186168` | `0x400ad9a4` | libre | |

### 46×31 : 7 masques de 184 o (copie gardée `0x4016be58`) : 0 pris, 7 libres (1 288 o)

| masque | constante | état | mods (octets écrits) |
|---|---|---|---|
| `0x40170ad8` | `0x400b08f6` | libre | |
| `0x40171bc8` | `0x400b06d0` | libre | |
| `0x401728f8` | `0x400b0528` | libre | |
| `0x40179140` | `0x400af6c2` | libre | |
| `0x40184988` | `0x400adc20` | libre | |
| `0x40185648` | `0x400ada58` | libre | |
| `0x401857f8` | `0x400ada1c` | libre | |

### 41×41 : 1 masques de 328 o (copie gardée `0x40187298`) : 0 pris, 1 libres (328 o)

| masque | constante | état | mods (octets écrits) |
|---|---|---|---|
| `0x4018d918` | `0x400acd1a` | libre | |

### 52×22 : 1 masques de 208 o (copie gardée `0x4014bfe4`) : 0 pris, 1 libres (208 o)

| masque | constante | état | mods (octets écrits) |
|---|---|---|---|
| `0x4016ea78` | `0x400b0d50` | libre | |

### Masques 0xFF redirigés vers `0x40154ae4` (notes/14 §5)

Trois masques entièrement à 0xFF, les plus grands ; plusieurs mods s'y partagent la place (`check_overlaps.py` garantit qu'ils n'écrivent pas les mêmes octets, ou à l'identique).

| masque | taille | constante | état | mods (octets écrits) |
|---|---|---|---|---|
| `0x4015c044` | 720 o | `0x400b6434` | pris (550/720 o) | 6ch-usbup (384 o), macro (208 o), md-machines (208 o), model-tg (208 o), model-tg-st (208 o), syntakt-* (32/32, 208 o), syntakt-*-macro (31/31, 208 o), trig-hold (166 o) |
| `0x4016cae8` | 1024 o | `0x400b1106` | pris (1016/1024 o) | arp (824 o), macro (104 o), macro-tg (96 o), md-machines (154 o), sdvintage-7th (40 o), sdvintage-exact (40 o), sdvintage-snare (973 o), syntakt-* (32/32, 80 o), syntakt-*-macro (31/31, 188 o), syntakt-tg-* (33/33, 172–188 o), syntakt-tg-*-macro (31/31, 180 o), syntakt-vintage (40 o) |
| `0x4018a788` | 1024 o | `0x400ad1aa` | pris (1016/1024 o) | arp (1016 o), sdvintage-snare (638 o) |

## 2. Autres écritures dans des octets 0xFF (caves)

Octets à 0xFF dans l'OS d'origine, hors des masques ci-dessus (tables à trous, fins de blocs). `build.py` refuse d'y écrire si l'image d'origine pointe dedans, sauf référence vérifiée à la main (`device.json`, `cave_refs_ok`).

| adresse | octets | mods |
|---|---|---|
| `0x4010df48` | 8 | model-tg, model-tg-st |
| `0x40147f22` | 2 | browser-scroll, model-tg, model-tg-st |
| `0x40147f25` | 126 | browser-scroll, model-tg, model-tg-st |
| `0x40147fa4` | 52 | browser-scroll, model-tg, model-tg-st |
| `0x40148328` | 104 | latching-mute, model-tg, model-tg-st |
| `0x401485f0` | 16 | browser-scroll, model-tg, model-tg-st |
| `0x40148662` | 348 | latching-mute, model-tg, model-tg-st |
| `0x401487e0` | 4 | latching-mute, model-tg, model-tg-st |
| `0x401487ec` | 2 | latching-mute, model-tg, model-tg-st |
| `0x401489fa` | 2 | model-tg, model-tg-st, trig-preview |
| `0x401489fd` | 246 | model-tg, model-tg-st, trig-preview |
| `0x40148af4` | 76 | model-tg, model-tg-st, trig-preview |
| `0x40148b41` | 15 | model-tg, model-tg-st, trig-preview |
| `0x40148b51` | 49 | model-tg, model-tg-st, trig-preview |

## 3. Charges utiles ajoutées après l'OS

Code trop gros pour un masque, ajouté à la fin de l'image (`at`) et copié au démarrage en mémoire (`dest`) ; les charges d'un même firmware s'enchaînent dans l'ordre `order` (notes/17, 31), ce que `check_overlaps.py` vérifie pour chaque ensemble installable. L'image ne peut pas dépasser `0x40200000`.

| mod | order | dans l'image (`at`) | octets | fin | en mémoire (`dest`) | octets | demande |
|---|---|---|---|---|---|---|---|
| sdvintage-exact | 21 | `0x401aa140` | 205 200 | `0x401dc2d0` | `0x43000000` | 205 200 |  |
| sdvintage-7th | 22 | `0x401aa140` | 218 208 | `0x401df5a0` | `0x43000000` | 218 208 |  |
| syntakt-vintage | 23 | `0x401aa140` | 218 560 | `0x401df700` | `0x43000000` | 218 560 |  |
| syntakt-bits | 24 | `0x401aa140` | 264 448 | `0x401eaa40` | `0x43000000` | 264 448 |  |
| syntakt-bits-macro | 24 | `0x401aa140` | 233 802 | `0x401e328a` | `0x43000000` | 471 792 |  |
| syntakt-bits-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-bits-swarm-macro | 24 | `0x401aa140` | 240 027 | `0x401e4adb` | `0x43000000` | 471 792 |  |
| syntakt-cp | 24 | `0x401aa140` | 260 352 | `0x401e9a40` | `0x43000000` | 260 352 |  |
| syntakt-cp-bits | 24 | `0x401aa140` | 264 448 | `0x401eaa40` | `0x43000000` | 264 448 |  |
| syntakt-cp-bits-macro | 24 | `0x401aa140` | 234 049 | `0x401e3381` | `0x43000000` | 471 792 |  |
| syntakt-cp-bits-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-cp-bits-swarm-macro | 24 | `0x401aa140` | 240 250 | `0x401e4bba` | `0x43000000` | 471 792 |  |
| syntakt-cp-macro | 24 | `0x401aa140` | 229 144 | `0x401e2058` | `0x43000000` | 471 792 |  |
| syntakt-cp-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-cp-swarm-macro | 24 | `0x401aa140` | 240 013 | `0x401e4acd` | `0x43000000` | 471 792 |  |
| syntakt-cp-toy | 24 | `0x401aa140` | 260 352 | `0x401e9a40` | `0x43000000` | 260 352 |  |
| syntakt-cp-toy-bits | 24 | `0x401aa140` | 264 448 | `0x401eaa40` | `0x43000000` | 264 448 |  |
| syntakt-cp-toy-bits-macro | 24 | `0x401aa140` | 234 254 | `0x401e344e` | `0x43000000` | 471 792 |  |
| syntakt-cp-toy-bits-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-cp-toy-bits-swarm-macro | 24 | `0x401aa140` | 240 459 | `0x401e4c8b` | `0x43000000` | 471 792 |  |
| syntakt-cp-toy-macro | 24 | `0x401aa140` | 229 399 | `0x401e2157` | `0x43000000` | 471 792 |  |
| syntakt-cp-toy-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-cp-toy-swarm-macro | 24 | `0x401aa140` | 240 229 | `0x401e4ba5` | `0x43000000` | 471 792 |  |
| syntakt-sd | 24 | `0x401aa140` | 260 352 | `0x401e9a40` | `0x43000000` | 260 352 |  |
| syntakt-sd-bits | 24 | `0x401aa140` | 264 448 | `0x401eaa40` | `0x43000000` | 264 448 |  |
| syntakt-sd-bits-macro | 24 | `0x401aa140` | 234 083 | `0x401e33a3` | `0x43000000` | 471 792 |  |
| syntakt-sd-bits-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-sd-bits-swarm-macro | 24 | `0x401aa140` | 240 287 | `0x401e4bdf` | `0x43000000` | 471 792 |  |
| syntakt-sd-cp | 24 | `0x401aa140` | 260 352 | `0x401e9a40` | `0x43000000` | 260 352 |  |
| syntakt-sd-cp-bits | 24 | `0x401aa140` | 264 448 | `0x401eaa40` | `0x43000000` | 264 448 |  |
| syntakt-sd-cp-bits-macro | 24 | `0x401aa140` | 234 278 | `0x401e3466` | `0x43000000` | 471 792 |  |
| syntakt-sd-cp-bits-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-sd-cp-bits-swarm-macro | 24 | `0x401aa140` | 240 472 | `0x401e4c98` | `0x43000000` | 471 792 |  |
| syntakt-sd-cp-macro | 24 | `0x401aa140` | 229 407 | `0x401e215f` | `0x43000000` | 471 792 |  |
| syntakt-sd-cp-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-sd-cp-swarm-macro | 24 | `0x401aa140` | 240 234 | `0x401e4baa` | `0x43000000` | 471 792 |  |
| syntakt-sd-cp-toy | 24 | `0x401aa140` | 260 352 | `0x401e9a40` | `0x43000000` | 260 352 |  |
| syntakt-sd-cp-toy-bits | 24 | `0x401aa140` | 264 448 | `0x401eaa40` | `0x43000000` | 264 448 |  |
| syntakt-sd-cp-toy-bits-macro | 24 | `0x401aa140` | 234 478 | `0x401e352e` | `0x43000000` | 471 792 |  |
| syntakt-sd-cp-toy-bits-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-sd-cp-toy-bits-swarm-macro | 24 | `0x401aa140` | 240 674 | `0x401e4d62` | `0x43000000` | 471 792 |  |
| syntakt-sd-cp-toy-macro | 24 | `0x401aa140` | 229 617 | `0x401e2231` | `0x43000000` | 471 792 |  |
| syntakt-sd-cp-toy-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-sd-cp-toy-swarm-macro | 24 | `0x401aa140` | 240 455 | `0x401e4c87` | `0x43000000` | 471 792 |  |
| syntakt-sd-macro | 24 | `0x401aa140` | 229 154 | `0x401e2062` | `0x43000000` | 471 792 |  |
| syntakt-sd-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-sd-swarm-macro | 24 | `0x401aa140` | 240 023 | `0x401e4ad7` | `0x43000000` | 471 792 |  |
| syntakt-sd-toy | 24 | `0x401aa140` | 260 352 | `0x401e9a40` | `0x43000000` | 260 352 |  |
| syntakt-sd-toy-bits | 24 | `0x401aa140` | 264 448 | `0x401eaa40` | `0x43000000` | 264 448 |  |
| syntakt-sd-toy-bits-macro | 24 | `0x401aa140` | 234 276 | `0x401e3464` | `0x43000000` | 471 792 |  |
| syntakt-sd-toy-bits-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-sd-toy-bits-swarm-macro | 24 | `0x401aa140` | 240 489 | `0x401e4ca9` | `0x43000000` | 471 792 |  |
| syntakt-sd-toy-macro | 24 | `0x401aa140` | 229 411 | `0x401e2163` | `0x43000000` | 471 792 |  |
| syntakt-sd-toy-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-sd-toy-swarm-macro | 24 | `0x401aa140` | 240 239 | `0x401e4baf` | `0x43000000` | 471 792 |  |
| syntakt-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-swarm-macro | 24 | `0x401aa140` | 239 735 | `0x401e49b7` | `0x43000000` | 471 792 |  |
| syntakt-toy | 24 | `0x401aa140` | 260 352 | `0x401e9a40` | `0x43000000` | 260 352 |  |
| syntakt-toy-bits | 24 | `0x401aa140` | 264 448 | `0x401eaa40` | `0x43000000` | 264 448 |  |
| syntakt-toy-bits-macro | 24 | `0x401aa140` | 234 050 | `0x401e3382` | `0x43000000` | 471 792 |  |
| syntakt-toy-bits-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-toy-bits-swarm-macro | 24 | `0x401aa140` | 240 250 | `0x401e4bba` | `0x43000000` | 471 792 |  |
| syntakt-toy-macro | 24 | `0x401aa140` | 229 134 | `0x401e204e` | `0x43000000` | 471 792 |  |
| syntakt-toy-swarm | 24 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-toy-swarm-macro | 24 | `0x401aa140` | 239 998 | `0x401e4abe` | `0x43000000` | 471 792 |  |
| macro | 25 | `0x401aa140` | 103 552 | `0x401c35c0` | `0x43000000` | 324 336 |  |
| md-machines | 26 | `0x401aa140` | 224 760 | `0x401e0f38` | `0x43000000` | 252 024 |  |
| model-tg | 30 | `0x401aa140` | 87 936 | `0x401bf8c0` | `0x401aa140` | 87 936 |  |
| model-tg-st | 30 | `0x401aa140` | 87 936 | `0x401bf8c0` | `0x401aa140` | 87 936 |  |
| syntakt-tg-bits | 31 | `0x401bf8c0` | 234 548 | `0x401f8cf4` | `0x46700000` | 264 448 | model-tg-st |
| syntakt-tg-bits-macro | 31 | `0x401bf8c0` | 234 074 | `0x401f8b1a` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-bits-swarm | 31 | `0x401bf8c0` | 241 508 | `0x401fa824` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-bits-swarm-macro | 31 | `0x401bf8c0` | 240 303 | `0x401fa36f` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-cp | 31 | `0x401bf8c0` | 227 772 | `0x401f727c` | `0x46700000` | 260 352 | model-tg-st |
| syntakt-tg-cp-bits | 31 | `0x401bf8c0` | 235 184 | `0x401f8f70` | `0x46700000` | 264 448 | model-tg-st |
| syntakt-tg-cp-bits-macro | 31 | `0x401bf8c0` | 234 342 | `0x401f8c26` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-cp-bits-swarm | 31 | `0x401bf8c0` | 242 020 | `0x401faa24` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-cp-bits-swarm-macro | 31 | `0x401bf8c0` | 240 532 | `0x401fa454` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-cp-macro | 31 | `0x401bf8c0` | 229 425 | `0x401f78f1` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-cp-swarm | 31 | `0x401bf8c0` | 241 508 | `0x401fa824` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-cp-swarm-macro | 31 | `0x401bf8c0` | 240 281 | `0x401fa359` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-cp-toy | 31 | `0x401bf8c0` | 228 348 | `0x401f74bc` | `0x46700000` | 260 352 | model-tg-st |
| syntakt-tg-cp-toy-bits | 31 | `0x401bf8c0` | 235 688 | `0x401f9168` | `0x46700000` | 264 448 | model-tg-st |
| syntakt-tg-cp-toy-bits-macro | 31 | `0x401bf8c0` | 234 542 | `0x401f8cee` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-cp-toy-bits-swarm | 31 | `0x401bf8c0` | 242 512 | `0x401fac10` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-cp-toy-bits-swarm-macro | 31 | `0x401bf8c0` | 240 739 | `0x401fa523` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-cp-toy-macro | 31 | `0x401bf8c0` | 229 677 | `0x401f79ed` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-cp-toy-swarm | 31 | `0x401bf8c0` | 241 980 | `0x401fa9fc` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-cp-toy-swarm-macro | 31 | `0x401bf8c0` | 240 496 | `0x401fa430` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd | 31 | `0x401bf8c0` | 227 772 | `0x401f727c` | `0x46700000` | 260 352 | model-tg-st |
| syntakt-tg-sd-bits | 31 | `0x401bf8c0` | 235 196 | `0x401f8f7c` | `0x46700000` | 264 448 | model-tg-st |
| syntakt-tg-sd-bits-macro | 31 | `0x401bf8c0` | 234 366 | `0x401f8c3e` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd-bits-swarm | 31 | `0x401bf8c0` | 242 040 | `0x401faa38` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-sd-bits-swarm-macro | 31 | `0x401bf8c0` | 240 564 | `0x401fa474` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd-cp | 31 | `0x401bf8c0` | 228 360 | `0x401f74c8` | `0x46700000` | 260 352 | model-tg-st |
| syntakt-tg-sd-cp-bits | 31 | `0x401bf8c0` | 235 712 | `0x401f9180` | `0x46700000` | 264 448 | model-tg-st |
| syntakt-tg-sd-cp-bits-macro | 31 | `0x401bf8c0` | 234 552 | `0x401f8cf8` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd-cp-bits-swarm | 31 | `0x401bf8c0` | 242 532 | `0x401fac24` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-sd-cp-bits-swarm-macro | 31 | `0x401bf8c0` | 240 752 | `0x401fa530` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd-cp-macro | 31 | `0x401bf8c0` | 229 690 | `0x401f79fa` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd-cp-swarm | 31 | `0x401bf8c0` | 242 000 | `0x401faa10` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-sd-cp-swarm-macro | 31 | `0x401bf8c0` | 240 505 | `0x401fa439` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd-cp-toy | 31 | `0x401bf8c0` | 228 856 | `0x401f76b8` | `0x46700000` | 260 352 | model-tg-st |
| syntakt-tg-sd-cp-toy-bits | 31 | `0x401bf8c0` | 236 200 | `0x401f9368` | `0x46700000` | 264 448 | model-tg-st |
| syntakt-tg-sd-cp-toy-bits-macro | 31 | `0x401bf8c0` | 234 759 | `0x401f8dc7` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd-cp-toy-bits-swarm | 31 | `0x401bf8c0` | 243 024 | `0x401fae10` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-sd-cp-toy-bits-swarm-macro | 31 | `0x401bf8c0` | 240 948 | `0x401fa5f4` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd-cp-toy-macro | 31 | `0x401bf8c0` | 229 887 | `0x401f7abf` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd-cp-toy-swarm | 31 | `0x401bf8c0` | 242 492 | `0x401fabfc` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-sd-cp-toy-swarm-macro | 31 | `0x401bf8c0` | 240 721 | `0x401fa511` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd-macro | 31 | `0x401bf8c0` | 229 427 | `0x401f78f3` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd-swarm | 31 | `0x401bf8c0` | 241 504 | `0x401fa820` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-sd-swarm-macro | 31 | `0x401bf8c0` | 240 299 | `0x401fa36b` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd-toy | 31 | `0x401bf8c0` | 228 348 | `0x401f74bc` | `0x46700000` | 260 352 | model-tg-st |
| syntakt-tg-sd-toy-bits | 31 | `0x401bf8c0` | 235 708 | `0x401f917c` | `0x46700000` | 264 448 | model-tg-st |
| syntakt-tg-sd-toy-bits-macro | 31 | `0x401bf8c0` | 234 571 | `0x401f8d0b` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd-toy-bits-swarm | 31 | `0x401bf8c0` | 242 532 | `0x401fac24` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-sd-toy-bits-swarm-macro | 31 | `0x401bf8c0` | 240 760 | `0x401fa538` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd-toy-macro | 31 | `0x401bf8c0` | 229 683 | `0x401f79f3` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-sd-toy-swarm | 31 | `0x401bf8c0` | 241 988 | `0x401faa04` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-sd-toy-swarm-macro | 31 | `0x401bf8c0` | 240 511 | `0x401fa43f` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-swarm | 31 | `0x401bf8c0` | 240 884 | `0x401fa5b4` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-swarm-macro | 31 | `0x401bf8c0` | 240 010 | `0x401fa24a` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-toy | 31 | `0x401bf8c0` | 227 760 | `0x401f7270` | `0x46700000` | 260 352 | model-tg-st |
| syntakt-tg-toy-bits | 31 | `0x401bf8c0` | 235 180 | `0x401f8f6c` | `0x46700000` | 264 448 | model-tg-st |
| syntakt-tg-toy-bits-macro | 31 | `0x401bf8c0` | 234 340 | `0x401f8c24` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-toy-bits-swarm | 31 | `0x401bf8c0` | 242 012 | `0x401faa1c` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-toy-bits-swarm-macro | 31 | `0x401bf8c0` | 240 527 | `0x401fa44f` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-toy-macro | 31 | `0x401bf8c0` | 229 403 | `0x401f78db` | `0x46700000` | 471 792 | model-tg-st |
| syntakt-tg-toy-swarm | 31 | `0x401bf8c0` | 241 492 | `0x401fa814` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-toy-swarm-macro | 31 | `0x401bf8c0` | 240 273 | `0x401fa351` | `0x46700000` | 471 792 | model-tg-st |
| macro-tg | 32 | `0x401bf8c0` | 103 964 | `0x401d8edc` | `0x46700000` | 324 336 | model-tg-st |
| syntakt-meter | 90 | `0x401aa140` | 269 056 | `0x401ebc40` | `0x43000000` | 269 056 |  |
| syntakt-tg-meter | 91 | `0x401bf8c0` | 243 472 | `0x401fafd0` | `0x46700000` | 269 056 | model-tg-st |
| syntakt-tg-profile | 92 | `0x401bf8c0` | 243 904 | `0x401fb180` | `0x46700000` | 269 056 | model-tg-st |

Fin la plus haute : `0x401fb180`, soit 20 096 o avant la limite (une charge posée sur une autre, comme les moteurs du Syntakt sur Model-TG, est déjà comptée à sa place dans la chaîne).

## 4. Points d'accroche (crochets) sur l'OS

Instructions de l'OS remplacées par un détour (`jsr`, `jmp`, `bsr.l`, `bra.l`) vers le code d'un mod, ou vers une autre fonction de l'OS. Deux mods installables ensemble ne peuvent détourner la même adresse qu'avec les mêmes octets (`check_overlaps.py`) ; sinon ils se déclarent `conflicts`. Les combinaisons de moteurs du Syntakt visent des décalages différents dans leur charge utile : une ligne par adresse et par zone visée, avec le nombre de cibles (moteurs résumés en familles : présents/total). Le rôle de chaque crochet est dans la note du mod.

| adresse | origine (hex) | détour | vers | mods | notes |
|---|---|---|---|---|---|
| `0x400004b2` | `4feffff048d700f0` | jmp | masque `0x4016cae8` +0x0 | macro, md-machines, sdvintage-7th, sdvintage-exact, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-vintage | notes/17, notes/18, notes/36 |
| `0x4000154a` | `4eb940044df8` | jsr | masque `0x40192ba4` +0x70 `midi_gate` | midi-live-both | notes/53 |
| `0x4000156a` | `4eb940044df8` | jsr | masque `0x40192ba4` +0x70 `midi_gate` | midi-live-both | notes/53 |
| `0x40001590` | `4eb940044df8` | jsr | masque `0x40192ba4` +0x70 `midi_gate` | midi-live-both | notes/53 |
| `0x400027e8` | `203c0030008072302540…` | jmp | OS `0x4019b136` | 6ch-multiout |  |
| `0x400027e8` | `203c0030008072302540…` | jmp | masque `0x4015c044` +0xd2 | 6ch-usbup | notes/36 |
| `0x400029e4` | `e7882239404a05e8d280…` | jmp | OS `0x4019b244` | 6ch-multiout |  |
| `0x400029e4` | `e7882239404a05e8d280…` | jmp | masque `0x4015c044` +0x1e0 | 6ch-usbup | notes/36 |
| `0x40002a06` | `206f002422414281d1c5…` | jmp | OS `0x4019b1e0` | 6ch-multiout |  |
| `0x40002a06` | `206f002422414281d1c5…` | jmp | masque `0x4015c044` +0x17c | 6ch-usbup | notes/36 |
| `0x40002a42` | `721320402004e3ace788…` | jmp | OS `0x4019b182` | 6ch-multiout |  |
| `0x40002a42` | `721320402004e3ace788…` | jmp | masque `0x4015c044` +0x11e | 6ch-usbup | notes/36 |
| `0x40005f36` | `b2ac00286730` | jmp | masque `0x4018dba8` +0x0 | trigless-dim | notes/45 |
| `0x40006086` | `4ef94008e77e` | jmp | masque `0x4018dba8` +0x20 | trigless-dim | notes/45 |
| `0x400081f2` | `4eb940090f48` | jsr | masque `0x4018f4b4` +0x0 | level-pan-values | notes/44 |
| `0x4001413e` | `205242a72f0a` | jmp | charge utile (image) +0x10eb6 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x400169f0` | `4feffff448d7040c` | jmp | charge utile (image) +0x4fb6 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x4001a1c4` | `4eb940016086` | jsr | masque `0x4018a788` +0x16 | arp | notes/32 |
| `0x4001aa4e` | `4fefffe048d70cfc` | jmp | masque `0x4018f4b4` +0xc | level-pan-values | notes/44 |
| `0x4001b22a` | `4e56ffc048d73cfc` | jmp | masque `0x4018f4b4` +0x78 | level-pan-values | notes/44 |
| `0x4001cb3e` | `4eb94002d138` | jsr | masque `0x40179730` +0x0 `ck_ui_menu_ctor` | chord-keys | notes/42 |
| `0x4001d25e` | `4eb940016086` | jsr | masque `0x4018a788` +0x1a | arp | notes/32 |
| `0x4001e4ca` | `4eb94000b22a` | jsr | masque `0x40183118` +0x13c `ck_shape_name` | chord-keys | notes/42 |
| `0x4001e8da` | `202f0020226a0068` | jsr | charge utile (mémoire), 14 cibles selon la combinaison | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage | notes/18, notes/31, notes/36, notes/43 |
| `0x40021f56` | `2f034e944879404a8cb8…` | jsr | charge utile (image) +0x4f16 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x4002249c` | `4eb940072490` | jsr | masque `0x4015c044` +0x28 `th_press` | trig-hold | notes/33 |
| `0x400224ee` | `2f034eb9400724a0` | jmp | cave `0x401489fa` +0x0 | model-tg, model-tg-st, trig-preview | notes/31, notes/34, notes/36 |
| `0x40022d44` | `4eb940072460` | jsr | masque `0x4015c044` +0x3a `th_hold` | trig-hold | notes/33 |
| `0x40022da6` | `4eb94006b736` | jsr | masque `0x4015c044` +0x6c `th_release` | trig-hold | notes/33 |
| `0x4002351a` | `2f024eb9400740ca` | jmp | cave `0x40148328` +0x0 | latching-mute, model-tg, model-tg-st | notes/31, notes/36 |
| `0x4002d480` | `4cef7c7c0018` | jmp | masque `0x4016cae8` +0xc0 | arp | notes/32 |
| `0x4002f7d8` | `4cef7c7c0018` | jmp | charge utile (image) +0x11350 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x40032aee` | `4cef7c7c0018` | jmp | charge utile (image) +0xd424 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x4003560a` | `4eb940044df84a8057c0…` | jmp | masque `0x40192ba4` +0x0 `midi_key` | midi-live-both | notes/53 |
| `0x4004df40` | `704c222f0004` | jmp | charge utile (mémoire), 3 cibles selon la combinaison | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage | notes/18, notes/31, notes/36, notes/43 |
| `0x4004df5c` | `7206202f0004` | jmp | charge utile (mémoire), 8 cibles selon la combinaison | macro, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-vintage | notes/18, notes/36 |
| `0x4004df5c` | `4ef9401ae84e` | jmp | charge utile (mémoire), 6 cibles selon la combinaison | macro-tg, syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31) | notes/31, notes/36, notes/43 |
| `0x4004df5c` | `7206202f0004` | jmp | charge utile (image) +0x470e | model-tg, model-tg-st | notes/31, notes/36 |
| `0x4004df76` | `7205202f0004` | jmp | charge utile (mémoire), 8 cibles selon la combinaison | macro, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-vintage | notes/18, notes/36 |
| `0x4004df76` | `4ef9401b278a` | jmp | charge utile (mémoire), 6 cibles selon la combinaison | macro-tg, syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31) | notes/31, notes/36, notes/43 |
| `0x4004df76` | `7205202f0004` | jmp | charge utile (image) +0x864a | model-tg, model-tg-st | notes/31, notes/36 |
| `0x4004dfa2` | `704c222f0004` | jmp | charge utile (mémoire), 3 cibles selon la combinaison | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage | notes/18, notes/31, notes/36, notes/43 |
| `0x40053a6c` | `4fefff8048d77cfc42af…` | jsr | OS `0x4008e6ba` | boot-anim | notes/39 |
| `0x40056610` | `4fefffd848d73cfc` | jmp | charge utile (image) +0xdbf6 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x40056b38` | `4878000448798000b990` | jsr | charge utile (image) +0xab08 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x400587f6` | `4eb940091f20` | jsr | masque `0x4018a788` +0x1b2 | arp | notes/32 |
| `0x40058ca0` | `a93c00000020` | jsr | masque `0x4015c044` +0x1f8 | 6ch-usbup, macro, md-machines, model-tg, model-tg-st, syntakt-* (32/32), syntakt-*-macro (31/31) | notes/31, notes/36 |
| `0x40058e28` | `72ff242a0008202a000c` | jsr | masque `0x4018a788` +0x0 | arp | notes/32 |
| `0x4005910e` | `4aaa0030670c2002` | jsr | masque `0x40183118` +0x0 `pv_copy` | sample-preview, sample-preview-st | notes/46 |
| `0x40059382` | `4eb94005979e` | jsr | charge utile (mémoire), 12 cibles selon la combinaison | syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31) | notes/31, notes/36 |
| `0x40059392` | `4eb940002912` | jsr | masque `0x4015c044` +0x292 | 6ch-usbup, macro, md-machines, model-tg, model-tg-st, syntakt-* (32/32), syntakt-*-macro (31/31) | notes/31, notes/36 |
| `0x400593ce` | `4eb940002912` | jsr | masque `0x4015c044` +0x292 | 6ch-usbup, macro, md-machines, model-tg, model-tg-st, syntakt-* (32/32), syntakt-*-macro (31/31) | notes/31, notes/36 |
| `0x4005981e` | `4eb9401b715c` | jsr | charge utile (mémoire) +0x3350e | syntakt-tg-* (1/33) | notes/31 |
| `0x40059872` | `4eb9401b7b54` | jsr | charge utile (mémoire) +0x3353e | syntakt-tg-* (1/33) | notes/31 |
| `0x40059dea` | `76ff781533c38c000000` | jmp | masque `0x40192734` +0x0 `td_led` | trigless-dim | notes/45 |
| `0x4005a31a` | `20065286eb88` | jmp | charge utile (mémoire), 6 cibles selon la combinaison | macro-tg, syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31) | notes/31, notes/36, notes/43 |
| `0x4005a340` | `7005b085643e` | jmp | charge utile (mémoire), 13 cibles selon la combinaison | macro, macro-tg, md-machines, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage | notes/31, notes/36, notes/43 |
| `0x4005a50a` | `724c202f0004` | jmp | charge utile (mémoire), 13 cibles selon la combinaison | macro, macro-tg, md-machines, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage | notes/31, notes/36, notes/43 |
| `0x4005a6a6` | `4ef9401ae8fc` | jmp | charge utile (mémoire), 6 cibles selon la combinaison | macro-tg, syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31) | notes/31, notes/36, notes/43 |
| `0x4005a6a6` | `7205b2826430` | jmp | charge utile (image) +0x47bc | model-tg, model-tg-st | notes/31, notes/36 |
| `0x4005a6b6` | `4ef9401ae936` | jmp | charge utile (mémoire), 6 cibles selon la combinaison | macro-tg, syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31) | notes/31, notes/36, notes/43 |
| `0x4005a6b6` | `eb8a41f940a7` | jmp | charge utile (image) +0x47f6 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x4005a8f0` | `7405b4816532` | jmp | charge utile (mémoire), 3 cibles selon la combinaison | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage | notes/18, notes/31, notes/36, notes/43 |
| `0x4005aecc` | `4feffff448d7` | jmp | charge utile (image) +0x9b66 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x4005afa0` | `4feffff448d7` | jmp | charge utile (image) +0x9ace | model-tg, model-tg-st | notes/31, notes/36 |
| `0x4005b054` | `4feffff448d7` | jmp | charge utile (image) +0x9ae8 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x4005b4a8` | `7001156b001c001c` | jmp | masque `0x4016b6f8` +0x14e `ck_storage_load_hook` | chord-keys | notes/42 |
| `0x40061564` | `1140001b48780010` | jmp | masque `0x4018d1b8` +0xea `ck_storage_init_hook` | chord-keys | notes/42 |
| `0x4007240c` | `206f00042028` | jmp | charge utile (image) +0x4828 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x40081474` | `b08365000178` | jmp | charge utile (image) +0x10ffc | model-tg, model-tg-st | notes/31, notes/36 |
| `0x4008171e` | `4ef9401b3210` | jmp | masque `0x40185968` +0x0 `pv_note` | sample-preview, sample-preview-st | notes/46 |
| `0x4008173c` | `b083650001ce` | jmp | charge utile (image) +0x10fb2 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x40081908` | `4ebaf2ec588f` | jsr | masque `0x40189930` +0x102 | arp | notes/32 |
| `0x40084b8e` | `487800222d48` | jmp | charge utile (image) +0x9d98 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x40084c14` | `721b4fef0028` | jmp | charge utile (image) +0x9e1e | model-tg, model-tg-st | notes/31, notes/36 |
| `0x40094c9a` | `71aa00084fef0020` | jmp | charge utile (image) +0xd606 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x400a2638` | `eb8c48780001` | jmp | charge utile (mémoire), 14 cibles selon la combinaison | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage | notes/18, notes/31, notes/36, notes/43 |
| `0x400a26a2` | `7850428545f9` | jmp | charge utile (mémoire), 11 cibles selon la combinaison | macro-tg, md-machines, syntakt-* (27/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31) | notes/31, notes/36, notes/43 |
| `0x400a4dc4` | `700541e8000a` | jmp | charge utile (mémoire), 14 cibles selon la combinaison | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage | notes/18, notes/31, notes/36, notes/43 |
| `0x400a5588` | `2eaa028c4e95` | jmp | masque `0x401904b4` +0x2a `ml_row` | multiline-browser | notes/40 |
| `0x400a55a4` | `4fef001c226e` | jmp | masque `0x401904b4` +0x5e `ml_after` | multiline-browser | notes/40 |
| `0x400a5612` | `20522f0a20680040` | jsr | masque `0x401904b4` +0x10 `ml_bound` | multiline-browser | notes/40 |
| `0x400a576e` | `4eb940071da4` | jsr | masque `0x401904b4` +0x102 `ml_icon` | multiline-browser | notes/40 |
| `0x400a6426` | `4eb9400a3052` | jsr | masque `0x40185c58` +0x0 `pv_parse` | sample-preview, sample-preview-st | notes/46 |
| `0x400a6816` | `206800504e90` | jsr | charge utile (image) +0x116ac | model-tg, model-tg-st | notes/31, notes/36 |
| `0x400a7da8` | `2d41003c4a936730` | jmp | charge utile (image) +0x1f2a | model-tg, model-tg-st | notes/31, notes/36 |
| `0x400a7dfe` | `b08465224ef9` | jmp | charge utile (mémoire), 8 cibles selon la combinaison | macro-tg, syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31) | notes/31, notes/36, notes/43 |
| `0x400a7dfe` | `b08465222046` | jmp | charge utile (mémoire), 6 cibles selon la combinaison | syntakt-* (32/32), syntakt-*-macro (31/31) | notes/36 |
| `0x400a7e02` | `204622704c002f0a2f0e…` | jmp | charge utile (image) +0x2918 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x400a7e24` | `269522434280` | jmp | charge utile (mémoire), 7 cibles selon la combinaison | syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31) | notes/31, notes/36 |
| `0x400a8906` | `287c8000caa8` | jmp | charge utile (image) +0xddf6 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x400a956c` | `2f0a226f00084280` | jmp | charge utile (image) +0xddd6 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x400a98c4` | `22115c8124730800` | jmp | charge utile (image) +0xdcda | model-tg, model-tg-st | notes/31, notes/36 |
| `0x400a9daa` | `4feffff448d70c04` | jmp | charge utile (image) +0xdcf8 | model-tg, model-tg-st | notes/31, notes/36 |
| `0x400aae88` | `4fefffe448d71c3c` | jmp | masque `0x40185968` +0x0 `chord_audio_update` | chord-keys | notes/42 |
| `0x400ab0e4` | `d1fc4012142c` | jmp | masque `0x4018cd48` +0x0 `chord_audio_ratios` | chord-keys | notes/42 |

## 5. Pointeurs réécrits

Constantes 32 bits de l'OS (tables de fonctions, données) qui pointent maintenant vers le code ou les données d'un mod. Même regroupement qu'au §4.

| adresse | ancien | vers | mods |
|---|---|---|---|
| `0x40000532` | `401bf3d8` | masque `0x4016cae8` +0x0 | macro-tg, syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31) |
| `0x4000a94e` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4000b214` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4000b236` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4000b3ec` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4000b47e` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4000b522` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4000b662` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4000b6f4` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4000b790` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4001d5ee` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4001d902` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4001e032` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4001f32e` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x40022a84` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x40022b06` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x40029e88` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4002b438` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x40046d64` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4004e32e` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a2be` | `40a79418` | charge utile (mémoire), 3 valeurs selon la combinaison | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a2de` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a322` | `40a79418` | charge utile (mémoire), 3 valeurs selon la combinaison | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a390` | `40a79418` | charge utile (mémoire), 3 valeurs selon la combinaison | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a3aa` | `40a7ada4` | charge utile (mémoire), 3 valeurs selon la combinaison | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a4f4` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a516` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a538` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a562` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a59a` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a5d8` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a60a` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a634` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a67a` | `4010dce8` | charge utile (mémoire) +0x34008 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a6ba` | `40a79418` | charge utile (mémoire), 3 valeurs selon la combinaison | macro, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-vintage |
| `0x4005a6f0` | `40a79418` | charge utile (mémoire), 3 valeurs selon la combinaison | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a77e` | `4010dd00` | charge utile (mémoire) +0x34020 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a78a` | `4010dd00` | charge utile (mémoire) +0x34020 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a7bc` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a7dc` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a804` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a826` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a848` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a86a` | `4010dce0` | charge utile (mémoire) +0x34000 | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x4005a912` | `40a7ada4` | charge utile (mémoire), 3 valeurs selon la combinaison | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x400a2614` | `401177e4` | charge utile (mémoire) +0x33800 | macro, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-vintage |
| `0x400a2614` | `401bf51a` | charge utile (mémoire) +0x33800 | macro-tg, syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31) |
| `0x400a7d6c` | `40118628` | charge utile (mémoire), 7 valeurs selon la combinaison | macro, macro-tg, md-machines, sdvintage-7th, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31), syntakt-vintage |
| `0x400a7dc4` | `40118640` | charge utile (mémoire), 7 valeurs selon la combinaison | macro, macro-tg, md-machines, syntakt-* (32/32), syntakt-*-macro (31/31), syntakt-tg-* (33/33), syntakt-tg-*-macro (31/31) |
| `0x400a7e16` | `40118610` | charge utile (mémoire), 3 valeurs selon la combinaison | macro, md-machines, sdvintage-7th, syntakt-vintage |
| `0x400fd170` | `4000a70e` | masque `0x40179730` +0xf8 | chord-keys |
| `0x400fd174` | `4000a66a` | masque `0x40185968` +0xba | chord-keys |
| `0x400ff9cc` | `4001a0d2` | masque `0x40185018` +0x0 | chord-keys |
| `0x40118614` | `400ab6e8` | charge utile (mémoire) +0x31196 | sdvintage-exact |
| `0x40118614` | `400ab6e8` | masque `0x4018a788` +0x0 | sdvintage-snare |
| `0x4011862c` | `400ab3b0` | charge utile (mémoire) +0x31000 | sdvintage-exact |
| `0x4011862c` | `400ab3b0` | masque `0x4016cae8` +0x0 | sdvintage-snare |

## 6. Données sauvegardées (déclaré d'après les notes)

Ce que les écritures ne montrent pas : les octets des structures sauvegardées (pattern, projet) qu'un mod s'attribue. Un nouveau mod qui en prend un l'ajoute à `DECLARED` dans `tools/registry.py`, avec sa note. La mémoire où tournent les charges utiles est au §3 ; l'état que les mods gardent dans leurs masques, au §1.

| mod | ce qu'il s'attribue | source |
|---|---|---|
| arp | octet +512 de chaque piste dans le pattern : sens de l'arpège et octaves (inutilisé par l'OS, sauvegardé avec le pattern) | notes/32 §4 |

## 7. Ce que chaque mod touche

Nombre d'écritures de chaque sorte (une plage pour une famille de moteurs).

| mod | écritures | patchs | crochets | pointeurs | masques | redirections | caves | charge utile (image) | note |
|---|---|---|---|---|---|---|---|---|---|
| latching-mute | 8 | 3 | 1 | 0 | 0 | 0 | 4 |  |  |
| trig-preview | 6 | 0 | 1 | 0 | 0 | 0 | 5 |  | notes/34 |
| browser-scroll | 5 | 1 | 0 | 0 | 0 | 0 | 4 |  |  |
| 6ch-multiout | 29 | 25 | 4 | 0 | 0 | 0 | 0 |  |  |
| 6ch-usbup | 25 | 12 | 7 | 0 | 5 | 1 | 0 |  | notes/36 |
| sdvintage-snare | 10 | 4 | 0 | 2 | 2 | 2 | 0 |  | notes/16 |
| sdvintage-exact | 9 | 4 | 1 | 2 | 1 | 1 | 0 | 205 200 o | notes/17 |
| sdvintage-7th | 116 | 58 | 9 | 47 | 1 | 1 | 0 | 218 208 o | notes/18 |
| syntakt-vintage | 117 | 57 | 11 | 47 | 1 | 1 | 0 | 218 560 o |  |
| syntakt-* (32 tweaks) | 124 | 56–57 | 16–17 | 47 | 2 | 2 | 0 | 260 352–269 056 o | notes/36 |
| syntakt-*-macro (31 tweaks) | 124 | 56 | 17 | 47 | 2 | 2 | 0 | 229 134–240 674 o | notes/36 |
| macro | 122 | 56 | 14 | 48 | 2 | 2 | 0 | 103 552 o | notes/36 |
| md-machines | 123 | 56 | 15 | 48 | 2 | 2 | 0 | 224 760 o | notes/36 |
| model-tg | 142 | 94 | 32 | 0 | 1 | 1 | 14 | 87 936 o | notes/36 |
| model-tg-st | 142 | 94 | 32 | 0 | 1 | 1 | 14 | 87 936 o | notes/31 |
| syntakt-tg-* (33 tweaks) | 117–119 | 51 | 17–19 | 47 | 1 | 1 | 0 | 227 760–243 904 o | notes/31, notes/36 |
| syntakt-tg-*-macro (31 tweaks) | 117 | 51 | 17 | 47 | 1 | 1 | 0 | 229 403–240 948 o | notes/36 |
| macro-tg | 114 | 50 | 15 | 47 | 1 | 1 | 0 | 103 964 o | notes/43 |
| sample-preview | 11 | 0 | 3 | 0 | 4 | 4 | 0 |  | notes/46 |
| sample-preview-st | 11 | 0 | 3 | 0 | 4 | 4 | 0 |  | notes/46 |
| arp | 14 | 0 | 6 | 0 | 4 | 4 | 0 |  | notes/32 |
| trig-hold | 5 | 0 | 3 | 0 | 1 | 1 | 0 |  | notes/33 |
| tempo-max | 12 | 12 | 0 | 0 | 0 | 0 | 0 |  | notes/38 |
| boot-anim | 1 | 0 | 1 | 0 | 0 | 0 | 0 |  | notes/39 |
| multiline-browser | 16 | 10 | 4 | 0 | 1 | 1 | 0 |  | notes/40 |
| chord-keys | 37 | 0 | 6 | 3 | 14 | 14 | 0 |  | notes/42 |
| level-pan-values | 8 | 1 | 3 | 0 | 2 | 2 | 0 |  | notes/44 |
| trigless-dim | 8 | 1 | 3 | 0 | 2 | 2 | 0 |  | notes/45 |
| midi-both | 3 | 3 | 0 | 0 | 0 | 0 | 0 |  | notes/53 |
| midi-live-both | 6 | 0 | 4 | 0 | 1 | 1 | 0 |  | notes/53 |

