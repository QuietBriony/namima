"""namima.idm_ambient — ambient-side IDM prototype (Selected-Ambient-Works 系).

Deterministic numpy/scipy render on the absolute solfeggio scale (non-12-TET,
``presets.yaml`` is the single source of pitch truth).  One motif engine, three
directions so a listener can pick a lane from short judgement clips:

  ``beatless``  pad + motif + sub + texture      (the ambient side)
  ``soft``      + round kick / rim / swung hats   (Xtal-ish, sparse)
  ``idm``       + a chopped 2-bar break           (stutter / reverse / ratchet — restrained)

Taste rails carried over from the listening ledger:
  * NO portamento / siren lead — stable pitch, delayed 5 Hz vibrato only.
  * width lives >1800 Hz (mono-safe M/S) so the phone-mono sum stays comb-free.
  * lows stay linear — the sub is never saturated; glue drive only >150 Hz.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from .generator import load_presets, write_wav24
from .tuning import build_scale
from .solfeggio_composer import lp, hp, env_ar, reverb, _kick, _rim, _hat
from .solfeggio_idm import sub_note, synth_break_loop, chop_break, BREAK_PATTERNS

__version__ = "0.1.0-proto"
TAU = 2.0 * np.pi
MODES = ("beatless", "soft", "idm")

# Scale degrees (0..8 of the folded solfeggio octave 174..319.5 Hz).
# (0, 2, 3, 6, 8) ≈ 0 / 224 / 313 / 723 / 1052 cents — a minor-pentatonic-ish
# subset whose "fifth" is 21 c sharp and whose "seventh" leans flat: the wrong
# notes that sound right.  Pad = root / ~minor third / ~fifth of the same set.
LEAD_DEGREES = (0, 2, 3, 6, 8)
PAD_DEGREES = (0, 3, 6)
RMS_TARGET = {"beatless": 0.11, "soft": 0.14, "idm": 0.16}

# 2-bar rhythm cells as 16th-step onsets (dotted "3+3+2" leaning).
RHYTHM_CELLS = (
    (0, 3, 6, 8, 12, 16, 19, 22, 24, 28),
    (0, 4, 6, 10, 12, 16, 20, 22, 26, 28),
    (0, 3, 8, 11, 14, 16, 19, 24, 27, 30),
)


@dataclass
class AmbientConfig:
    bars: int = 36
    bpm: float = 96.0
    seed: int = 174852
    sample_rate: int = 48000
    gain: float = 0.86
    mode: str = "soft"
    root_degree: int = 0

    @property
    def beat(self) -> float:
        return 60.0 / self.bpm

    @property
    def bar(self) -> float:
        return 4.0 * self.beat

    @property
    def step(self) -> float:
        return self.beat / 4.0

    def as_meta(self) -> dict:
        return {
            "version": __version__, "kind": "namima_idm_ambient", "mode": self.mode,
            "bpm": self.bpm, "bars": self.bars, "seed": self.seed,
            "sample_rate": self.sample_rate, "bit_depth": 24, "channels": 2,
            "gain": self.gain, "root_degree": self.root_degree,
            "pitch_system": "absolute-solfeggio-Hz (non-12-TET; presets.yaml)",
        }


# =============================================================================
# pitch
# =============================================================================
def scale_hz(presets: dict | None = None) -> list[float]:
    """The nine folded degrees, ascending (174 .. 319.5 Hz)."""
    return [f for f, _ in build_scale(presets or load_presets())]


def degree_hz(scale: Sequence[float], degree: int, octave: int = 0) -> float:
    o, d = divmod(int(degree), len(scale))
    return float(scale[d]) * 2.0 ** (octave + o)


def lead_pool(scale: Sequence[float], root_degree: int = 0) -> list[float]:
    """Ten lead pitches: the five LEAD_DEGREES over two octaves (348 .. ~1280 Hz)."""
    return [degree_hz(scale, root_degree + d, octave)
            for octave in (1, 2) for d in LEAD_DEGREES]


def pad_chord(scale: Sequence[float], root_degree: int) -> list[float]:
    return [degree_hz(scale, root_degree + d, 0) for d in PAD_DEGREES]


# =============================================================================
# voices
# =============================================================================
def _tri(phase: np.ndarray) -> np.ndarray:
    v = np.zeros_like(phase)
    for k, h in enumerate((1, 3, 5, 7, 9)):
        v += ((-1.0) ** k) / (h * h) * np.sin(h * phase)
    return v


def lead_note(f: float, dur: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    """Soft analogue-ish lead: two detuned triangles + sub-octave sine, a
    filter that opens on the attack, and a *delayed* 5 Hz vibrato (no glide)."""
    n = max(int(dur * sr), 8)
    t = np.arange(n) / sr
    vib_on = np.clip((t - 0.18) / 0.35, 0.0, 1.0)
    cents = 6.0 * vib_on * np.sin(TAU * 5.2 * t + rng.uniform(0, TAU))
    f_inst = f * 2.0 ** (cents / 1200.0)
    phase = TAU * np.cumsum(f_inst) / sr
    v = _tri(phase * 2.0 ** (-4.0 / 1200.0)) + _tri(phase * 2.0 ** (4.0 / 1200.0))
    v += 0.28 * np.sin(phase * 0.5)
    dark, bright = lp(v, 1500, sr, 2), lp(v, 3400, sr, 2)
    v = dark + (bright - dark) * np.exp(-t / 0.30)
    env = env_ar(n, 0.035, 0.12, sr) * (0.7 + 0.3 * np.exp(-t / 0.25))
    return v * env * 0.5


def pad_scene(freqs: Sequence[float], dur: float, sr: int, rng: np.random.Generator,
              lfo_phase: float) -> np.ndarray:
    """Three detuned band-limited saws per chord tone, slow filter sweep, breathing."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    n_h = 14
    v = np.zeros(n)
    for f in freqs:
        for det in (-7.0, 0.0, 7.0):
            fk = f * 2.0 ** (det / 1200.0)
            ph = rng.uniform(0, TAU)
            for h in range(1, n_h + 1):
                sigma = np.sinc(h / (n_h + 1))                       # Lanczos: no Gibbs edge
                v += (sigma / h) * np.sin(TAU * h * fk * t + ph)
    v /= (3.0 * len(freqs))
    dark, bright = lp(v, 500, sr, 2), lp(v, 2000, sr, 2)
    sweep = 0.5 - 0.5 * np.cos(TAU * 0.045 * t + lfo_phase)
    v = dark + (bright - dark) * sweep
    breathe = 0.85 + 0.15 * np.sin(TAU * 0.03 * t + rng.uniform(0, TAU))
    return v * breathe * env_ar(n, 2.0, 2.5, sr)


