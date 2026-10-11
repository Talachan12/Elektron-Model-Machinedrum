# TrxB2 — the Machinedrum TRX-B2 kick on the Model:Cycles

A 7th machine for the **Elektron Model:Cycles (OS 1.13)**: the **TRX-B2** bass drum of the **Elektron Machinedrum
SPS-1 UW (OS 1.63)**, ported **sample for sample** from the Machinedrum's DSP code.

Built on [Modded-Cycles](https://github.com/18nelli18/Modded-Cycles) (same patching toolchain, same added-machine
mechanism as its MACRO machine). Tested on a real Model:Cycles.

## No Elektron bytes in this repository

You patch **your own** firmware files:

- `model-cycles_OS1.13.syx`: the official Model:Cycles OS, from elektron.se.
- `Elektron_SPS1-1UW_OS1.63.syx`: the official Machinedrum UW OS 1.63, from elektron.se.

The TRX-B2 tables (pitch, decay, hold, dirt) are read from your Machinedrum OS at build time. The 32768-point sine is
recomputed with the Machinedrum DSP's own algorithm. The tweak (`tweaks/model-cycles_OS1.13/26-trx-b2.json`) only holds
our compiled code and the recipe.

## Patch your Model:Cycles

You only need Python 3: no compiler, no extra packages.

1. Put both official `.syx` files next to this folder.
2. Run the build:
   ```bash
   python3 tools/build.py -i model-cycles_OS1.13.syx -t trx-b2 --md Elektron_SPS1-1UW_OS1.63.syx
   ```
3. Check the result. The patched MAIN OS SHA-256 must be
   `7278e2bb411fc70d27eb10e28a2ba22e5efe30a2af2caf11b8fdcef3e2700d33`. The build writes
   `model-cycles_OS1.13_mod.syx`.
4. Flash it as described in [FLASH.md](FLASH.md). You need a MIDI interface on the Cycles' **MIDI IN** (TRS jack):
   it is also your way back to the official OS (STARTUP MENU). Back up your projects first.

Flashing a modified firmware is at your own risk and may affect your warranty.

## Knobs

| Model:Cycles | TRX-B2 |
|---|---|
| PITCH (+ trig note − 60) | PTCH (same 0..127 scale as the Machinedrum; MD default is 0) |
| DECAY | DEC |
| SWEEP | RAMP |
| CONTOUR | HOLD |
| COLOR | DIST |
| SHAPE | DIRT |
| PUNCH on/off | TICK 64 / 0 |
| — | NOIS fixed at 0 |

## How faithful

- The C core (`tools/machines/trx_b2/trx_b2.c`) was compared with the original DSP56303 code run in the
  [dsp56300](https://github.com/dsp56300/dsp56300) emulator. Across 409 settings (every knob, extremes, retrigs,
  silence), every sample is identical.
- The Machinedrum runs at 44.1 kHz and the Cycles at 48 kHz. The machine renders exactly like the MD at 44.1 kHz,
  then a polyphase filter resamples it: flat to 20 kHz, ≥ 64 dB rejection of anything that would fold below 20 kHz.
- Only the machine is ported. The Cycles track stage (volume, pan, effects) applies, not the MD track filter, EQ or SRR.
- The proof `tools/emu/test_trx_b2.py` runs the real Cycles OS in Unicorn and checks:
  - boot;
  - the MACHINES screen, wheel and saves;
  - 21 sound scenarios against the host reference;
  - that the stock machines are unchanged.

## Limits

- CPU: one active TrxB2 track costs about 2× a KICK track, like the MACRO machine; a silent one costs almost nothing.
  Several TrxB2 tracks playing at once may crackle.
- It cannot be combined with the other added machines (Syntakt engines, MACRO, Model-TG). It combines with `6ch-usbup`.

## For developers

You need the m68k toolchain (`m68k-elf-*` or `m68k-linux-gnu-*`) and `pip install unicorn numpy`.

| Path | Content |
|---|---|
| `tools/machines/trx_b2/trx_b2.c` | TRX-B2 core (DSP P:$102c31/$102c4a/$102c5a + ColdFire knob function 0x201fd2) |
| `tools/machines/trx_b2/bridge.c` | Cycles voice-loop bridge, knob mapping, 44.1 → 48 kHz resampler |
| `tools/machines/trx_b2/md_os.py`, `md_sine.py`, `headers.py` | reading your MD OS, the sine algorithm, generated sources |
| `tools/gen_trx_b2.py` | builds the tweak (`--md` also proves the recipe equals the real-data build, `--check`) |
| `tools/emu/test_trx_b2.py` | emulation proof on the real Cycles OS |

Rebuild the tweak:
```bash
M68K_CROSS=m68k-elf- python3 tools/gen_trx_b2.py --cycles model-cycles_OS1.13.syx --md Elektron_SPS1-1UW_OS1.63.syx
```

Run the emulation proof:
```bash
python3 tools/emu/test_trx_b2.py --cycles model-cycles_OS1.13.syx --md Elektron_SPS1-1UW_OS1.63.syx
```

---

**PL:** Stopa TRX-B2 z Machinedruma (OS 1.63) jako 7. maszyna Model:Cycles (OS 1.13), wierna co do próbki.
Repozytorium nie zawiera żadnych bajtów Elektronu. Budujesz z własnych plików `.syx` jednym poleceniem (krok 2 powyżej),
a potem wgrywasz według FLASH.md przez MIDI IN. Robisz to na własne ryzyko.
