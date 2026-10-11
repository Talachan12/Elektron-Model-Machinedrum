# Machinedrum machines on the Model:Cycles

Three machines from the **Elektron Machinedrum SPS-1 UW (OS 1.63)**, added to the **Elektron Model:Cycles (OS 1.13)**
as machines 7–9 and ported **sample for sample** from the Machinedrum's DSP code:

| Cycles machine | Machinedrum machine | Cycles icon |
|---|---|---|
| **TrxB2** | TRX-B2, bass drum | KICK |
| **EfmBD** | EFM-BD, FM bass drum | KICK |
| **EfmSD** | EFM-SD, FM snare | SNARE |

Built on [Modded-Cycles](https://github.com/18nelli18/Modded-Cycles) (same patching toolchain, same added-machine
mechanism as its MACRO machine). TrxB2 has been tested on a real Model:Cycles. EfmBD and EfmSD are proven in
emulation; a hardware test is pending.

## No Elektron bytes in this repository

You patch **your own** firmware files:

- `model-cycles_OS1.13.syx`: the official Model:Cycles OS, from elektron.se.
- `Elektron_SPS1-1UW_OS1.63.syx`: the official Machinedrum UW OS 1.63, from elektron.se.

The Machinedrum tables (pitch, decays, hold, dirt) are read from your Machinedrum OS at build time. The 32768-point sine
is recomputed with the Machinedrum DSP's own algorithm. The tweak (`tweaks/model-cycles_OS1.13/26-md-machines.json`)
only holds our compiled code and the recipe.

## Patch your Model:Cycles

You only need Python 3: no compiler, no extra packages.

1. Put both official `.syx` files next to this folder.
2. Run the build:
   ```bash
   python3 tools/build.py -i model-cycles_OS1.13.syx -t md-machines --md Elektron_SPS1-1UW_OS1.63.syx
   ```
3. Check the result. The patched MAIN OS SHA-256 must be
   `07ab5d47c71f1815a28c64c14eef12a1dc50102d5a55b7f25b0aed1acfd76df8`. The build writes
   `model-cycles_OS1.13_mod.syx`.
4. Flash it as described in [FLASH.md](FLASH.md). You need a MIDI interface on the Cycles' **MIDI IN** (TRS jack):
   it is also your way back to the official OS (STARTUP MENU). Back up your projects first.

Flashing a modified firmware is at your own risk and may affect your warranty.

## Knobs

On all three machines, PITCH is PTCH and DECAY is DEC:

- PITCH plus (trig note − 60) gives the MD's PTCH, on the same 0..127 scale.
- DECAY gives the MD's DEC.

When PUNCH is off, the fixed values are the Machinedrum defaults.

| Cycles | TrxB2 | EfmBD | EfmSD |
|---|---|---|---|
| COLOR | DIST | MOD | MOD |
| SHAPE | DIRT | MFRQ | MFRQ |
| SWEEP | RAMP | RAMP | NOIS |
| CONTOUR | HOLD | RDEC | NDEC |
| PUNCH off / on | TICK 0 / 64 | MFB 127 / 0 | HPF 16 / 64 |
| fixed | NOIS 0 | MDEC 32 | MDEC 44 |

## How faithful

- The C cores (`tools/machines/md/trx_b2.c`, `efm.c`) were compared with the original DSP56303 code run in the
  [dsp56300](https://github.com/dsp56300/dsp56300) emulator. Every sample is identical for TRX-B2 across 409 settings,
  and for EFM-BD and EFM-SD across 303 settings each (every knob, extremes, retrigs, silence).
- The Machinedrum runs at 44.1 kHz and the Cycles at 48 kHz. The machines render exactly like the MD at 44.1 kHz,
  then a polyphase filter resamples them to 48 kHz:
  - flat to 20 kHz;
  - ≥ 64 dB rejection of anything that would fold below 20 kHz;
  - rounding error about −100 dBFS.
- Only the machines are ported. The Cycles track stage (volume, pan, effects) applies, not the MD track filter, EQ or
  SRR.
- `tools/emu/test_md_machines.py` runs the real Cycles OS in Unicorn and checks:
  - boot;
  - the MACHINES screen (9 machines), wheel, saves and machine changes;
  - 19 sound scenarios per machine against the host reference;
  - that the stock machines are unchanged.

## CPU

Instructions per audio block for the whole voice loop, with one track playing, at the attack:

| Machine | Instructions per block |
|---|---|
| KICK | ≈ 8.6k |
| TrxB2 | ≈ 10k |
| EfmBD | ≈ 11.8k |
| EfmSD | ≈ 15k |

The EFM cores multiply with the ColdFire's EMAC, as the OS's own voice loop does (MACSR 0xa0). All our code, the
resampler filter, the small Machinedrum tables and the track states run from the Cycles' internal SRAM, in place of
the CHORD wavetables, which move to SDRAM (as with the Modded-Cycles Syntakt engines). This keeps our code out of the
8 KB instruction cache; on hardware it costs far more than the instruction counts below show. The 128 KB sine table
stays in SDRAM. All six stock tracks
together take ≈ 42–51k. Some mixes:

| Six tracks | Instructions per block |
|---|---|
| 4 stock + EfmBD + EfmSD | ≈ 52k |
| 3 stock + 3 × EfmSD | ≈ 62k |
| 6 × EfmSD | ≈ 84k |

Once a machine's envelopes reach zero it costs almost nothing, and the EFM modulator and noise stop costing when
their own envelopes end. Many EfmSD tracks hit at the same moment may still overload the audio block. When that
happens, the sequencer slows down.

## Limits

- It cannot be combined with the other added machines (Syntakt engines, MACRO, Model-TG). It combines with `6ch-usbup`.
- Projects saved with the earlier TrxB2-only build keep working: TrxB2 is still machine 7.

## For developers

You need the m68k toolchain (`m68k-elf-*` or `m68k-linux-gnu-*`) and `pip install unicorn numpy`.

| Path | Content |
|---|---|
| `tools/machines/md/trx_b2.c` | TRX-B2 core (DSP P:$102c31/$102c4a/$102c5a + ColdFire knob function 0x201fd2) |
| `tools/machines/md/efm.c` | EFM-BD (P:$102eef/$102ef3/$102f06, knobs 0x20211c) and EFM-SD (P:$102f68/$102f6f/$102f85, knobs 0x2021fc) |
| `tools/machines/md/bridge.c` | Cycles voice-loop bridge, knob mapping, 44.1 → 48 kHz resampler |
| `tools/machines/md/md_os.py`, `md_sine.py`, `headers.py` | reading your MD OS, the sine algorithm, generated sources |
| `tools/gen_md_machines.py` | builds the tweak (`--md` also proves the recipe equals the real-data build, `--check`) |
| `tools/emu/test_md_machines.py` | emulation proof on the real Cycles OS |

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

---

**PL:** Trzy maszyny z Machinedruma (TRX-B2, EFM-BD, EFM-SD) jako maszyny 7–9 Model:Cycles, wierne co do próbki.
Repozytorium nie zawiera żadnych bajtów Elektronu. Budujesz z własnych plików `.syx` jednym poleceniem (krok 2
powyżej), a potem wgrywasz według FLASH.md przez MIDI IN. Robisz to na własne ryzyko.
