"""Offline frequency-based ambient renderer (candidate).

Deterministic, DAW-free renderer for 128 Hz / solfeggio / binaural ambient
drones. numpy for synthesis, scipy for the fade window (with a numpy fallback),
and the stdlib ``wave`` module for 48 kHz / 24-bit PCM WAV output (scipy.io
cannot write 24-bit).

Spec: ../../SKILL.md   Data: ../../presets.yaml   (kept in sync; enforced by tests)

Design constraints (namima repo rules):
  * self-synthesised audio only — no samples committed, generated WAVs are gitignored
  * numpy + scipy only — presets.yaml is read by a tiny built-in loader (no PyYAML)
  * deterministic for a fixed seed (test reproducibility)
"""

from __future__ import annotations

import argparse
import math
import warnings
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

__version__ = "0.1.0-candidate"

# --- allowed-range guidance (from SKILL.md). lfo_depth is HARD-clamped (a value
# --- > 1 would drive the amplitude envelope negative = a sign flip); the others
# --- are advisory and only warn.
LFO_RATE_RANGE = (0.05, 0.2)      # Hz
LFO_DEPTH_RANGE = (0.0, 1.0)      # hard clamp — outside this the signal inverts
BINAURAL_RANGE = (2.0, 8.0)       # Hz (0 disables binaural / mono-safe)
_PRESETS_PATH = Path(__file__).resolve().parents[2] / "presets.yaml"


# =============================================================================
# Minimal dependency-free YAML-subset loader
# =============================================================================
def _parse_scalar(text: str):
    """Parse a YAML scalar or inline list for this project's preset file only."""
    s = text.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in inner.split(",")]
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _load_yaml(text: str) -> dict:
    """Parse the flat, ≤2-level YAML shape used by presets.yaml. Not general."""
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if ":" not in stripped:
            raise ValueError(f"presets.yaml:{lineno}: expected 'key: value', got {stripped!r}")
        key, _, val = stripped.partition(":")
        key = key.strip()
        val = val.split("#", 1)[0].strip()  # allow trailing inline comments
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ValueError(f"presets.yaml:{lineno}: broken indentation")
        parent = stack[-1][1]
        if val == "":
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(val)
    return root


def load_presets(path: str | Path | None = None) -> dict:
    """Load and validate presets.yaml (the single source of truth)."""
    p = Path(path) if path is not None else _PRESETS_PATH
    data = _load_yaml(p.read_text(encoding="utf-8"))
    for required in ("tunings", "frequencies", "defaults"):
        if required not in data:
            raise ValueError(f"presets.yaml missing top-level key: {required!r}")
    if not isinstance(data["frequencies"], dict) or not data["frequencies"]:
        raise ValueError("presets.yaml 'frequencies' must be a non-empty map")
    for name, hz in data["frequencies"].items():
        if not isinstance(hz, (int, float)) or hz <= 0:
            raise ValueError(f"presets.yaml frequency {name!r} must be a positive number, got {hz!r}")

    defaults = data["defaults"]
    if not isinstance(defaults, dict) or not defaults:
        raise ValueError("presets.yaml 'defaults' must be a non-empty map")
    if not (isinstance(defaults.get("sample_rate"), int) and defaults["sample_rate"] > 0):
        raise ValueError("presets.yaml defaults.sample_rate must be a positive int")
    for key in ("duration_s", "smoke_duration_s"):
        v = defaults.get(key)
        if not (isinstance(v, (int, float)) and v > 0):
            raise ValueError(f"presets.yaml defaults.{key} must be a positive number")
    octaves = defaults.get("octaves")
    if not (isinstance(octaves, list) and octaves and all(isinstance(o, int) for o in octaves)):
        raise ValueError("presets.yaml defaults.octaves must be a non-empty list of ints")
    gain = defaults.get("gain")
    if not (isinstance(gain, (int, float)) and 0 < gain <= 1):
        raise ValueError("presets.yaml defaults.gain must be in (0, 1]")
    return data


def preset_frequency(name: str, presets: dict | None = None) -> float:
    """Look up an absolute fundamental (Hz) by preset name."""
    presets = presets or load_presets()
    freqs = presets["frequencies"]
    if name not in freqs:
        raise KeyError(f"unknown frequency preset {name!r}; known: {sorted(freqs)}")
    return float(freqs[name])


