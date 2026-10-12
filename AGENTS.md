# AGENTS.md — Modded Cycles

Guidance for coding agents working on this repository. Read this file first, then the `AGENTS.md` of every folder
you touch:

| Folder | Read before you change |
|---|---|
| [`tools/AGENTS.md`](tools/AGENTS.md) | generators, the Python build, ColdFire code, emulation proofs |
| [`tweaks/AGENTS.md`](tweaks/AGENTS.md) | the tweak JSON files and `PROVENANCE.md` |
| [`docs/AGENTS.md`](docs/AGENTS.md) | the website, the web flasher, the guide, the release notes |
| [`notes/AGENTS.md`](notes/AGENTS.md) | the technical notes |

## What this project is

Firmware mods for the **Elektron Model:Cycles, OS 1.13** (ColdFire MCF54415, big-endian m68k). A mod is a *tweak*: a
table of byte writes (`old` → `new`) applied to section 3 (the MAIN OS) of the user's **own** official `.syx`, plus,
for some mods, code compiled or assembled into free space. Users pick mods in a web flasher
(`docs/flasher/`, served by GitHub Pages at <https://18nelli18.github.io/Modded-Cycles/>), which builds the firmware in
the browser and sends it over USB. A pure-Python toolchain (`tools/build.py`) does the same build on the command line.

**Always the Model:Cycles OS, whatever the machine** (decision of 10/10/2026, notes/57). The Mods tab also flashes a
Model:Samples, but what it installs is still the Model:Cycles OS with the mods (sampling comes from Model-TG): the machine
picker only changes the packing (official Model:Samples container and signature, the 32-byte key change of notes/41,
transport `0x0F` or `0x11`; `tools/mods_for_samples.py`, `MCBuilder.modsForSamples`). Build, prove and reference a mod
once, on the Model:Cycles OS; never add a mod built on the Samples OS.

Owner: Maxime (GitHub `18nelli18`). He tests every firmware change on his own Model:Cycles.

## Hard rules

1. **Never commit an Elektron firmware image**, original or modified, or anything extracted from one (no `.syx`,
   `.zip`, extracted sections, dumps, copied routines). `.gitignore` covers `firmware/`, `*.syx`, `*.zip`, `build/`,
   `vendor/`, `*.wav`. A tweak carries only its own writes and the short `old` bytes that check the user's file; code
   taken from the Syntakt OS is extracted **at build time** from the user's file (recipes and relocation tables only,
   see notes/17). Never write that a file holds "no Elektron bytes" when it carries `old` bytes.
2. **Build from the official image only**, never on top of a previous build. Every write carries its `old` bytes and
   the build refuses a mismatch. Stock hashes are in `tweaks/model-cycles_OS1.13/device.json`.
3. **Hardware testing is Maxime's.** A new mod ships as `"status": "experimental"`. Only after he reports that it works
   on his Model:Cycles does it become `"tested"`, in a separate commit ("… tested on the Model:Cycles"). Never mark
   anything tested yourself, never claim a hardware result you did not get from him.
4. **One user-visible change, one PR**, with its docs, guide, release notes and note in the same PR. Open it as a
   draft and ask before merging; Maxime merges after testing on the hardware.
5. **Prove it in emulation first.** Every mod has a generator with `--check` and a proof under `tools/emu/` that runs
   the OS's own code (Unicorn), stock vs patched. Unproven code does not go in the flasher.
6. **Recovery must stay possible.** Only section 3 is touched; the bootloader and updater stay identical, so the
   STARTUP MENU (MIDI IN) can always bring back the official OS. The web flasher only offers tweaks that keep
   `CONFIG › UPGRADE` over USB working.
7. **Respect the licenses and credit authors.** The project is MIT (`LICENSE`); the scope and every third-party
   license are in `THIRD-PARTY-NOTICES.md`: drumkilla's tweaks and `tools/mtlib/` (MIT), elektron-firmware-tool by
   Marcel Bierling (MIT), Model-TG by TinyGregAudio (MIT, `LICENSE-Model-TG`), ms-multi-output by scottmetoyer (MIT,
   `LICENSE-ms-multi-output`), Braids by Émilie Gillet (MIT, `LICENSE-Braids`, compiled unchanged for MACRO), and `tools/webxfer_check.py`, transcribed from Elektroid (GPL-3.0-or-later). Never
   transcribe or closely paraphrase code whose license does not allow it into the repo (GPL code into MIT files, code
   with no license); check an upstream's license before porting from it, and keep its notice next to the copy. Record
   the origin and license of every tweak in `tweaks/model-cycles_OS1.13/PROVENANCE.md` (and outside code in
   `THIRD-PARTY-NOTICES.md`), set `credit` on its flasher card, and serve its MIT text with the page (`license` in
   `FEATURES`). Outside contributions are merged only under the terms of `CONTRIBUTING.md`: work sent privately needs
   its author's written OK.

