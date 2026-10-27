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
Wait for the loading label to become `Tap to start`, then complete a tap or use
Enter/Space on the start button. A stalled audio start becomes retryable after
10 seconds; backgrounding cancels the attempt. If the CDN scripts cannot load,
the loading screen offers a reload instead of an unresponsive start control.
When a saved older app updates, its idle screen reloads once to use matching
scripts; an update does not interrupt an active or pending audio start.
After the first tap it self-plays: a gentle "bloom" voice keeps drawing soft notes
from the current tide pool, and the tide slowly breathes between home / deep /
bright moods over a few minutes. Your taps add ripples on top — the bloom recedes
while you play and returns when you go quiet. Press `Music SYNC` to inspect a packet.

Touches now play a soft water tone immediately, followed by a short answer.
Left-to-right moves continuously from lower to higher notes. A new touch takes
the lead, and the ambient voice remembers up to four played notes for 24 seconds
before drifting away. Expanding rings follow the answers. Sleep mood has one
quieter answer, and backgrounding clears pending answers and short-term memory.

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

## Delivery lane (any PC — Surface / worker / studio)

For **editable parts in Sonar**, the separate opt-in
[IDM stem exporter](docs/idm-stem-export.md) creates seven premaster parts, two
comparison WAVs and a recipe/manual in a new explicit local folder only.
It preserves the existing master, does not launch playback or a DAW, and does not
change the public PWA or the delivery catalogue below. This is an offline candidate;
actual listening and DAW import still require human review.

`namima.deliver` turns a render into the shared hand-off packet
(`-master.wav` / `-iphone.m4a` / `-handoff.md` with SHA-256 + seed recipe) and
drops it in the Google Drive folder every machine syncs (`マイドライブ/AI連携/Music`,
override with `NAMIMA_HANDOFF_DIR`). CPU-only, deterministic, no GPU.

```bash
python scripts/deliver.py doctor                     # deps / ffmpeg / Drive dir / render speed on THIS machine
python scripts/deliver.py judge --name idm-ambient   # 3 x 90 s judgement clips (beatless / soft / idm) in parallel
python scripts/deliver.py long  --name idm-ambient --mode idm --bars 144 --seed 174852
```

ffmpeg resolution: `NAMIMA_FFMPEG` → PATH → `imageio-ffmpeg` (optional) → none (wav only).
Judgement clips deliver only the m4a + handoff; `long` delivers the full packet.

Catalogue + audition reel (same hand-off dir):

```bash
python scripts/catalog_deliveries.py                          # deliveries/CATALOG.md + catalog.csv from catalog.json + files on disk
python scripts/catalog_deliveries.py --set-verdict <packet> "採用。酸をもう少し前へ"   # record the human verdict
python scripts/audition_reel.py --plan deliveries/reel-plan-v1.json   # one m4a + cue sheet of every packet's key passage
```

Texture lane (ACE-Step bed under the Hz-true core, 285 Drift II): [scripts/texture_lane/README.md](scripts/texture_lane/README.md).

### 2026-09-30 再生の安定化

起動中の連打は一つの準備へまとめ、途中の画面ロック・失敗で音源を解放します。スマホ・低負荷端末では短いdelayの音場を使い、長い残響の二重生成を避けます。pad/airは各8voiceに制限し、音場更新は10Hz、スマホ描画は30fps。実iPhoneの音質・長時間試聴は未確認です。
