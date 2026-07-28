"""Lay an external texture bed under a rendered solfeggio track.

Where this sits
---------------
namima rule 5 keeps audio self-synthesised and sample-free, so a generated
texture WAV must never live in this repo. The CODE can: this module is pure
DSP that takes a path to an asset the caller supplies (kept in the release
workspace) and folds it under a finished render. Determinism survives - the
same asset plus the same core plus the same seed gives the same output.

What it has to protect
----------------------
The whole premise of the catalogue is an exact absolute frequency. A bed that
piles energy onto the root buries it, and the damage is easy to miss because
the mix simply sounds "fuller". So the bed is high-passed clear of the root
before it is mixed, the mix level is deliberately low, and ``root_impact``
reports what actually happened to the root band rather than trusting the plan.

Measured on the first ACE-Step take: 92% of its power sat below 100 Hz and its
strongest partial was 87 Hz, one octave under 174 - exactly the collision this
guards against.

    python -m namima.texture_layer core.wav bed.wav --out mixed.wav --level -22
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from math import gcd

from scipy.signal import butter, resample_poly, sosfiltfilt

from .spatial import band_energy, side_to_mid, spatialise

__version__ = "0.1.0"

DEFAULT_HIGHPASS_HZ = 800.0
DEFAULT_LEVEL_DB = -22.0


def read_wav(path):
    sr, data = wavfile.read(path)
    x = data.astype(np.float64)
    if np.issubdtype(data.dtype, np.integer):
        x /= float(np.iinfo(data.dtype).max)
    if x.ndim == 1:
        x = x[:, None]
    return sr, x


def resample_to(x, source_sr, target_sr):
    """Rate-match the bed to the core. The releases are 44.1 kHz; ACE-Step
    writes 48 kHz, so this is the normal path, not an edge case."""
    if source_sr == target_sr:
        return x
    divisor = gcd(int(source_sr), int(target_sr))
    up, down = int(target_sr) // divisor, int(source_sr) // divisor
    return np.stack([resample_poly(x[:, c], up, down) for c in range(x.shape[1])],
                    axis=1)


def trim_edges(x, sr, threshold=0.02, max_trim_s=6.0):
    """Drop the fade-in and fade-out a generator puts on every clip.

    Those fades are what make a bed unloopable: the head is loud and the tail is
    near silence, so any butt-join pumps. Threshold is relative to the clip's
    own peak.
    """
    mono = x.mean(axis=1)
    level = np.abs(mono)
    limit = threshold * level.max()
    # Clamp the search window to the clip: with a window longer than the clip
    # the head and tail searches overlap and the tail index runs negative.
    span = min(int(sr * max_trim_s), len(x))

    head_region = level[:span] > limit
    head = int(np.argmax(head_region)) if head_region.any() else 0

    tail_region = level[len(x) - span:] > limit
    # argmax on the reversed mask = samples of silence at the end.
    tail = len(x) - int(np.argmax(tail_region[::-1])) if tail_region.any() else len(x)

    if tail - head < sr:            # nothing usable left; keep the clip whole
        return x
    return x[head:tail]


def seamless_loop(x, sr, crossfade_s=2.0):
    """Fold the tail back over the head so the clip joins to itself."""
    fade = min(int(sr * crossfade_s), len(x) // 3)
    if fade <= 0:
        return x
    ramp = (0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, fade)))[:, None]
    body = x[:-fade].copy()
    body[:fade] = x[:fade] * ramp + x[-fade:] * (1.0 - ramp)
    return body


def tile_to(x, samples):
    if len(x) == 0:
        raise ValueError("empty texture")
    repeats = int(np.ceil(samples / len(x)))
    return np.concatenate([x] * repeats, axis=0)[:samples]


def root_impact(core, mixed, sr, root, span_cents=350.0):
    """dB the root band moves, and how much of the mix the bed now owns.

    A positive root delta means the bed is sitting on the fundamental. Anything
    beyond about +1 dB is the bed competing with the thing the track is named
    after.
    """
    lo = root * 2.0 ** (-span_cents / 1200.0)
    hi = root * 2.0 ** (+span_cents / 1200.0)
    core_mono = core.mean(axis=1)
    mixed_mono = mixed.mean(axis=1)

    def unit(signal):
        rms = np.sqrt((signal ** 2).mean())
        return signal / rms if rms > 0 else signal

    core_mono, mixed_mono = unit(core_mono), unit(mixed_mono)
    before = band_energy(core_mono, sr, lo, hi)
    after = band_energy(mixed_mono, sr, lo, hi)
    return {
        "root_band_hz": (lo, hi),
        "root_delta_db": 20.0 * np.log10(max(after, 1e-12) / max(before, 1e-12)),
    }


def layer(core, bed, sr, root, level_db=DEFAULT_LEVEL_DB,
          highpass_hz=DEFAULT_HIGHPASS_HZ, width=0.22, seed=174):
    """Return (mixed, prepared_bed). ``core`` is never filtered or widened."""
    bed = trim_edges(bed, sr)
    bed = seamless_loop(bed, sr)

    # Clear of the root before anything else: an 8th-order zero-phase high-pass
    # 2+ octaves above 174 leaves nothing to fight the fundamental.
    sos = butter(8, highpass_hz / (sr / 2), btype="high", output="sos")
    bed = np.stack([sosfiltfilt(sos, bed[:, c]) for c in range(bed.shape[1])], axis=1)

    bed = spatialise(bed.mean(axis=1), sr, seed=seed, width=width)
    bed = tile_to(bed, len(core))

    core_rms = np.sqrt((core.mean(axis=1) ** 2).mean())
    bed_rms = np.sqrt((bed.mean(axis=1) ** 2).mean())
    if bed_rms > 0:
        bed *= (core_rms * 10.0 ** (level_db / 20.0)) / bed_rms

    if core.shape[1] == 1:
        core = np.repeat(core, 2, axis=1)
    return core + bed, bed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("core")
    parser.add_argument("bed")
    parser.add_argument("--out", default=None)
    parser.add_argument("--root", type=float, default=174.0)
    parser.add_argument("--level", type=float, default=DEFAULT_LEVEL_DB,
                        help="bed level relative to the core, dB")
    parser.add_argument("--highpass", type=float, default=DEFAULT_HIGHPASS_HZ)
    parser.add_argument("--width", type=float, default=0.22)
    parser.add_argument("--seconds", type=float, default=None,
                        help="render only the first N seconds (audition)")
    args = parser.parse_args(argv)

    sr, core = read_wav(args.core)
    bed_sr, bed = read_wav(args.bed)
    if bed_sr != sr:
        print(f"resampling bed {bed_sr} -> {sr} Hz")
        bed = resample_to(bed, bed_sr, sr)
    if args.seconds:
        core = core[: int(sr * args.seconds)]

    mixed, prepared = layer(core, bed, sr, args.root, level_db=args.level,
                            highpass_hz=args.highpass, width=args.width)

    impact = root_impact(core, mixed, sr, args.root)
    lo, hi = impact["root_band_hz"]
    print(f"core {len(core)/sr:.1f}s, bed at {args.level:+.0f} dB, "
          f"high-passed {args.highpass:g} Hz, side/mid {side_to_mid(prepared):.2f}")
    print(f"root band {lo:.0f}-{hi:.0f} Hz: {impact['root_delta_db']:+.2f} dB "
          f"({'clear' if abs(impact['root_delta_db']) <= 1.0 else 'COMPETING'})")

    peak = np.abs(mixed).max()
    if peak > 0.99:
        mixed *= 0.99 / peak
        print(f"peak was {peak:.3f}; trimmed to 0.99")
    out = Path(args.out or Path(args.core).with_name(Path(args.core).stem + "-bedded.wav"))
    wavfile.write(out, sr, mixed.astype(np.float32))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