def echo(x: np.ndarray, delay_s: float, sr: int, fb: float = 0.42, taps: int = 5) -> np.ndarray:
    """Dotted-8th style feedback echo as finite filtered taps (vectorised)."""
    d = int(delay_s * sr)
    src = hp(lp(x, 2200, sr, 2), 250, sr, 1)
    out = np.zeros_like(x)
    for k in range(1, taps + 1):
        if k * d >= len(x):
            break
        out[k * d:] += (fb ** k) * src[: len(x) - k * d]
    return out


def crackle(N: int, sr: int, rng: np.random.Generator) -> np.ndarray:
    """Sparse vinyl clicks + a faint hiss bed (fades in over 4 s)."""
    clicks = np.zeros(N)
    count = int(N / sr * 6.0)
    pos = rng.integers(0, max(N - 64, 1), size=count)
    amp = rng.random(count) ** 2.5
    for p, a in zip(pos, amp):
        w = int(rng.integers(3, 12))
        clicks[p:p + w] += a * rng.standard_normal(w)
    clicks = hp(lp(clicks, 6000, sr, 2), 1500, sr, 2) * 0.05
    hiss = lp(rng.standard_normal(N), 6000, sr, 1) * 0.0035
    fade = np.clip(np.arange(N) / (4.0 * sr), 0.0, 1.0)
    return (clicks + hiss) * fade


