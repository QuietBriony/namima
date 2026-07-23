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
- 2026-07-22 — `solfeggio_idm.py` v0.2 (user: drums more complex / bass fatter):
  drums become a **chopped break** — synthesize a straight-grid 2-bar break loop,
  slice into 16ths, reassemble per phrase with seeded edit ops (stutter, reverse,
  neighbor-swap, half-speed, mute; snare-roll fills; intensity grows across
  sections; swing applied at reassembly so slices stay hit-aligned; 2 ms edge
  fades). Bass becomes a **fat bus**: driven mid layer + deep sub (<100 Hz) on
  solfeggio octave-downs (174→87/43.5, 285→142.5/71.25 Hz — same non-12-TET
  pitch classes), phrase-start /4 drops, hard kick-synced duck (pump groove),
  bus glued with tanh drive; kick sub tail raised, master HP 24→21 Hz. Clean
  body-kick layer stays un-chopped under the break.
- 2026-07-22 — `solfeggio_idm.py` v0.3 (user: low end sounded crushed; wants
  soft round lows à la Axel Boman "Hello", more air, richer timbre): **stop
  saturating the low end** — sub joins the bass bus clean (drive only on the mid
  layer), split-band master (lows <150 Hz linear, light glue above), loudness via
  RMS target + soft-knee ceiling that touches only rare peaks >0.70 (the soft
  low-end body passes untouched); round deep-house kick (drive 2.2→1.5, longer
  clean tail); soft slow sidechain (breathe, not pump); new FM e-piano offbeat
  stabs (1:1 Rhodes-ish + tremolo) for the "Hello" warmth; longer airier reverb,
  thinner break level (抜け感). Measured: low-band crest 9.5→13.2 dB (crush
  undone) at equal loudness. Music quality human_gate.
- 2026-07-22 — `solfeggio_idm.py` v0.4 (user: "パターンほかに欲しい / aphex twin
  パターンでいろいろ"): pattern BANKS rotating per 8-bar section — breaks
  {xtal=laid-back, on=bouncy kick-forward, roll=jungle-ish snare work}, bell
  riffs {call, rise=ascending, spark=sparse high glints}, bass {bounce=octaves,
  offbeat=house 8ths, roll16=rolling 16ths}; per-pattern seeded loop rngs so
  editing the plan never shifts another pattern's sound. Phrase-level variation
  (mute/re-pitch) kept on top. Section band-profiles measured distinct; low-band
  crest 12.8 dB (softness kept); tests pass.
- 2026-07-22 — `solfeggio_idm.py` v0.5 (user: "よりありがたい感じ、神聖幾何学的な
  パターン"): sacred-geometry layer built from the set's own number structure —
  `sacred_triads()` groups the nine solfeggio Hz by digit root into 3-6-9 triads
  {3:(174,417,741), 6:(285,528,852), 9:(396,639,963)} (an ~111 Hz lattice with
  shared 243/324 internal differences → slow communal beating), rotating per
  section; golden-angle (1/φ) chime spiral (phyllotaxis low-discrepancy timing);
  3:4:5 polyrhythm bells (LCM 60 beats = 15-bar mandala cycle); "mirror"
  palindrome riff added to BELL_RIFFS and the plan. Blooms in intro/breakdown/
  outro, faint (0.15) under the groove. Bell-riff smoke-test threshold 5x→3x
  (the intro now intentionally carries sparse chimes). Human_gate on the sound.
