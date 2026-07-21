# Namima

Namima is the Music Stack public-friendly ambient surface. It turns Music /
Hazama FM / Band Room `SYNC` metadata into safe water, garden, transparent, or
soft sleep mood. It does not store audio, samples, lyrics, raw mic buffers, or
raw pointer streams.

Use it:

```powershell
python -m http.server
```

Then open `index.html` and tap the surface to start audio (it never auto-starts).
After the first tap it self-plays: a gentle "bloom" voice keeps drawing soft notes
from the current tide pool, and the tide slowly breathes between home / deep /
bright moods over a few minutes. Your taps add ripples on top — the bloom recedes
while you play and returns when you go quiet. Press `Music SYNC` to inspect a packet.

Checks:

```powershell
node scripts/check-mood-profiles.mjs
node scripts/check-music-session-adapter.mjs
node scripts/check-pwa-static.mjs
```

More detail: [docs/README.md](docs/README.md)

## Offline frequency renderer (candidate)

A separate, offline Python renderer for frequency-based ambient sources
(128 Hz / solfeggio / binaural → 48 kHz / 24-bit WAV). It is a **candidate**
subsystem: not wired into the runtime above, generated audio is never committed,
and its numpy/scipy deps are **pending human approval** (namima rule 6).

Spec + presets: [SKILL.md](SKILL.md) / [presets.yaml](presets.yaml). Code in
`src/namima/`, tests in `tests/`.

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m namima.generator --preset c3_128 --smoke --out drone.wav
PYTHONPATH=src python -m pytest tests/     # or: python tests/test_generator.py
```