## Languages

- **Talk to Maxime in French.**
- **French**: technical notes (`notes/`), `BUILD.md`, `FLASH.md`, `dossier-technique.md`, `PROVENANCE.md`, tweak
  `name`/`description`, comments and docstrings in `tools/`.
- **English**: `README.md`, commit messages, PR titles and bodies, the code of the web pages.
- **Both, side by side**: everything users see on the site (flasher cards, guide, release notes, home page), as
  `en`/`fr` pairs or `data-l="en"`/`data-l="fr"` spans. Never add one language without the other.
- User-facing text speaks to musicians: what the mod does on the machine, which buttons to press, its limits. No
  addresses or jargon there; those belong in the notes.

## Repository map

```
tweaks/model-cycles_OS1.13/   tweak JSON files (generated), device.json, PROVENANCE.md
tools/build.py                Python build: applies tweaks, checks caves, repacks and re-signs (mtlib)
tools/gen_*.py                one generator per mod: writes its tweak JSON, --check verifies it is up to date
tools/machines/<mod>/         C and assembly sources compiled into the firmware
tools/emu/                    Unicorn emulation of the OS: test_<mod>.py proofs, mcengine.py, emac.py, syntakt.py
tools/gen_flasher_tweaks.py   FEATURES list -> docs/flasher/tweaks.js (generated)
tools/crossflash.py, tools/mods_for_samples.py   one OS in the other machine's container (notes/41, 57): Samples OS tab,
                              and the mods for a Model:Samples
tools/check_overlaps.py       no firmware needed: mods that can be ticked together never write the same bytes, except
                              the same whole write or a mod applied on top of another (`requires`) (notes/49)
tools/registry.py             no firmware needed: builds tweaks/model-cycles_OS1.13/REGISTRY.md from the tweaks, the
                              registry of free space (freed sprite masks, caves, payloads) and OS hooks (notes/52)
tools/ref_mainos.py           reference hashes in docs/flasher/app.js: each mod (REF_MODS) and a sample of combinations
                              (REF_MAINOS: each card alone, every pair, the largest ones)
tools/web*_check.*, webflash_smoke.*   checks of the web flasher against the Python build (node, jsdom)
docs/                         GitHub Pages site: index.html, flasher/, guide/, assets/release.js
notes/                        numbered technical notes (French), index in notes/README.md
BUILD.md, FLASH.md            command-line build and flashing (French)
.github/                      discord.yml + scripts/discord.mjs: new versions, mod status changes and merged PRs -> Discord
README.md                     English overview for Model:Cycles owners (mod table)
LICENSE, THIRD-PARTY-NOTICES.md   MIT for the project; what it does not cover; every third-party license
CONTRIBUTING.md               terms for outside contributions
```

## Adding a feature for users (the usual PR)

Follow the shape of the last ones (tempo-max: commits `5997b4a`, `14fb9fa`, `6e592bc`; trig-hold, arp). In order:

1. **Investigate and write the note.** New file `notes/NN-<slug>.md` (next free number; 58 is the last) with the
   user's request and its source, the OS code involved (addresses, `[FAIT]`/`[HYP]`), the design, free space used and
   conflicts with other tweaks. Add a row to `notes/README.md`. See `notes/AGENTS.md`.
2. **Write the generator** `tools/gen_<mod>.py` (and sources under `tools/machines/<mod>/` if it has code). It reads
   the official `.syx`, checks the stock bytes, and writes `tweaks/model-cycles_OS1.13/NN-<id>.json`; `--check`
   compares with the committed file. See `tools/AGENTS.md` and `tweaks/AGENTS.md`.
3. **Prove it**: `tools/emu/test_<mod>.py`, stock vs patched, on the OS's own code, alone and with the other mods
   (`--with 6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,arp,trig-hold,… --syntakt Syntakt_OS1.42.syx`).
   `tools/check_overlaps.py` must pass: its writes overlap no tweak it can be installed with (run it with `--git` on
   the open branches too), or it declares `conflicts`. Code goes in a mask marked free in
   `tweaks/model-cycles_OS1.13/REGISTRY.md`; `python3 tools/registry.py` regenerates that file (commit it) and refuses
   a write in a mask whose sprite is not redirected.
