"""Tests for the texture-layer spatialiser.

The one property that matters: this must never cost anything on the iPhone
built-in speaker, which sums to mono. A widener that combs is worse than no
widener at all, because the damage is inaudible on the headphones you tuned it
on. So mono safety is asserted at every width, not just the default.

Sources are synthesised here - namima rule 5, no sample files in the repo.

Runs under pytest, or standalone:  python tests/test_spatial.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from namima.spatial import (  # noqa: E402
    ANALYSIS_BANDS, channel_correlation, decay_noise_ir, mono_safety,
    side_to_mid, spatialise,
)

SR = 48000


def texture(seconds=2.0, seed=7):
    """Band-limited noise plus a metallic partial - the shape of a real bed."""
    rng = np.random.default_rng(seed)
    n = int(SR * seconds)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n) * 0.3
    ring = 0.5 * np.sin(2 * np.pi * 2900.0 * t) * np.exp(-((t % 0.7) / 0.4))
    x = noise + ring
    return x / np.abs(x).max()


def test_width_zero_is_a_no_op():
    x = texture()
    out = spatialise(x, SR, width=0.0)
    assert np.allclose(out[:, 0], out[:, 1])
    assert np.allclose(out[:, 0], x)
    assert side_to_mid(out) == 0.0
    assert channel_correlation(out) == 1.0


def test_mono_sum_survives_every_width():
    """A comb would eat 6-20 dB from a band. Budget: 3 dB."""
    x = texture()
    for width in (0.1, 0.25, 0.4, 0.7, 1.0):
        out = spatialise(x, SR, width=width)
        deltas = mono_safety(out, x, SR)
        assert deltas, f"width {width}: no band had enough source energy to judge"
        worst = min(deltas.values())
        assert worst > -3.0, f"width {width}: {worst:.2f} dB in {min(deltas, key=deltas.get)}"


def test_width_actually_widens():
    x = texture()
    ratios = [side_to_mid(spatialise(x, SR, width=w)) for w in (0.0, 0.1, 0.25, 0.5)]
    assert ratios == sorted(ratios), ratios
    assert ratios[-1] > 0.5, ratios


def test_deterministic_for_a_fixed_seed():
    x = texture()
    first = spatialise(x, SR, seed=174, width=0.3)
    second = spatialise(x, SR, seed=174, width=0.3)
    assert np.array_equal(first, second)


def test_seed_changes_the_room():
    x = texture()
    a = spatialise(x, SR, seed=174, width=0.3)
    b = spatialise(x, SR, seed=285, width=0.3)
    assert not np.allclose(a, b)


def test_ears_are_not_the_same_impulse():
    """The two ears must come from independent noise, or nothing decorrelates."""
    left = decay_noise_ir(SR, SR, 174, 1.0)
    right = decay_noise_ir(SR, SR, 174 + 977, 1.0)
    overlap = abs(float((left * right).sum()) /
                  np.sqrt((left ** 2).sum() * (right ** 2).sum()))
    assert overlap < 0.1, overlap


def test_no_nan_and_no_runaway_level():
    x = texture()
    out = spatialise(x, SR, width=0.5)
    assert np.isfinite(out).all()
    assert np.abs(out).max() < 4.0 * np.abs(x).max()


def test_stereo_input_is_accepted():
    x = texture()
    stereo = np.stack([x, np.roll(x, 13)], axis=1)
    out = spatialise(stereo, SR, width=0.3)
    assert out.shape == (len(x), 2)
    assert np.isfinite(out).all()


def test_mono_safety_skips_empty_bands():
    """A band the source does not occupy must not be reported at all."""
    n = int(SR * 2)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * 2000.0 * t)          # only the 800-3000 band
    out = spatialise(x, SR, width=0.4)
    reported = set(mono_safety(out, x, SR))
    assert (800, 3000) in reported
    assert (60, 250) not in reported
    assert reported <= set(ANALYSIS_BANDS)


if __name__ == "__main__":
    failures = 0
    for name, function in sorted(globals().items()):
        if not name.startswith("test_") or not callable(function):
            continue
        try:
            function()
            print(f"ok   {name}")
        except AssertionError as error:
            failures += 1
            print(f"FAIL {name}: {error}")
    raise SystemExit(1 if failures else 0)