def note_to_freq(note: str, tuning: float = 440.0) -> float:
    """Derive an absolute frequency (Hz) for a note name under a given tuning.

    ``tuning`` is the A4 reference (e.g. 432 / 440 / 444). Note format is a
    letter A-G, optional #/b, then an octave, e.g. ``C3``, ``F#4``, ``Bb2``.
    This is where the ``tuning`` knob actually bites — the absolute preset
    frequencies in presets.yaml already bake in their intended tuning.

    Note the equal-tempered result is not the rounded "healing" number: e.g.
    ``note_to_freq("C3", 432) ≈ 128.43`` Hz, whereas the ``c3_128`` preset is the
    nominal 128.0. ``note_to_freq("C5", 444) ≈ 528.0`` matches its preset closely.
    """
    semitone = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}
    m = note.strip()
    letter = m[0].upper()
    if letter not in semitone:
        raise ValueError(f"bad note {note!r}")
    idx = 1
    accidental = 0
    while idx < len(m) and m[idx] in "#b":
        accidental += 1 if m[idx] == "#" else -1
        idx += 1
    octave = int(m[idx:])
    n = semitone[letter] + accidental + (octave - 4) * 12  # semitones from A4
    return float(tuning) * (2.0 ** (n / 12.0))


# =============================================================================
# Render configuration
# =============================================================================
@dataclass
class RenderConfig:
    """Resolved render parameters (defaults pulled from presets.yaml)."""

    base_freq: float
    tuning: float = 440.0
    duration: float = 600.0
    sample_rate: int = 48000
    octaves: Sequence[int] = (-1, 1)
    detune_cents: float = 6.0
    lfo_rate: float = 0.1
    lfo_depth: float = 0.15
    binaural_offset: float = 0.0
    fade_s: float = 8.0
    loop: bool = False
    seed: int = 0
    gain: float = 0.5

    def as_meta(self) -> dict:
        return {
            "version": __version__,
            "base_freq": self.base_freq,
            "tuning": self.tuning,
            "duration_s": self.duration,
            "sample_rate": self.sample_rate,
            "bit_depth": 24,
            "channels": 2,
            "octaves": list(self.octaves),
            "detune_cents": self.detune_cents,
            "lfo_rate_hz": self.lfo_rate,
            "lfo_depth": self.lfo_depth,
            "binaural_offset_hz": self.binaural_offset,
            "fade_s": 0.0 if self.loop else self.fade_s,
            "loop": self.loop,
            "seed": self.seed,
            "gain": self.gain,
        }


def _defaults_from_presets(presets: dict) -> dict:
    d = dict(presets.get("defaults", {}))
    return d


