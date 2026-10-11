# Machinedrum machines on the Model:Cycles

Three machines from the **Elektron Machinedrum SPS-1 UW (OS 1.63)**, added to the **Elektron Model:Cycles (OS 1.13)** as
machines 7, 8 and 9 and ported **sample for sample** from the Machinedrum's DSP code:

| Cycles machine | Machinedrum machine | Cycles icon |
|---|---|---|
| **TrxB2** | TRX-B2, bass drum | KICK |
| **TrxSD** | TRX-SD, snare drum | SNARE |
| **TrxCH** | TRX-CH, closed hi-hat | METAL |

Built on [Modded-Cycles](https://github.com/18nelli18/Modded-Cycles) (same patching toolchain, same added-machine
mechanism as its MACRO machine). TrxB2 and TrxSD have been tested on a real Model:Cycles. TrxCH is proven in emulation; a
hardware test is pending.

## No Elektron bytes in this repository

You patch **your own** firmware files:

- `model-cycles_OS1.13.syx`: the official Model:Cycles OS, from elektron.se.
- `Elektron_SPS1-1UW_OS1.63.syx`: the official Machinedrum UW OS 1.63, from elektron.se.

The following are read from your Machinedrum OS at build time:

- the knob tables, from its ColdFire OS;
- the TrxSD noise filter coefficients and its attack sample, and the TrxCH filter coefficients, from its DSP program.

The 32768-point sine is recomputed with the Machinedrum DSP's own algorithm. The tweak
(`tweaks/model-cycles_OS1.13/26-md-machines.json`) only holds our compiled code and the recipe.

## Patch your Model:Cycles

### In your browser

