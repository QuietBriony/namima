# SKILL — namima solfeggio ambient composer (candidate)

> **Status: candidate.** Experimental subsystem, a sibling to the `generator.py`
> drone renderer. Not wired into the namima runtime (`sketch.js` / `audio.js`),
> not a product feature. Code: `src/namima/solfeggio_composer.py`. Tests:
> `tests/test_solfeggio_composer.py`.

## Purpose

Compose a ~3-minute **ambient piece** (not a single drone): a deep beat, a warm
detuned pad/sub bed that drifts across harmonic scenes, a floating ("たゆたう")
melody, an optional formant-synth wordless voice, and 888 Hz bell / 8888 Hz
sparkle accents. Fully offline, deterministic, self-synthesised.

## Locked aesthetic (user direction — do not revert)

- **Deep beat + drifting melody**, ambient. Aphex-Twin *Alberto Balsalm* = **mood
  only**.
- **No portamento / glide lead.** The melody is soft, **stable-pitch** swells that
  overlap and cross-fade. (An earlier glide-lead version was rejected as a
  "siren".)
- **Pitches are the solfeggio frequencies as absolute Hz**, sourced from
  `presets.yaml` (`solfeggio_*`), **not** snapped to 12-TET. The 89-cent
  **396 ↔ 417** step is intentional ("outside do-re-mi").
- **888 Hz** appears only as an **inharmonic bell**; **8888 Hz** only as **sparse,
  quiet "air" grains** — never a sustained/piercing tone.
- Optional **Norah-Jones-ish wordless voice** = formant-synth hum on solfeggio
  pitches.

## Hard constraints

- **numpy + scipy only.** Unlike `generator.py`, this candidate **imports
  `scipy.signal`** (`butter` / `lfilter` / `fftconvolve`) for its filters and
  reverb — recorded in `requirements.txt`.
- **Deterministic**: fixed `seed` → identical WAV. Each layer gets its own seeded
  RNG (`seed+1..+7`) so editing one layer does not perturb the others.
- **48 kHz / 24-bit** stereo WAV via the shared `generator.write_wav24`.
- **Mono-compatible.** The user auditions on an **iPhone built-in (mono) speaker**:
  the mono sum must not comb/cancel, and depth is carried by **audible mid-body
  (~120–500 Hz)**, not sub-bass (inaudible there).
- Self-synthesised only — **no samples**; generated WAVs are gitignored.

## Layers

- **Bed** — per-scene detuned pad (partials + slow "breathe" AM) over a sustained
  sub (root + octave-down). Four harmonic scenes drift `174 ⇄ 285` roots with
  near-harmonic partials; a dark↔bright lowpass crossfade opens the pad over the
  piece. Pad low-mids + sub are **sidechain-ducked** under the kick.
- **Melody** — overlapping stable-pitch swells; a seeded random walk over the
  scene's solfeggio pool with a periodic **wide leap** so it fills the register
  instead of clustering on the 396/417 pair; cross-fades (no glide).
- **Voice** (optional) — formant-synth hum: a warm `1/k^1.6` glottal source +
  breath, through three bandpass vowel formants.
- **Deep beat** — kick with an explicit **165 Hz thump + 110 Hz knock**,
  high-passed *before* saturation and driven hard so its body survives on the
  phone; soft rim backbeat; airy hats; swing + humanised timing.
- **Accents** — 888/444 Hz inharmonic **bell** on phrase heads and the breakdown
  drop/return; 8888 Hz **sparkle** grains. Both get release fades (no HF clicks).
- **Master** — high-passed, gently saturated, faded; **mono-safe M/S stereo**
  where the side is a high-passed (>1800 Hz) delayed copy, so `L+R == 2·mix`
  exactly (comb-free mono) and width lives only where the phone can't hear it.

## Structure

Intro (bed) → deep beat + melody (+ voice) enters → **breakdown** (beat drops,
bed/voice float, marked by an 888 bell) → return → outro fade. Bar boundaries of
the melody/voice lag the bed by 2 bars so scenes dissolve rather than switch.

## Usage

```bash
pip install -r requirements.txt            # numpy + scipy

PYTHONPATH=src python -m namima.solfeggio_composer --out drift.wav        # full ~3 min
PYTHONPATH=src python -m namima.solfeggio_composer --out s.wav --smoke    # 16-bar smoke
PYTHONPATH=src python -m namima.solfeggio_composer --out s.wav --no-voice --seed 7
```

```python
from namima import compose, ComposeConfig
stereo, meta = compose(ComposeConfig(bars=72, seed=528639))
```

## Tests

```bash
PYTHONPATH=src python -m pytest tests/test_solfeggio_composer.py
# or:  python tests/test_solfeggio_composer.py
```

Guards: determinism (seed), no-clip, 24-bit round-trip, **iPhone-mono
compatibility** (no Haas comb in 150–700 Hz), the **396↔417 non-12-TET microtone**,
kick mid-body audibility, presets-sourced pitches, and the breakdown structure.

## Boundaries (namima rules)

- numpy + scipy only; pitches sourced from `presets.yaml` (no re-typed table).
- No dependencies merged without approval (scipy is already pinned).
- No GitHub Actions; tests run locally / pytest.
- Generated audio is **not committed**; no samples/lyrics in the repo.
- Candidate: no runtime wiring. **Sound quality is a human-ear judgment** — an
  agent renders and self-checks structure, but does not mark the *music* "done".
```
