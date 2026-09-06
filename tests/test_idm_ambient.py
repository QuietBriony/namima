"""Smoke tests for the ambient-side IDM prototype.

Runs under pytest, or standalone:  python tests/test_idm_ambient.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from namima.idm_ambient import (  # noqa: E402
    AmbientConfig, render, scale_hz, lead_pool, pad_chord, motif_events, MODES,
)
from namima.generator import load_presets, preset_frequency  # noqa: E402

SR = 48000


def _band(sig, lo, hi):
    S = np.abs(np.fft.rfft(sig))
    f = np.fft.rfftfreq(len(sig), 1.0 / SR)
    m = (f >= lo) & (f < hi)
    return float(np.sqrt(np.mean(S[m] ** 2))) if m.any() else 0.0


def test_shape_no_clip_finite():
    st, meta = render(AmbientConfig(bars=12, mode="soft", gain=0.86))
    assert st.ndim == 2 and st.shape[1] == 2 and st.shape[0] == meta["frames"]
    assert np.isfinite(st).all()
    peak = float(np.max(np.abs(st)))
    assert peak <= 1.0 and abs(peak - 0.86) < 1e-6


def test_determinism_and_seed_sensitivity():
    a, _ = render(AmbientConfig(bars=12, seed=5))
    b, _ = render(AmbientConfig(bars=12, seed=5))
    assert np.array_equal(a, b)
    c, _ = render(AmbientConfig(bars=12, seed=6))
    assert not np.array_equal(a, c)


def test_modes_differ():
    outs = {m: render(AmbientConfig(bars=12, mode=m))[0] for m in MODES}
    assert not np.array_equal(outs["beatless"], outs["soft"])
    assert not np.array_equal(outs["soft"], outs["idm"])


def test_mono_compatible():
    """L+R must not comb the audible mid-body (iPhone-mono audition)."""
    st, _ = render(AmbientConfig(bars=12, mode="idm"))
    ratio = _band(st.mean(1), 150, 700) / max(_band(st[:, 0], 150, 700), 1e-9)
    assert 0.9 < ratio < 1.1, f"mono/L mid-body ratio {ratio:.3f}"


def test_pitches_are_solfeggio_octaves():
    p = load_presets()
    sources = [preset_frequency(f"solfeggio_{n}", p)
               for n in (174, 285, 396, 417, 528, 639, 741, 852, 963)]

    def on_grid(f):
        return any(abs(np.log2(f / s) - round(np.log2(f / s))) < 1e-9 for s in sources)

    scale = scale_hz(p)
    assert len(scale) == 9 and scale == sorted(scale)
    for f in lead_pool(scale) + pad_chord(scale, 0) + pad_chord(scale, 3):
        assert on_grid(f), f"{f} Hz is not a solfeggio octave"


def test_motif_events_in_range():
    cfg = AmbientConfig(bars=36)
    ev = motif_events(cfg, np.random.default_rng(1), pool_n=10, start_bar=8)
    assert ev, "motif should produce events"
    for bar, step, p, dur, vel in ev:
        assert 8 <= bar < cfg.bars and 0 <= step < 16 and 0 <= p < 10
        assert dur > 0 and 0.5 < vel < 1.1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