Open the **[web patcher](https://talachan12.github.io/Elektron-Model-Machinedrum/)**. Then:

1. Drop both official `.syx` files.
2. Click **Build**.
3. Download `model-cycles_OS1.13_md.syx`.

The firmware is built in the page (`docs/`, published by GitHub Pages, with a copy of the Modded-Cycles
`builder.js`). Nothing is uploaded. The page checks the patched MAIN OS SHA-256 against the reference, and its
output is byte for byte the same as the Python build (`node tools/md_web_check.js`).

### On the command line

You only need Python 3: no compiler, no extra packages.

1. Put both official `.syx` files next to this folder.
2. Run the build:
   ```bash
   python3 tools/build.py -i model-cycles_OS1.13.syx -t md-machines --md Elektron_SPS1-1UW_OS1.63.syx
   ```
3. Check the result. The patched MAIN OS SHA-256 must be
   `ecffe87484d7254f87e4526a1eb506a3d9a9b699e1c2719d535b0cec0309ed27`. The build writes
   `model-cycles_OS1.13_mod.syx`.

### Flash

Flash as described in [FLASH.md](FLASH.md). You need a MIDI interface on the Cycles' **MIDI IN** (TRS jack): it is also
your way back to the official OS (STARTUP MENU). Back up your projects first.

Flashing a modified firmware is at your own risk and may affect your warranty.

## Knobs

On TrxB2 and TrxSD, PITCH plus (trig note − 60) gives the MD's PTCH, on the same 0..127 scale. TRX-CH has no PTCH:
there, PITCH plus (trig note − 60) gives LPF, the tuning of its resonant filter. DECAY gives the MD's DEC on all
three. When PUNCH is off, the fixed values are the Machinedrum defaults.

TrxCH gets one extra control the Machinedrum does not expose. SWEEP sets the resonance of its two filters. The MD
always uses index 70 of the DSP's own resonance table, and SWEEP 0..127 picks any index of that table. At 70
the sound is exactly the Machinedrum's. Lower values give a darker, quieter hat; higher values give a brighter,
louder ring.

| Cycles | TrxB2 | TrxSD | TrxCH |
|---|---|---|---|
| PITCH | PTCH | PTCH | LPF (resonant filter) |
| COLOR | DIST | SNAP (noise and attack sample) | MTAL (noise ↔ six square oscillators) |
| SHAPE | DIRT | TONE (mix of the two oscillators) | HPF |
| SWEEP | RAMP | BUMP | RES: filter resonance, not on the Machinedrum (70 = the MD sound) |
| CONTOUR | HOLD | BENV | GAP (length of the tail) |
| PUNCH off / on | TICK 0 / 64 | CLIP 0 / 64 | – |
| fixed | NOIS 0 | TUNE 64 | |

## How faithful

- The C cores (`tools/machines/md/trx_b2.c`, `trx_sd.c`, `trx_ch.c`) were compared with the original DSP56303 code run
  in the [dsp56300](https://github.com/dsp56300/dsp56300) emulator. Every sample is identical for TRX-B2 across 409
  settings, for TRX-SD across 304 and for TRX-CH across 404 plus 12 3000-block tails (every knob, extremes, retrigs, silence).
- TRX-SD has a line-by-line reference (`trx_sd_ref.c`, a model of the DSP's accumulators, X/Y memory and address
  registers) and a fast version; both give the same samples as the DSP.
- The Machinedrum runs at 44.1 kHz and the Cycles at 48 kHz. The machines render exactly like the MD at 44.1 kHz,
  then a polyphase filter resamples them to 48 kHz:
  - flat to 20 kHz;
  - ≥ 64 dB rejection of anything that would fold below 20 kHz;
  - rounding error about −100 dBFS.
- Only the machines are ported. The Cycles track stage (volume, pan, effects) applies, not the MD track filter, EQ or
  SRR.
- `tools/emu/test_md_machines.py` runs the real Cycles OS in Unicorn and checks:
  - boot and the SRAM layout;
  - the MACHINES screen, wheel, saves and machine changes;
  - 19 sound scenarios per machine against the host reference;
  - that stock tracks are unchanged, alone and next to our machines.

## CPU

Instructions per audio block for the whole voice loop, with one track playing, at the attack:

| Machine | Instructions per block |
|---|---|
| KICK | ≈ 8.6k |
| TrxB2 | ≈ 10k |
| TrxSD | ≈ 13.4k |
| TrxCH | ≈ 15.3k |

The cores multiply with the ColdFire's EMAC, as the OS's own voice loop does (MACSR 0xa0). All our code, the
resampler filter, most small Machinedrum tables and the track states run from the Cycles' internal SRAM, in place of
the CHORD wavetables, which move to SDRAM (as with the Modded-Cycles Syntakt engines). This keeps our code out of the
8 KB instruction cache. The 128 KB sine, the TrxSD attack sample and the TrxCH filter tables (read once per
block) stay in SDRAM.

| Six tracks | Instructions per block |
|---|---|
| 6 × stock | ≈ 42k |
| 6 × CHORD | ≈ 51k |
| 4 stock + TrxB2 + TrxSD | ≈ 49k |
| 2 × TrxB2 + 2 × TrxSD + 2 stock | ≈ 56k |
| 3 stock + TrxB2 + TrxSD + TrxCH | ≈ 56k |
| 2 × TrxB2 + 2 × TrxSD + 2 × TrxCH | ≈ 72k |
| 6 × TrxSD | ≈ 74k |
| 6 × TrxCH | ≈ 86k |

These figures have every track hit at once. A silent machine costs almost nothing. TrxSD keeps its noise filters
running, as the Machinedrum does, because their state carries over to the next hit. TrxCH stops computing once its
tail has reached exactly zero: its next hit clears its filters.

## Limits

- It cannot be combined with the other added machines (Syntakt engines, MACRO, Model-TG). It combines with `6ch-usbup`.
- Projects saved with earlier builds: TrxB2 is still machine 7. Machine 8, EfmBD in the previous build, is now TrxSD.

## For developers

You need the m68k toolchain (`m68k-elf-*` or `m68k-linux-gnu-*`) and `pip install unicorn numpy`.

| Path | Content |
|---|---|
| `tools/machines/md/trx_b2.c` | TRX-B2 core (DSP P:$102c31/$102c4a/$102c5a + ColdFire knob function 0x201fd2) |
| `tools/machines/md/trx_sd.c` | TRX-SD core (DSP P:$10074c/$10075b/$100776 + ColdFire knob function 0x2013a6) |
| `tools/machines/md/trx_sd_ref.c`, `dsp56.h` | TRX-SD line-by-line reference (host only) |
| `tools/machines/md/trx_ch.c` | TRX-CH core (DSP P:$10201f/$102034/$10204d + ColdFire knob function 0x201800) |
| `tools/machines/md/mdmath.h` | exact 24 × 24-bit products: EMAC on the ColdFire, 32-bit C on the host |
| `tools/machines/md/bridge.c` | Cycles voice-loop bridge, knob mapping, 44.1 → 48 kHz resampler |
| `tools/machines/md/md_os.py`, `md_sine.py`, `headers.py` | reading your MD OS (ColdFire and DSP sections), the sine algorithm, generated sources |
| `tools/gen_md_machines.py` | builds the tweak (`--md` also proves the recipe equals the real-data build, `--check`) |
| `tools/emu/test_md_machines.py` | emulation proof on the real Cycles OS |
| `docs/` | web patcher, published on GitHub Pages (main, /docs); `md-data.js` is generated by `tools/gen_md_web.py`, checked by `tools/md_web_check.js` |
| `modded-cycles-site/` | the original Modded-Cycles website (flasher, guide), kept but not published here |

In the Machinedrum's DSP A, the machine tables (init / trig / render) are at P:$145af5 / $145bb6 / $145c77, indexed by
the MIDI machine id + 1.

Rebuild the tweak:
```bash
M68K_CROSS=m68k-elf- python3 tools/gen_md_machines.py --cycles model-cycles_OS1.13.syx --md Elektron_SPS1-1UW_OS1.63.syx
```

Run the emulation proof:
```bash
python3 tools/emu/test_md_machines.py --cycles model-cycles_OS1.13.syx --md Elektron_SPS1-1UW_OS1.63.syx
```
