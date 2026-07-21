# namima — decision log

One line per decision. Newest last.

- 2026-07-12 — Parameterise frequency-based ambient generation: add an offline,
  deterministic numpy/scipy renderer (128 Hz / solfeggio / binaural → 48 kHz /
  24-bit WAV) driven by `presets.yaml`, as a **candidate** subsystem (spec in
  `SKILL.md`; no runtime change, generated audio not committed, deps pending
  human approval). See PR / branch `feat/freq-ambient-renderer-candidate`.
