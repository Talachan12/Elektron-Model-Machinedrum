# AGENTS.md — notes/

The project's lab notebook, in **French**. Every mod and every fix has a note; the tweak's `description`, the code
comments, `BUILD.md` and the guide point to it. Read the root [`AGENTS.md`](../AGENTS.md) first, and
[`README.md`](README.md) (the index, conventions and key figures) before starting anything: most OS functions you will
need are already decoded in an earlier note.

## Before you investigate

Search the notes for the addresses and subsystems involved (`rg 0x4005 notes/`, `rg -i retrig notes/`). Useful
starting points: 03 (ColdFire platform, pitfalls), 05 (patch method and safety rules), 09 (OS 1.13 analysis),
14 §1–5 (machines, voice loop, freed sprite masks), 23/25/36 (audio load and the governor), 32–34 (keys, events,
sequencer, interface), 35 (USB audio driver), 38 (tempo and the musical clock).

## A new note

- File `NN-<slug>.md`, next free number (58 is the last), slug in French (`38-tempo-546-bpm.md`).
- Title `# NN — <what the user gets or the problem>`, then a short paragraph: the user's request and where it came
  from (Reddit, Elektronauts, Maxime, with a link and the date), the tweak file, the generator, the proof, and
  "Adresses : VA de l'OS 1.13."
- A **Réponse courte** / **En bref** section first when the question has an answer (what is possible, the limit, why).
- Then numbered sections: what the OS does (tables of addresses and roles), what depends on it, the design, where the
  code lives and what free space it takes, conflicts with other tweaks, the tweak itself, the emulation proof (a
  stock vs modified table), and what is left to check.
- Mark certainty: `[FAIT]` read in the code or decoded byte for byte, `[HYP]` hypothesis, `[À FAIRE]` to do,
  `[FAIT en émulation]` proven in the emulator but not yet on the machine.
- Add a row to the table in `README.md` (bold summary, key facts, test status).

## Hardware results

Only Maxime tests on the machine. Record his result in a section `## N. Testé sur la machine (JJ/MM/AAAA)`: what he
flashed (which mods, which method), what he reported (quote him when useful), what was fixed after. Update the index
row ("**testé sur la machine le JJ/MM/AAAA**"). A problem he reports gets its own section with the diagnosis and the
fix, in the same note.

## Style

Plain, precise French; numbers with French separators (65 535, 546,0 BPM); addresses as `0x40058bb4`; code in fenced
blocks. Fix a statement that turned out wrong, but record later findings, hardware results and fixes in a new dated
section that says what changed, so the note keeps the story of the mod.