# =============================================================================
# DSP
# =============================================================================
def _fade_envelope(n: int, sample_rate: int, fade_s: float) -> np.ndarray:
    """Deterministic raised-cosine (Tukey-style) fade-in/out envelope.

    Pure numpy on purpose: the window must be bit-identical regardless of whether
    scipy happens to be installed, so a fixed ``seed`` produces the same WAV in
    every environment. ``fade_s`` seconds ramp in at the head and out at the tail.
    """
    if fade_s <= 0 or n <= 1:
        return np.ones(n)
    k = int(min(round(fade_s * sample_rate), n // 2))  # fade samples at each end
    if k <= 0:
        return np.ones(n)
    env = np.ones(n)
    ramp = 0.5 - 0.5 * np.cos(np.linspace(0.0, math.pi, k, endpoint=True))
    env[:k] = ramp
    env[-k:] = ramp[::-1]
    return env


def _build_channel(
    t: np.ndarray,
    f0: float,
    octaves: Iterable[int],
    detune_cents: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """A drone channel: fundamental + octave partials, each a micro-detuned
    3-voice cluster for slow beating (うなり)."""
    sig = np.zeros_like(t)
    detunes = (0.0, +detune_cents, -detune_cents)
    for octv in (0, *octaves):
        f = f0 * (2.0 ** octv)
        weight = 0.5 ** abs(octv)  # -6 dB per octave from the fundamental
        for dc in detunes:
            fk = f * (2.0 ** (dc / 1200.0))
            phase = rng.uniform(0.0, 2.0 * math.pi)
            sig += (weight / len(detunes)) * np.sin(2.0 * math.pi * fk * t + phase)
    return sig


def render(
    base_freq: float,
    tuning: float = 440.0,
    duration: float = 600.0,
    *,
    sample_rate: int = 48000,
    octaves: Sequence[int] = (-1, 1),
    detune_cents: float = 6.0,
    lfo_rate: float = 0.1,
    lfo_depth: float = 0.15,
    binaural_offset: float = 0.0,
    fade_s: float = 8.0,
    loop: bool = False,
    seed: int = 0,
    gain: float = 0.5,
    out_path: str | Path | None = None,
):
    """Render a stereo ambient drone.

    Returns ``(stereo, meta)`` where ``stereo`` is a float64 ndarray of shape
    ``(n, 2)`` in [-1, 1] and ``meta`` is a provenance dict. If ``out_path`` is
    given, also writes a 48 kHz / 24-bit WAV and puts the path in ``meta['path']``.

    Deterministic for a fixed ``seed``. ``binaural_offset`` (2..8 Hz) shifts the
    right channel's fundamental to create a binaural beat; 0 keeps L == R.
    """
    if base_freq <= 0:
        raise ValueError("base_freq must be > 0")
    if duration <= 0:
        raise ValueError("duration must be > 0")

    cfg = RenderConfig(
        base_freq=float(base_freq), tuning=float(tuning), duration=float(duration),
        sample_rate=int(sample_rate), octaves=tuple(int(o) for o in octaves),
        detune_cents=float(detune_cents), lfo_rate=float(lfo_rate),
        lfo_depth=float(lfo_depth), binaural_offset=float(binaural_offset),
        fade_s=float(fade_s), loop=bool(loop), seed=int(seed), gain=float(gain),
    )

    # lfo_depth is hard-clamped: > 1 would drive the envelope negative (a sign
    # flip, not just a loud dip). rate / binaural are advisory — warn only.
    if not (LFO_DEPTH_RANGE[0] <= cfg.lfo_depth <= LFO_DEPTH_RANGE[1]):
        warnings.warn(f"lfo_depth {cfg.lfo_depth} clamped to {LFO_DEPTH_RANGE}", stacklevel=2)
        cfg.lfo_depth = float(min(max(cfg.lfo_depth, LFO_DEPTH_RANGE[0]), LFO_DEPTH_RANGE[1]))
    if cfg.lfo_depth > 0 and not (LFO_RATE_RANGE[0] <= cfg.lfo_rate <= LFO_RATE_RANGE[1]):
        warnings.warn(f"lfo_rate {cfg.lfo_rate} Hz outside advisory {LFO_RATE_RANGE} Hz", stacklevel=2)
    if cfg.binaural_offset != 0.0 and not (BINAURAL_RANGE[0] <= abs(cfg.binaural_offset) <= BINAURAL_RANGE[1]):
        warnings.warn(
            f"binaural_offset {cfg.binaural_offset} Hz outside advisory {BINAURAL_RANGE} Hz", stacklevel=2
        )

    n = int(round(cfg.duration * cfg.sample_rate))
    t = np.arange(n, dtype=np.float64) / cfg.sample_rate
    rng = np.random.default_rng(cfg.seed)

    left = _build_channel(t, cfg.base_freq, cfg.octaves, cfg.detune_cents, rng)
    if cfg.binaural_offset != 0.0:
        # Separate rng stream so L is unchanged whether or not binaural is on.
        # The whole right-channel tone is transposed to (f0 + offset): the
        # fundamental beats at `offset` Hz, octave partials at multiples of it.
        rng_r = np.random.default_rng(cfg.seed + 1)
        right = _build_channel(
            t, cfg.base_freq + cfg.binaural_offset, cfg.octaves, cfg.detune_cents, rng_r
        )
    else:
        right = left

    # Slow amplitude LFO (shared, so the stereo image breathes together).
    lfo_phase = rng.uniform(0.0, 2.0 * math.pi)
    lfo = 1.0 - cfg.lfo_depth * (0.5 - 0.5 * np.cos(2.0 * math.pi * cfg.lfo_rate * t + lfo_phase))

    env = np.ones(n) if cfg.loop else _fade_envelope(n, cfg.sample_rate, cfg.fade_s)
    shape = lfo * env

    left = left * shape
    right = right * shape if cfg.binaural_offset != 0.0 else left

    stereo = np.stack([left, right], axis=1)

    # Peak-normalise to the target gain (headroom), then hard-guard against clip.
    peak = float(np.max(np.abs(stereo)))
    if peak > 0:
        stereo = stereo * (cfg.gain / peak)
    stereo = np.clip(stereo, -1.0, 1.0)

    meta = cfg.as_meta()
    meta["frames"] = n
    if out_path is not None:
        write_wav24(out_path, stereo, cfg.sample_rate)
        meta["path"] = str(out_path)
    return stereo, meta


# =============================================================================
# 24-bit WAV output (stdlib wave; scipy.io.wavfile cannot do 24-bit)
# =============================================================================
def write_wav24(path: str | Path, stereo: np.ndarray, sample_rate: int) -> str:
    """Write a stereo float array in [-1, 1] as 24-bit little-endian PCM WAV."""
    x = np.asarray(stereo, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 2:
        raise ValueError("stereo must have shape (n, 2)")
    x = np.clip(x, -1.0, 1.0)
    ints = np.round(x * (2 ** 23 - 1)).astype("<i4")  # int32 LE, fits int24 range
    interleaved = np.ascontiguousarray(ints).reshape(-1)          # L,R,L,R,...
    low3 = interleaved.view(np.uint8).reshape(-1, 4)[:, :3]        # low 3 LE bytes
    pcm = np.ascontiguousarray(low3).tobytes()
    path = str(path)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(3)          # 24-bit
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm)
    return path


# =============================================================================
# FUTURE SLOT — reference-material layer (interface only; implementation TODO)
# =============================================================================
def add_reference_layer(
    stereo: np.ndarray,
    asset_path: str | Path,
    target_freq: float,
    *,
    gain: float = 0.25,
    sample_rate: int = 48000,
) -> np.ndarray:
    """Pitch-correct an ``assets/`` WAV (e.g. a BandLab export) toward
    ``target_freq`` and mix it under the synthesised drone.

    TODO(candidate): implement pitch detection + resampling-based correction and
    a length-matched underlay. For now this is the agreed interface only — it
    raises so callers can wire against a stable signature without a silent no-op.
    See SKILL.md §"Future slot".
    """
    raise NotImplementedError(
        "add_reference_layer is a reserved interface (SKILL.md §Future slot); "
        "asset pitch-correction is not implemented in the candidate."
    )


# =============================================================================
# CLI
# =============================================================================
def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="namima.generator",
        description="Offline frequency-based ambient renderer (candidate).",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--preset", help="preset name from presets.yaml (e.g. c3_128, solfeggio_528)")
    src.add_argument("--freq", type=float, help="explicit fundamental frequency in Hz")
    src.add_argument("--note", help="note name (with --tuning), e.g. C3, F#4")
    p.add_argument("--tuning", type=float, default=None, help="A4 reference (432/440/444)")
    p.add_argument("--duration", type=float, default=None, help="length in seconds")
    p.add_argument("--smoke", action="store_true", help="use the short smoke duration")
    p.add_argument("--binaural", type=float, default=0.0, help="L/R beat offset Hz (2..8)")
    p.add_argument("--lfo-rate", type=float, default=None, help="amplitude LFO rate Hz (0.05..0.2)")
    p.add_argument("--lfo-depth", type=float, default=None)
    p.add_argument("--detune-cents", type=float, default=None)
    p.add_argument("--octaves", default=None, help="comma list, e.g. -1,1 or -2,-1,1,2")
    p.add_argument("--fade", type=float, default=None, help="fade in/out seconds")
    p.add_argument("--loop", action="store_true", help="omit fades for looping")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--gain", type=float, default=None, help="peak target 0..1")
    p.add_argument("--out", default="out.wav", help="output WAV path")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    presets = load_presets()
    d = _defaults_from_presets(presets)

    tuning = args.tuning if args.tuning is not None else float(presets.get("default_tuning", 440))
    if args.preset is not None:
        base_freq = preset_frequency(args.preset, presets)
    elif args.note is not None:
        base_freq = note_to_freq(args.note, tuning)
    else:
        base_freq = float(args.freq)

    if args.smoke:
        duration = float(d.get("smoke_duration_s", 5))
    elif args.duration is not None:
        duration = args.duration
    else:
        duration = float(d.get("duration_s", 600))

    octaves = (
        tuple(int(x) for x in args.octaves.split(","))
        if args.octaves
        else tuple(d.get("octaves", (-1, 1)))
    )

    _, meta = render(
        base_freq,
        tuning=tuning,
        duration=duration,
        sample_rate=int(d.get("sample_rate", 48000)),
        octaves=octaves,
        detune_cents=args.detune_cents if args.detune_cents is not None else float(d.get("detune_cents", 6.0)),
        lfo_rate=args.lfo_rate if args.lfo_rate is not None else float(d.get("lfo_rate_hz", 0.1)),
        lfo_depth=args.lfo_depth if args.lfo_depth is not None else float(d.get("lfo_depth", 0.15)),
        binaural_offset=args.binaural,
        fade_s=args.fade if args.fade is not None else float(d.get("fade_s", 8.0)),
        loop=args.loop,
        seed=args.seed,
        gain=args.gain if args.gain is not None else float(d.get("gain", 0.5)),
        out_path=args.out,
    )
    print(
        f"wrote {meta['path']}  "
        f"{meta['base_freq']:.3f} Hz  {meta['duration_s']}s  "
        f"{meta['sample_rate']}Hz/{meta['bit_depth']}bit  "
        f"binaural={meta['binaural_offset_hz']}Hz  seed={meta['seed']}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
