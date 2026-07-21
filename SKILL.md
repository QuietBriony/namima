# SKILL — namima offline ambient renderer (candidate)

> **Status: candidate.** Experimental subsystem. Not wired into the namima
> runtime (`sketch.js` / `audio.js`), not merged to `main`. This file is the
> **single source of truth** for the renderer's spec; `presets.yaml` mirrors the
> frequency table below and the smoke test enforces that they agree.

## Purpose

Mass-produce frequency-based ambient sources — 128 Hz / solfeggio / binaural —
from parameters, fully offline (no DAW, no realtime engine), as deterministic
48 kHz / 24-bit WAV. Intended as reference/candidate material for namima's
family-safe ambient direction; **generated WAVs are never committed** (see
`.gitignore`), audio is self-synthesised (namima rule 5).

## Frequency presets

Absolute fundamentals (Hz). `presets.yaml → frequencies` must equal this table.

| preset name     | Hz  | note                                        |
|-----------------|-----|---------------------------------------------|
| `c3_128`        | 128 | ≈ C3 at A=432 (nominal 128; ET C3@432=128.43)|
| `c5_528`        | 528 | ≈ C5 at A=444 (also solfeggio 528)          |
| `solfeggio_174` | 174 | solfeggio                              |
| `solfeggio_285` | 285 | solfeggio                              |
| `solfeggio_396` | 396 | solfeggio                              |
| `solfeggio_417` | 417 | solfeggio                              |
| `solfeggio_528` | 528 | solfeggio                              |
| `solfeggio_639` | 639 | solfeggio                              |
| `solfeggio_741` | 741 | solfeggio                              |
| `solfeggio_852` | 852 | solfeggio                              |
| `solfeggio_963` | 963 | solfeggio                              |

**Tuning**: `432 / 440 / 444` (A4 reference). The preset frequencies above are
absolute and already bake in their intended tuning; `tuning` is recorded as
provenance and is only *applied* when deriving a base frequency from a note via
`note_to_freq(note, tuning)`. Note the equal-tempered result differs slightly
from the rounded preset: `note_to_freq("C3", 432) ≈ 128.43` (the `c3_128` preset
is the nominal 128.0), while `note_to_freq("C5", 444) ≈ 528.0` matches closely.

## Layer composition

- **Fundamental drone** + **octave partials** (default `±1`, configurable e.g.
  `-2,-1,1,2`); each octave is −6 dB from the fundamental.
- **Micro-detune** (default 6 cents): each partial is a 3-voice cluster spread by
  ±`detune_cents`, producing slow beating (うなり).
- **Slow amplitude LFO**: rate `0.05–0.2 Hz` (default 0.1), depth 0–~0.2.
- **Optional binaural**: `binaural_offset` `2–8 Hz` transposes the **whole**
  right-channel tone to `f0 + offset` — the fundamental beats at `offset` Hz and
  each octave partial at a multiple of it; `0` keeps L == R (mono-safe).
- **Fade in/out**: `fade_s` deterministic raised-cosine fade (skipped when
  `loop=true`).
- **Loop support**: `loop=true` omits the fades. Note this alone is **not**
  click-free for arbitrary frequencies — a seamless loop needs a `duration` that
  is a whole number of cycles of the fundamental (a proper tail→head crossfade is
  a future TODO).

## Output

- WAV **48 kHz / 24-bit**, stereo, little-endian PCM (stdlib `wave`;
  `scipy.io.wavfile` cannot write 24-bit).
- Variable length: default **10 min** (`duration_s: 600`); **5 s smoke mode**
  (`--smoke`, `smoke_duration_s`) for CI/tests.
- Deterministic: identical output for a fixed `seed`.

## Usage

```bash
pip install -r requirements.txt            # numpy + scipy (candidate deps)

# render a preset (10-min default) to WAV
PYTHONPATH=src python -m namima.generator --preset c3_128 --out drone.wav

# 5-second binaural solfeggio smoke clip
PYTHONPATH=src python -m namima.generator --preset solfeggio_528 --smoke \
    --binaural 4 --out beat.wav

# explicit frequency / note + tuning
PYTHONPATH=src python -m namima.generator --note C3 --tuning 432 --out c3.wav
```

Programmatic:

```python
from namima import render
stereo, meta = render(128.0, tuning=432, duration=600, binaural_offset=0,
                      seed=0, out_path="drone.wav")
```

## Tests

```bash
PYTHONPATH=src python -m pytest tests/        # or: python tests/test_generator.py
```

5-second smoke checks: waveform length, no clipping, fundamental via FFT,
determinism (seed), 24-bit WAV round-trip, binaural separation, and
`presets.yaml` ↔ this table sync.

## Future slot (interface only — TODO)

`add_reference_layer(stereo, asset_path, target_freq, ...)` — pitch-correct an
`assets/` WAV (e.g. a BandLab export) toward `target_freq` and underlay it. The
signature is reserved and raises `NotImplementedError`; implementation is
deferred to a follow-up candidate.

## Boundaries (namima rules)

- numpy + scipy **only**; `presets.yaml` is read by a built-in loader (no PyYAML).
- **No dependencies merged without approval** (rule 6) — see `requirements.txt`.
- **No GitHub Actions added** (rule 7) — tests run locally/pytest; CI wiring is a
  separate human-approved step.
- Generated audio is **not committed**; no samples/lyrics in the repo (rule 5).
- Candidate: no change to runtime files; merge only after human review.
