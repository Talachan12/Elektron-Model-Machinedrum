<div align="center">

# Modded Cycles

**Custom firmware mods for the Elektron Model:Cycles, installed from your browser in about 30 seconds.**

6-channel USB audio · Syntakt engines · Model-TG sampler · arpeggiator · up to 546 BPM · and more

[**Open the web flasher**](https://18nelli18.github.io/Modded-Cycles/flasher/) &nbsp;·&nbsp;
[Read the guide](https://18nelli18.github.io/Modded-Cycles/guide/) &nbsp;·&nbsp;
[Website](https://18nelli18.github.io/Modded-Cycles/) &nbsp;·&nbsp;
[Join the Discord](https://discord.gg/hWegtJZcmm) &nbsp;·&nbsp;
[Support on Ko-fi](https://ko-fi.com/18nelli)

<img src="docs/images/readme/device.png" alt="Drawing of a Model:Cycles with the six track pads lit and the screen showing USB AUDIO, 6 CHANNELS" width="720">

</div>

---

## Why

The Model:Cycles is a great little groovebox, but its firmware leaves some obvious things on the table:
the USB output only carries the stereo mix, there are just six machines, the tempo stops at 300 BPM,
and a few everyday gestures (muting, removing trigs) take more presses than they should.

Modded Cycles patches **your own copy** of the official OS to fix that. You pick the mods you want,
the page builds the firmware in your browser, and sends it to the Model:Cycles over USB.
Going back to the official firmware is one click away.

> [!IMPORTANT]
> **No Elektron firmware is included in this repository**, original or modified. You bring the official OS
> file from [elektron.se](https://www.elektron.se/support-downloads/modelcycles); the mods are applied to it on your computer.
> This is an independent project, not affiliated with or endorsed by Elektron. Flashing a modified OS is
> **at your own risk** and may void your warranty.

## The mods

| Mod | What you get | Status |
|---|---|---|
| **6-channel USB audio** | Each track gets its own USB channel (48 kHz / 32-bit): record six separate stems in your DAW. OS updates over USB keep working. | ✅ Tested |
| **Syntakt engines** | Up to five real Syntakt machines added next to the original six: **SD VINTAGE**, **CP VINTAGE**, **SY TOY**, **SY BITS** and **SY SWARM**, with the Syntakt's knob names and defaults. They are read from your own Syntakt OS file. | ✅ Tested |
| **Model-TG** | A full Sampler machine with seven playback modes, resampling, a beat-repeat page with master FX, slide trigs, Scale Lock and more, by [TinyGregAudio](https://github.com/TinyGregAudio/Model-TG). Works with the 6-channel mod and the Syntakt engines. | 🧪 Experimental |
| **Sample preview** | An add-on to Model-TG: on a Sampler track, press FUNC + MACHINES (preset menu) and the track's pad plays the sample under the cursor, the way presets can be heard before you pick them. A sample not yet in memory loads on the first press; if there isn't enough free memory, or while Model-TG is resampling, the press plays nothing. The track keeps its own sample. Requires Model-TG (ticking it ticks Model-TG); reuses a short piece of [Model-TG's code](tweaks/model-cycles_OS1.13/LICENSE-Model-TG) (MIT). | ✅ Tested |
| **MACRO machine** | One extra machine with the 47 synthesis models of Braids, Émilie Gillet's open-source macro-oscillator, from [her own code](https://github.com/pichenettes/eurorack): analog-style waves, FM, vowels, physical models, drums, wavetables and noises. `SHAPE` picks the model, `COLOR` and `SWEEP` shape it, `FUNC` + `PITCH` gives lo-fi (sample rate down to 4 kHz on the left, bit depth down to 2 bits on the right). Thirteen of the models are computed at 48 kHz for half the processor time. Works with Model-TG and the Syntakt engines. | ✅ Tested |
| **Machinedrum machines** | The TRX-B2 kick, TRX-SD snare and TRX-CH closed hi-hat of the Elektron Machinedrum SPS-1 UW as machines 7, 8 and 9, ported sample for sample from its DSP code. Their tables are read from your own official Machinedrum UW OS 1.63 file, dropped in the flasher. The Cycles knobs set the Machinedrum parameters; TrxCH adds a resonance control. Not with Model-TG, MACRO or the Syntakt engines. By Talachan12. | 🧪 Experimental |
| **Arpeggiator** | Hold several notes with RETRIG and they play as an arpeggio. `FUNC` + `RETRIG` adds direction (up, down, up/down, random, or in the order played) and range (1 to 4 octaves), saved with the pattern. | ✅ Tested |
| **Chord Keys** | Play the selected CHORD track with the lower `TRIG 1–16` buttons: I–VII on 1–7, the same degrees one octave higher on 8–14, then I–II two octaves higher on 15–16. T1–T6 keep their normal controls. Choose a triad, 7th, 9th, 11th or 13th for each degree in `FUNC` + `RETRIG`, saved per track and pattern. SHAPE arranges the notes (BASE, close or open voicings); COLOR blends their levels. Does not combine with Model-TG. By Nico Heuser. | ✅ Tested |
| **Tempo up to 546 BPM** | The TEMPO knob, tap tempo, MIDI clock and saved projects go past 300 BPM. Tempo-synced LFOs stay in time. | ✅ Tested |
| **Per-track filter** | Hold `MACHINES` and turn `SWEEP`: low-pass to the left, off in the centre, high-pass to the right, like a DJ mixer, with the Model:Samples' range. `CONTOUR` sets the resonance, `COLOR` and `SHAPE` a filter envelope. Real parameters: p-locks, LFO, velocity, MIDI CC 74/71. Not with Model-TG yet. | ✅ Tested |
| **LFO 2, 3, 4** | Three more LFOs per track: on the LFO page, press `LFO` again for LFO 2, 3 and 4. LFO 2 is saved with the sound and can be p-locked; LFO 3 and 4 are for live play. With or without Model-TG, not with the per-track filter. After DavidCaruso. | ✅ Tested |
| **Startup animation** | When the Model:Cycles starts, the four squares of the modded-cycles logo pop in and “modded-cycles” types itself underneath, instead of the original tile animation. Same duration. | ✅ Tested |
| **Multi-line browser** | The preset browser shows three names at once in a small font instead of one in big letters, with a `>` on the name under the cursor. From an idea by a community member. | ✅ Tested |
| **Volume and pan as numbers** | On the main screen, turning `LEVEL/DATA` shows the track's volume (0 to 127) as a number; with `FUNC` held, its pan (-64 to 63). `LEVEL/DATA` then moves in steps of 1 instead of 2 there. Based on a mod by djd_oz. | ✅ Tested |
| **Dimmed trigless trigs** | A trig key that holds a trigless trig lights dimmed, so you can tell it from a note trig. Based on a mod by djd_oz. | ✅ Tested |
| **MIDI OUT while in THRU** | With `THR` selected (CONFIG › MIDI › PORTS › OUT/THRU), the Model:Cycles forwards incoming MIDI and also sends its own clock, notes and parameter changes. `OUT` and the menu stay as they are. Best when only one side plays notes, since what comes in is passed on as it arrives. By [AveyCole](https://github.com/AveyCole/Modded-Cycles). | ✅ Tested |
| **Live MIDI OUT + THRU toggle** | With `THR` selected, hold `FUNC` and press the `LEVEL/DATA` knob to add the Cycles' own MIDI to what it forwards, or take it away. The screen stays on `THR`. By AveyCole. | ✅ Tested |
| **Easier trig removal** | A quick press on a step that holds a trig removes it, instead of opening it as a hold. | ✅ Tested |
| **Latching mute** | Hold `TRACK` and tap `FUNC`: mute mode stays on, no more holding `FUNC`. By [drumkilla](https://github.com/drumkilla/elektron-model-tweaks). | ✅ Tested |
| **Trig preview** | Sequencer stopped or paused: hold a step and press `PAGE` to hear it, with its note, length and p-locks. By drumkilla. | ✅ Tested |
| **Scrolling names** | Sound names too long for the screen scroll in the sound browser. By drumkilla. | ✅ Tested |
| **Samples OS** | Turns the Model:Cycles into a Model:Samples, built from both official OS files. Coming back needs a MIDI interface. | ✅ Tested |
| **Cycles OS for Model:Samples** | The other way round: turns a Model:Samples into a Model:Cycles, over USB, from both official OS files. Going back to the Model:Samples OS works over USB too, from the same tab. | 🧪 Experimental |
| **Mods on a Model:Samples** | Pick your machine in the Mods tab: a Model:Samples gets the Model:Cycles OS with the mods you tick (Model-TG's Sampler plays your samples), over USB, and can change mods later. The flasher always installs the Model:Cycles OS, whatever the machine. Original flasher by RDS (AIM), integrated into Modded Cycles by DaftMaple. | ✅ Tested |

The mods can be combined freely (the two MIDI THRU mods are alternatives; Samples OS and Cycles OS for Model:Samples are separate installs; Chord Keys and Model-TG not together; LFO 2, 3, 4 and the per-track filter not together). Each one is explained step by step, with the buttons to press, in the
**[guide](https://18nelli18.github.io/Modded-Cycles/guide/)**.

<p align="center">
  <img src="docs/images/readme/device-syntakt.png" alt="The MACHINES menu on the Model:Cycles screen, listing 05 Tone, 06 Chord, 07 SDVtg and 08 CPVtg" width="560"><br>
  <sub>The Syntakt engines show up as extra machines in the MACHINES menu.</sub>
</p>

## Install in four steps

<img src="docs/images/readme/flasher.png" alt="The web flasher, step 1: a list of mods with checkboxes, 6-channel USB audio ticked" width="100%">

1. **Open the [web flasher](https://18nelli18.github.io/Modded-Cycles/flasher/)** in Chrome, Edge or Opera on a desktop computer (it needs Web MIDI).
2. **Tick the mods you want.**
3. **Drop your official OS file**, `model-cycles_OS1.13.syx`, from the [Elektron download](https://www.elektron.se/support-downloads/modelcycles) (unzip it first).
   For the Syntakt engines, also drop `Syntakt_OS1.42.syx` ([download](https://www.elektron.se/support-downloads/syntakt); 1.41 works too).
4. **Connect the Model:Cycles over USB and press Flash.** Close Elektron Transfer first and leave the machine on its usual screen.
   The transfer takes about 30 seconds, then the Model:Cycles asks you to confirm with **YES**.

Everything runs in your browser: your files are never uploaded anywhere.

**Before you flash**, back up your projects and samples with Elektron Transfer.

<details>
<summary><b>Other ways to flash</b></summary>

- **Classic method.** If the fast method does not work on your setup, the flasher can also send the firmware the
  way Elektron Transfer does through `CONFIG › UPGRADE` (5 to 10 minutes).
- **Elektron Transfer.** The flasher has a *Download the .syx* button: drop that file onto Elektron Transfer yourself.
- **Command line.** See [Command line](#command-line) below.

</details>

<details>
<summary><b>Going back to the official firmware</b></summary>

Open the flasher, choose the **Official firmware** tab, drop your official OS file and flash. Before that,
set any track that uses an added machine (Syntakt engine, MACRO, Machinedrum machine or Sampler) back to one of the six original machines.

</details>

<details>
<summary><b>If something goes wrong</b></summary>

If a Model:Cycles ever stops starting, it can always be recovered from its startup menu (`FUNC` + power on, then `TRIG 4`).
That menu only listens to the **MIDI IN** port, so you need a USB-MIDI interface and the scripts described in
[`FLASH.md`](FLASH.md) (in French). The guide has a [troubleshooting section](https://18nelli18.github.io/Modded-Cycles/guide/#trouble).

</details>

## Command line

The web flasher is a port of a pure-Python toolchain that lives in this repository: no compiler and no firmware needed.

```sh
python3 tools/build.py --list                       # every available mod
python3 tools/build.py -i model-cycles_OS1.13.syx -t 6ch-usbup,latching-mute,trig-preview,browser-scroll
./flash.sh                                           # macOS / Linux  (flash.bat on Windows)
```

Details in [`BUILD.md`](BUILD.md) and [`FLASH.md`](FLASH.md) (both in French). The web flasher is checked byte for byte
against the Python build (`tools/webflash_check.sh`, `tools/webbuild_check.sh`).

## How it is made

Every mod is checked in an emulator that runs the Model:Cycles' own code, and then on a real Model:Cycles before it is
marked *Tested*. The Syntakt engines are not imitations: their code and tables are taken from your Syntakt OS file and
relocated into the Model:Cycles firmware, and they produce the same samples as the Syntakt in emulation.

The research behind it (firmware analysis, hardware architecture, engine ports, measurements) is written up in the
[technical notes](notes/README.md), in French. Release notes for each flasher version are on the
[website](https://18nelli18.github.io/Modded-Cycles/#version).

## Credits

This project stands on the work of others:

- **[scottmetoyer/ms-multi-output](https://github.com/scottmetoyer/ms-multi-output)** (MIT): the original 6-channel USB mod.
- **[drumkilla/elektron-model-tweaks](https://github.com/drumkilla/elektron-model-tweaks)** (MIT): latching mute, trig preview, scrolling names, and the `mtlib` toolkit and tweak format used by the build.
- **[TinyGregAudio/Model-TG](https://github.com/TinyGregAudio/Model-TG)** (MIT): the Sampler machine and everything that comes with it ([license](tweaks/model-cycles_OS1.13/LICENSE-Model-TG)).
- **[pichenettes/eurorack](https://github.com/pichenettes/eurorack)** (MIT): Émilie Gillet's Braids code, compiled as is for the synthesis models of the MACRO machine ([license](tweaks/model-cycles_OS1.13/LICENSE-Braids)).
- **[dagargo/elektroid](https://github.com/dagargo/elektroid)** (GPL-3.0): the Elektron Transfer update protocol behind fast USB flashing.
- **[mischa85/elektron-firmware-tool](https://github.com/mischa85/elektron-firmware-tool)** (MIT): the firmware container format and its signature, on which `mtlib` is based.
- **[mxldyn/octamax](https://github.com/mxldyn/octamax)** and **[bryantysinger/octa-bt-pt](https://github.com/bryantysinger/octa-bt-pt)**: reverse-engineering and patching methods (ideas only, no code).

## License

Modded-Cycles' own code, tweak files, website and notes are released under the [MIT License](LICENSE). Third-party
code keeps its own license: see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). No Elektron firmware is included or
licensed here; Elektron, Model:Cycles, Model:Samples and Syntakt are trademarks of Elektron Music Machines MAV AB. To
contribute, see [CONTRIBUTING.md](CONTRIBUTING.md).

If these mods are useful to you, you can support the project on **[Ko-fi](https://ko-fi.com/18nelli)**.
Questions, feedback and feature requests are welcome on the **[Discord](https://discord.gg/hWegtJZcmm)**; bug reports also fit in the [issues](https://github.com/18nelli18/Modded-Cycles/issues).
