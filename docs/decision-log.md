# namima — decision log

One line per decision. Newest last.

- 2026-07-12 — Parameterise frequency-based ambient generation: add an offline,
  deterministic numpy/scipy renderer (128 Hz / solfeggio / binaural → 48 kHz /
  24-bit WAV) driven by `presets.yaml`, as a **candidate** subsystem (spec in
  `SKILL.md`; no runtime change, generated audio not committed, deps pending
  human approval). See PR / branch `feat/freq-ambient-renderer-candidate`.
- 2026-07-22 — Add `solfeggio_composer.py`: a second **candidate** that composes a
  ~3-min ambient *piece* (deep beat + drifting non-12-TET solfeggio melody +
  formant hum + 888/8888 accents), reusing the generator's `write_wav24` and
  sourcing its absolute pitches from `presets.yaml`. Deterministic (per-layer
  seeded RNG); mono-compatible for iPhone-speaker audition; hardened via a
  multi-lens quality audit (kick mid-body punch, mono-safe M/S stereo replacing a
  combing Haas, click-free bell/sparkle). Spec: `docs/solfeggio-composer.md`.
  **Uses scipy.signal** (unlike the generator) — see `requirements.txt`. Candidate
  only: no runtime wiring, generated audio not committed. **Music quality is a
  human-ear call; not marked done.**
- 2026-07-22 — Add `solfeggio_idm.py` (candidate): IDM sibling of the drift
  composer after feedback it was 単調/no-timbre. Aphex "Xtal"/"On" mood, 114 BPM:
  register→timbre map (174/285 bass+pad, 396-528 KS-pluck+voice, 639-963 FM
  mallet-bell riff), composed 2-bar riffs with 間 that vary per phrase, swing +
  velocity + syncopated octave bass locked to the kick, per-kick sidechain,
  mono-safe M/S master. Pitches from `presets.yaml` (absolute non-12-TET
  solfeggio). Tests: `tests/test_solfeggio_idm.py`. Same candidate boundaries;
  music quality human_gate.