# =============================================================================
# motif engine
# =============================================================================
def motif_events(cfg: AmbientConfig, rng: np.random.Generator, pool_n: int,
                 start_bar: int = 8) -> list[tuple[int, int, int, float, float]]:
    """(bar, step, pool_index, dur_steps, vel).  One seeded 2-bar cell, repeated
    4x per 8-bar phrase with small mutations, phrases shifted by a pool degree."""
    cell = list(RHYTHM_CELLS[int(rng.integers(0, len(RHYTHM_CELLS)))])
    idx = 3
    pitches = []
    for _ in cell:
        r = rng.random()
        if r < 0.18:
            mv = 0
        elif r < 0.66:
            mv = int(rng.choice([-1, 1]))
        elif r < 0.90:
            mv = int(rng.choice([-2, 2]))
        else:
            mv = int(rng.choice([-3, 3]))
        idx = int(np.clip(idx + mv, 0, pool_n - 1))
        pitches.append(idx)
    stable = (0, 3, 5, 8)                                   # root / fifth-ish anchors
    pitches[-1] = min(stable, key=lambda s: abs(s - pitches[-1]))
    sub_j = int(rng.integers(0, len(cell)))
    events = []
    for phrase in range(start_bar, cfg.bars, 8):
        shift = (0, 1, 0, -1)[((phrase - start_bar) // 8) % 4]
        for rep in range(4):
            bar0 = phrase + rep * 2
            if bar0 >= cfg.bars:
                break
            for j, st in enumerate(cell):
                p = pitches[j] + shift
                if rep == 2 and j == sub_j:
                    p += int(rng.choice([-1, 1]))
                if rep == 3 and j == len(cell) - 1 and rng.random() < 0.5:
                    continue
                p = int(np.clip(p, 0, pool_n - 1))
                nxt = cell[j + 1] if j + 1 < len(cell) else 32
                dur_steps = max(nxt - st, 1) * 0.92
                vel = (0.95 if st % 8 == 0 else 0.72) + rng.uniform(-0.05, 0.05)
                bar = bar0 + st // 16
                if bar < cfg.bars:
                    events.append((bar, st % 16, p, dur_steps, vel))
    return events


# =============================================================================
# render
# =============================================================================
def _structure(cfg: AmbientConfig) -> dict:
    """Bar map: lead from 8, drums from 12, a 4-bar breakdown every 32 bars from
    bar 24 once the form is long enough (>= 32 bars), and an 8-bar outro (drums
    out, lead anchors only) on long forms (>= 64 bars).  A 36-bar render keeps
    the single (24, 28) breakdown of the judgement clips."""
    b_lead, b_drums = 8, 12
    breakdowns = [(b, b + 4) for b in range(24, cfg.bars - 8, 32)] if cfg.bars >= 32 else []
    outro = cfg.bars - 8 if cfg.bars >= 64 else None
    return {"lead": b_lead, "drums": b_drums, "breakdowns": breakdowns, "outro": outro}


def _in_breakdown(bar: int, s: dict) -> bool:
    if any(b0 <= bar < b1 for b0, b1 in s["breakdowns"]):
        return True
    return s["outro"] is not None and bar >= s["outro"]


def _drums_on(bar: int, s: dict) -> bool:
    return bar >= s["drums"] and not _in_breakdown(bar, s)


def render(cfg: AmbientConfig | None = None, presets: dict | None = None):
    """Render the piece. Returns ``(stereo (n,2) in [-1,1], meta)``. Deterministic."""
    cfg = cfg or AmbientConfig()
    if cfg.mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {cfg.mode!r}")
    presets = presets or load_presets()
    scale = scale_hz(presets)
    sr = cfg.sample_rate
    N = int((cfg.bars * cfg.bar + 3.0) * sr)
    s = _structure(cfg)

    r_pad = np.random.default_rng(cfg.seed + 1)
    r_lead = np.random.default_rng(cfg.seed + 2)
    r_drm = np.random.default_rng(cfg.seed + 3)
    r_brk = np.random.default_rng(cfg.seed + 4)
    r_tex = np.random.default_rng(cfg.seed + 5)
    r_mst = np.random.default_rng(cfg.seed + 6)

    def put(dst, buf, t0, vel):
        i0 = int(t0 * sr)
        i1 = min(i0 + len(buf), N)
        if 0 <= i0 < i1:
            dst[i0:i1] += buf[: i1 - i0] * vel

    def stime(bar, step, human=0.0015, rng=r_drm):
        t = bar * cfg.bar + step * cfg.step
        if (step // 2) % 2 == 1:                            # swing the off 8ths
            t += 0.25 * cfg.step
        return t + rng.uniform(-human, human)

    # --- pad: 8-bar scenes alternating root / +3 degrees (relative-minor lean)
    pad = np.zeros(N)
    for i, b0 in enumerate(range(0, cfg.bars, 8)):
        root = cfg.root_degree + (0, 3)[i % 2]
        dur = min(8, cfg.bars - b0) * cfg.bar + 2.5
        seg = pad_scene(pad_chord(scale, root), dur, sr, r_pad, lfo_phase=i * 1.3)
        put(pad, seg, b0 * cfg.bar, 1.0)

    # --- sub: root an octave-pair down (43 .. 80 Hz), whole notes from bar 4
    sub = np.zeros(N)
    f_sub = degree_hz(scale, cfg.root_degree, 0) / 4.0
    for bar in range(4, cfg.bars):
        put(sub, sub_note(f_sub, cfg.bar * 0.95, sr), bar * cfg.bar, 0.9)
        if cfg.mode != "beatless" and bar % 2 == 1 and _drums_on(bar, s):
            put(sub, sub_note(f_sub, cfg.beat * 1.6, sr), bar * cfg.bar + 2 * cfg.beat, 0.5)

    # --- lead motif (stable pitch, delayed vibrato) + dotted-8th echo
    pool = lead_pool(scale, cfg.root_degree)
    lead = np.zeros(N)
    for (bar, step, p, dur_steps, vel) in motif_events(cfg, r_lead, len(pool), s["lead"]):
        thin = _in_breakdown(bar, s)
        if thin and step % 8 != 0:
            continue                                          # breakdown: anchors only
        note = lead_note(pool[p], dur_steps * cfg.step + 0.05, sr, r_lead)
        put(lead, note, stime(bar, step, rng=r_lead), vel)
    lead_echo = echo(lead, 0.75 * cfg.beat, sr)

    # --- drums
    drums = np.zeros(N)
    if cfg.mode in ("soft", "idm"):
        kick, rim, hatc, hato = _kick(r_drm, sr), _rim(r_drm, sr), _hat(r_drm, sr), _hat(r_drm, sr, True)
        for bar in range(cfg.bars):
            if not _drums_on(bar, s):
                continue
            if cfg.mode == "soft":
                put(drums, kick, stime(bar, 0), 1.0)
                put(drums, kick, stime(bar, 8), 0.85)
                if r_drm.random() < 0.3:
                    put(drums, kick, stime(bar, 11), 0.45)
                put(drums, rim, stime(bar, 4), 0.55)
                put(drums, rim, stime(bar, 12), 0.5)
                for st in range(0, 16, 2):
                    v = (0.55, 0.28, 0.42, 0.28)[(st // 2) % 4] * r_drm.uniform(0.85, 1.0)
                    put(drums, hato if st == 14 and bar % 4 == 3 else hatc, stime(bar, st), v)
            else:
                put(drums, kick, stime(bar, 0), 0.6)          # weight under the break
        if cfg.mode == "idm":
            loop = synth_break_loop(cfg, r_brk, BREAK_PATTERNS["xtal"])
            for phrase in range(0, cfg.bars, 2):
                if not _drums_on(phrase, s):
                    continue
                inten = 0.35 if phrase < s["drums"] + 8 else (0.6 if phrase < 64 else 0.75)
                fill = (phrase % 8) == 6
                put(drums, chop_break(loop, cfg, r_brk, inten, fill=fill), phrase * cfg.bar, 0.7)
        drums = lp(drums, 12000, sr, 2)

    tex = crackle(N, sr, r_tex)

    # --- mix / master (same rails as the other namima composers)
    send = hp(0.5 * pad + 0.8 * lead + 0.4 * lead_echo + 0.25 * drums, 300, sr, 2)
    wet = reverb(send, r_mst, sr, decay=0.9, length=3.0, predelay=0.03) * 0.30
    mix = 0.30 * pad + 0.55 * lead + 0.35 * lead_echo + 0.85 * sub + 0.90 * drums + tex + wet
    mix = hp(mix, 22, sr, 1)
    low = lp(mix, 150, sr, 2)
    mix = low + np.tanh(1.1 * (mix - low)) / np.tanh(1.1)   # glue only >150 Hz
    fi, fo = int(1.5 * sr), int(5.0 * sr)
    mix[:fi] *= np.linspace(0, 1, fi)
    mix[-fo:] *= np.linspace(1, 0, fo)
    rms = float(np.sqrt(np.mean(mix ** 2)))
    mix *= RMS_TARGET[cfg.mode] / max(rms, 1e-9)
    knee, ceil = 0.70, cfg.gain
    over = np.abs(mix) > knee
    mix[over] = np.sign(mix[over]) * (
        knee + (ceil - knee) * np.tanh((np.abs(mix[over]) - knee) / (ceil - knee)))
    mix = np.clip(mix, -ceil, ceil)

    d = int(0.008 * sr)                                       # mono-safe M/S: L+R == 2*mix
    side = np.concatenate([np.zeros(d), hp(mix, 1800, sr, 1)[:-d]])
    stereo = np.stack([mix + 0.16 * side, mix - 0.16 * side], axis=1)
    stereo *= cfg.gain / float(np.max(np.abs(stereo)))

    meta = cfg.as_meta()
    meta["frames"] = int(stereo.shape[0])
    meta["structure"] = s
    return stereo, meta


# =============================================================================
# CLI
# =============================================================================
def _to_mp3(wav_path: Path, bitrate: str = "192k") -> Path | None:
    try:
        import imageio_ffmpeg  # optional
        import subprocess
    except ImportError:
        return None
    mp3 = wav_path.with_suffix(".mp3")
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
                    "-i", str(wav_path), "-codec:a", "libmp3lame", "-b:a", bitrate, str(mp3)],
                   check=True)
    return mp3


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="namima ambient-side IDM prototype (deterministic)")
    p.add_argument("--mode", choices=MODES, default="soft")
    p.add_argument("--bars", type=int, default=36)
    p.add_argument("--bpm", type=float, default=96.0)
    p.add_argument("--seed", type=int, default=174852)
    p.add_argument("--root-degree", type=int, default=0)
    p.add_argument("--out", required=True, help="output .wav path (24-bit / 48 kHz)")
    p.add_argument("--mp3", action="store_true", help="also encode an mp3 next to the wav")
    a = p.parse_args(argv)
    cfg = AmbientConfig(bars=a.bars, bpm=a.bpm, seed=a.seed, mode=a.mode, root_degree=a.root_degree)
    stereo, meta = render(cfg)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_wav24(out, stereo, cfg.sample_rate)
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {out}  ({meta['frames'] / cfg.sample_rate:.1f}s, mode={cfg.mode}, seed={cfg.seed})")
    if a.mp3:
        mp3 = _to_mp3(out)
        print(f"wrote {mp3}" if mp3 else "mp3 skipped (imageio_ffmpeg not installed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