4. **Register it**: `tweaks/model-cycles_OS1.13/PROVENANCE.md` row; `BUILD.md` section with the commands and the
   MAIN OS SHA-256 of the main combinations.
5. **Put it in the flasher**: add it to `FEATURES` in `tools/gen_flasher_tweaks.py` (`"status": "experimental"`, and
   its section `cat`), regenerate `docs/flasher/tweaks.js`, regenerate `REF_MAINOS` and `REF_MODS` with
   `tools/ref_mainos.py`, add its row texts (`FEAT` en + fr: `label`, `short`, `desc`) and guide anchor (`GUIDE_OF`) in
   `docs/flasher/app.js`, update the lists checked by `tools/webflash_smoke.js`. See `docs/AGENTS.md`.
6. **Document it for users**: a guide section in `docs/guide/index.html` (en + fr, buttons to press, limits), a new
   release at the top of `docs/assets/release.js` (en + fr), bump the `MC_BUILD` / `?v=` stamp on the pages, a row
   in the mod table of `README.md`.
7. **Validate** (below), commit, push, open a **draft** PR, and tell Maxime what to test on the machine.
8. **After his test**: a small follow-up commit flips the status to `tested` (generator `FEATURES`, `tweaks.js`,
   guide, release notes, README, note: "Testé sur la machine (JJ/MM/AAAA)"). If he reports a problem, record it in the
   note, fix, and bump the release.

A fix to an existing mod follows the same path, minus the new files: note section, generator, proof, regenerated
JSON/`tweaks.js`/`REF_MAINOS`, release entry.

## Validation before pushing

Without firmware (always possible, run them all):

```sh
python3 tools/gen_flasher_tweaks.py --check      # tweaks.js matches tweaks/
python3 tools/check_overlaps.py                  # mods ticked together never write the same bytes (notes/49), except the
                                                 # same whole write or a mod on top of another (`requires`)
python3 tools/registry.py --check                # REGISTRY.md (free space and hooks, notes/52) matches tweaks/
python3 tools/relocate_6ch.py --check            # needs m68k binutils (below)
tools/webbuild_check.sh                          # builder.js == build.py, byte for byte (node)
tools/webflash_check.sh                          # flasher.js validates .syx like mtlib (node)
tools/webflash_smoke.sh                          # the flasher page in jsdom (node, npm, network)
python3 -m py_compile tools/*.py tools/emu/*.py
```

With the official files (download them from elektron.se into `firmware/`, which is git-ignored:
`model-cycles_OS1.13.syx`, SHA-256 `44fe5862…9800640c`; `Syntakt_OS1.42.syx` for the Syntakt engines):

```sh
python3 tools/gen_<mod>.py --cycles firmware/model-cycles_OS1.13.syx --check
python3 tools/emu/test_<mod>.py --cycles firmware/model-cycles_OS1.13.syx
python3 tools/ref_mainos.py --cycles firmware/model-cycles_OS1.13.syx --syntakt firmware/Syntakt_OS1.42.syx --check
tools/webflash_smoke.sh firmware/model-cycles_OS1.13.syx firmware/Syntakt_OS1.42.syx   # the REF_MAINOS sample, each mod checked
```

Emulation needs `pip install unicorn numpy`. Code mods need the m68k toolchain (`m68k-linux-gnu-*` from the Debian/Ubuntu
packages `binutils-m68k-linux-gnu gcc-m68k-linux-gnu`, or `m68k-elf-*`); some committed outputs were compiled with a
specific GCC (SD VINTAGE v2 with `m68k-elf-gcc` 16.2, notes/16 §6), so `--check` can differ with another compiler.
If a check cannot run (no network, no toolchain), say so in the PR instead of skipping it silently.

## Commits and PRs

- Commit messages in English: a short subject saying what the user gets ("Tempo up to 546 BPM (tempo-max tweak,
  notes/38)"), a body with the why, the bullets of what changed, and how it was proven.
- Merge `main` into a feature branch rather than rebasing shared branches; regenerate `tweaks.js` and `REF_MAINOS`/`REF_MODS`
  after a merge instead of resolving their conflicts by hand.
- The PR body says what the user sees before and after, how it was proven, and **what Maxime should test on the
  machine** (which mods ticked, which buttons, what to listen or look for).
