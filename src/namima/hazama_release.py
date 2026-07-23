"""hazama — solfeggio release batch pipeline (candidate tool).

Renders the 27-track "hazama" release: 9 solfeggio frequencies × 3 moods, as
distributor-ready 44.1 kHz / 16-bit stereo WAV (the TuneCore-Japan / BIG UP!
delivery spec). No audio is committed anywhere — output goes to an external
directory (default ``C:\\workspace\\hazama-release``).

Moods (per target frequency N):
  * pure   (~10:00) — N drone + its 3-6-9 digit-root triad siblings underneath
                      (generator.render × 3, sleep-quiet master)
  * drift  (~9:40)  — solfeggio_composer with harmonic scenes centred on N
  * groove (~3:15)  — solfeggio_idm @108 BPM with scenes centred on N

Every render is deterministic (seed derived from the frequency), so the whole
catalogue is reproducible from this file — masters don't need archiving.

    PYTHONPATH=src python -m namima.hazama_release --out C:/workspace/hazama-release
    PYTHONPATH=src python -m namima.hazama_release --only 528 --mood groove
    PYTHONPATH=src python -m namima.hazama_release --quick        # tiny smoke set
"""
from __future__ import annotations

import argparse
import wave
from pathlib import Path
from typing import Sequence

import numpy as np
from scipy.signal import resample_poly

from .generator import render as drone_render, load_presets, preset_frequency
from . import solfeggio_composer as sc
from . import solfeggio_idm as si

__version__ = "0.1.0-candidate"

SOLFEGGIO = (174, 285, 396, 417, 528, 639, 741, 852, 963)
DELIVERY_SR = 44100                      # distributor spec: 44.1 kHz / 16-bit WAV
MASTER_SR = 48000

# per-mood loudness targets (sleep music masters quiet on purpose; Apple Sound
# Check normalises playback anyway)
RMS_TARGET = {"pure": 0.07, "drift": 0.12, "groove": 0.20}
PEAK_CEIL = {"pure": 0.50, "drift": 0.70, "groove": 0.86}

TRACK_TITLES = {
    "pure": "{hz} Hz Pure Solfeggio - Deep Sleep Tone",
    "drift": "{hz} Hz Drift - Ambient Solfeggio Sleep",
    "groove": "{hz} Hz Groove - Solfeggio Chill Beats",
}
ALBUMS = {
    "pure": "Pure Solfeggio Sleep",
    "drift": "Solfeggio Drift",
    "groove": "Solfeggio Groove",
}
ARTIST = "hazama"


# =============================================================================
# per-frequency musical material (centred on N, staying inside the set)
# =============================================================================
def _bassify(f: float) -> float:
    while f > 300.0:
        f /= 2.0
    return f


def _voicify(f: float) -> float:
    """Bring a frequency into the formant-friendly 300-700 Hz register."""
    while f > 700.0:
        f /= 2.0
    while f < 300.0:
        f *= 2.0
    return f


def triad_of(n: int, presets: dict) -> tuple:
    fam = n % 9 or 9
    return si.sacred_triads(presets)[fam]


def _nearest(center: float, pool, k: int):
    return sorted(sorted(pool, key=lambda f: abs(np.log2(f / center)))[:k])


def drift_blocks_for(n: int, presets: dict) -> list:
    """solfeggio_composer blocks centred on frequency preset ``n``."""
    S = lambda k: preset_frequency(f"solfeggio_{k}", presets)          # noqa: E731
    allf = [S(k) for k in SOLFEGGIO]
    center = S(n)
    tri = triad_of(n, presets)
    sibs = [f for f in tri if f != center] or [center]
    ra, rb = _bassify(center), _bassify(sibs[0])
    mel = _nearest(center, allf, 4)
    voice = sorted({_voicify(center), _voicify(sibs[0])})
    hi = max(tri)
    return [
        dict(bass=ra, pad=[ra, ra * 2, _voicify(center)], mel=mel, voice=voice),
        dict(bass=rb, pad=[rb, rb * 2, _voicify(sibs[-1])], mel=mel, voice=voice),
        dict(bass=ra, pad=[ra, ra * 2, _voicify(center), hi], mel=mel, voice=voice),
        dict(bass=rb, pad=[rb, rb * 2, _voicify(center)], mel=mel, voice=voice),
    ]


def groove_scenes_for(n: int, presets: dict) -> list:
    """solfeggio_idm scenes centred on frequency preset ``n``."""
    S = lambda k: preset_frequency(f"solfeggio_{k}", presets)          # noqa: E731
    allf = [S(k) for k in SOLFEGGIO]
    center = S(n)
    tri = triad_of(n, presets)
    sibs = [f for f in tri if f != center] or [center]
    ra, rb = _bassify(center), _bassify(sibs[0])
    bells = _nearest(max(center, 639.0), [f for f in allf if f >= 528], 4)
    pluck = _nearest(_voicify(center), allf, 3)
    voice = sorted({_voicify(center), _voicify(sibs[0])})
    return [
        dict(root=ra, bell=bells, pluck=pluck,
             pad=[ra, ra * 2, _voicify(center)], voice=voice),
        dict(root=rb, bell=bells, pluck=pluck,
             pad=[rb, rb * 2, _voicify(sibs[-1])], voice=voice),
    ]


# =============================================================================
# renders (each returns float stereo @ 48 kHz)
# =============================================================================
def render_pure(n: int, presets: dict, duration: float = 600.0) -> np.ndarray:
    center = preset_frequency(f"solfeggio_{n}", presets)
    tri = triad_of(n, presets)
    sibs = [f for f in tri if f != center]
    seed = 100000 + n
    main, _ = drone_render(center, duration=duration, sample_rate=MASTER_SR,
                           octaves=(-1, 1), detune_cents=5.0, lfo_rate=0.08,
                           lfo_depth=0.12, fade_s=12.0, seed=seed, gain=0.5)
    out = main.copy()
    for i, f in enumerate(sibs):
        sib, _ = drone_render(f, duration=duration, sample_rate=MASTER_SR,
                              octaves=(-1,), detune_cents=4.0, lfo_rate=0.06,
                              lfo_depth=0.15, fade_s=12.0, seed=seed + 1 + i,
                              gain=0.5)
        out += 0.28 * sib                      # triad siblings underneath (-11 dB)
    return out


def render_drift(n: int, presets: dict, bars: int = 232) -> np.ndarray:
    cfg = sc.ComposeConfig(bars=bars, seed=200000 + n)
    stereo, _ = sc.compose(cfg, blocks=drift_blocks_for(n, presets))
    return stereo


def render_groove(n: int, presets: dict, bars: int = 88) -> np.ndarray:
    cfg = si.IdmConfig(bars=bars, bpm=108.0, seed=300000 + n)
    stereo, _ = si.compose(cfg, scenes=groove_scenes_for(n, presets))
    return stereo


# =============================================================================
# mastering + delivery WAV
# =============================================================================
def master(stereo: np.ndarray, mood: str) -> np.ndarray:
    """RMS-target + peak ceiling (linear low end — no added saturation here)."""
    x = np.asarray(stereo, dtype=np.float64)
    rms = float(np.sqrt(np.mean(x ** 2)))
    x = x * (RMS_TARGET[mood] / max(rms, 1e-9))
    peak = float(np.max(np.abs(x)))
    if peak > PEAK_CEIL[mood]:
        x = x * (PEAK_CEIL[mood] / peak)      # keep it simple & clean: scale down
    return x


def write_wav16_441(path: str | Path, stereo48: np.ndarray, seed: int = 0) -> str:
    """Resample 48k→44.1k (147/160 polyphase) and write 16-bit WAV with 1-LSB
    TPDF dither (seeded — the whole pipeline stays deterministic)."""
    x = resample_poly(stereo48, 147, 160, axis=0)
    rng = np.random.default_rng(seed)
    dither = (rng.random(x.shape) + rng.random(x.shape) - 1.0) / 32768.0
    x = np.clip(x + dither, -1.0, 1.0)
    ints = np.clip(np.round(x * 32767.0), -32768, 32767).astype("<i2")
    path = str(path)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(DELIVERY_SR)
        wf.writeframes(np.ascontiguousarray(ints).tobytes())
    return path


# =============================================================================
# batch CLI
# =============================================================================
def run_track(n: int, mood: str, out_dir: Path, presets: dict, quick: bool) -> Path:
    if mood == "pure":
        stereo = render_pure(n, presets, duration=30.0 if quick else 600.0)
    elif mood == "drift":
        stereo = render_drift(n, presets, bars=16 if quick else 232)
    else:
        stereo = render_groove(n, presets, bars=16 if quick else 88)
    stereo = master(stereo, mood)
    album_dir = out_dir / ALBUMS[mood].replace(" ", "-").lower()
    album_dir.mkdir(parents=True, exist_ok=True)
    idx = SOLFEGGIO.index(n) + 1
    fname = f"{idx:02d}-{n}hz-{mood}.wav"
    path = album_dir / fname
    write_wav16_441(path, stereo, seed=400000 + n)
    dur = stereo.shape[0] / MASTER_SR
    peak = float(np.max(np.abs(stereo)))
    rms = float(np.sqrt(np.mean(stereo ** 2)))
    print(f"OK {ALBUMS[mood]:22s} {TRACK_TITLES[mood].format(hz=n):46s} "
          f"{dur/60:5.1f}min  peak {peak:.2f}  rms {rms:.3f}  -> {path.name}",
          flush=True)
    return path


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="namima.hazama_release",
                                description="hazama 27-track solfeggio release batch")
    p.add_argument("--out", default=r"C:\workspace\hazama-release")
    p.add_argument("--only", type=int, default=None, help="one frequency, e.g. 528")
    p.add_argument("--mood", choices=("pure", "drift", "groove"), default=None)
    p.add_argument("--quick", action="store_true", help="short smoke renders")
    args = p.parse_args(argv)

    presets = load_presets()
    out_dir = Path(args.out)
    freqs = [args.only] if args.only else list(SOLFEGGIO)
    moods = [args.mood] if args.mood else ["pure", "drift", "groove"]
    for n in freqs:
        for mood in moods:
            run_track(n, mood, out_dir, presets, args.quick)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
