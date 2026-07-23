"""Smoke tests for the solfeggio IDM composer (candidate).

Runs under pytest, or standalone:  python tests/test_solfeggio_idm.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from namima.solfeggio_idm import compose, IdmConfig, build_scenes  # noqa: E402
from namima.generator import load_presets, preset_frequency  # noqa: E402

SR = 48000


def _band(sig, lo, hi):
    S = np.abs(np.fft.rfft(sig))
    f = np.fft.rfftfreq(len(sig), 1.0 / SR)
    m = (f >= lo) & (f < hi)
    return float(np.sqrt(np.mean(S[m] ** 2))) if m.any() else 0.0


def test_shape_no_clip_finite():
    st, meta = compose(IdmConfig(bars=16, gain=0.86))
    assert st.ndim == 2 and st.shape[1] == 2 and st.shape[0] == meta["frames"]
    assert np.isfinite(st).all()
    peak = float(np.max(np.abs(st)))
    assert peak <= 1.0 and abs(peak - 0.86) < 1e-6


def test_determinism():
    a, _ = compose(IdmConfig(bars=16, seed=5))
    b, _ = compose(IdmConfig(bars=16, seed=5))
    assert np.array_equal(a, b)
    c, _ = compose(IdmConfig(bars=16, seed=6))
    assert not np.array_equal(a, c)


def test_mono_compatible():
    """L+R must not comb the audible mid-body (iPhone-mono audition)."""
    st, _ = compose(IdmConfig(bars=16))
    ratio = _band(st.mean(1), 150, 700) / max(_band(st[:, 0], 150, 700), 1e-9)
    assert 0.9 < ratio < 1.1, f"mono/L mid-body ratio {ratio:.3f}"


def test_scene_pitches_from_presets():
    p = load_presets()
    allowed = {round(preset_frequency(f"solfeggio_{n}", p), 6)
               for n in (174, 285, 396, 417, 528, 639, 741, 852, 963)}
    for sc in build_scenes(p):
        assert round(sc["root"], 6) in allowed
        for key in ("bell", "pluck", "voice"):
            for f in sc[key]:
                assert round(f, 6) in allowed, f"{key} pitch {f}"
        for f in sc["pad"]:
            assert round(f, 6) in allowed or round(f / 2, 6) in allowed


def test_groove_and_bell_present():
    """Bell riff register (600-1000 Hz) and kick low band must both appear in a
    full-groove section, and the intro must have no drums."""
    st, _ = compose(IdmConfig(bars=40))
    mono = st.mean(1)
    bar = 60.0 / 114.0 * 4

    def seg(b, n=4):
        i = int(b * bar * SR)
        return mono[i:i + int(n * bar * SR)]

    groove = seg(24)
    intro = seg(2)
    # the FM bell's strike band sits ABOVE the pad's 1700 Hz lowpass, so 2.5-5.5k
    # isolates the riff (600-1000 is shared with pad harmonics — not a valid probe).
    # 3x, not stricter: since v0.5 the intro intentionally carries sparse sacred
    # golden-angle chimes, which lift the baseline in this band.
    assert _band(groove, 2500, 5500) > 3 * _band(intro, 2500, 5500), "bell riff should enter"
    assert _band(groove, 60, 250) > 1.5 * _band(intro, 60, 250), "kick should enter"


def _run_standalone():
    tests = [test_shape_no_clip_finite, test_determinism, test_mono_compatible,
             test_scene_pitches_from_presets, test_groove_and_bell_present]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {fn.__name__}: {exc}")
    print(f"\n{'ALL PASS' if not failed else str(failed) + ' FAILED'}")
    return failed


if __name__ == "__main__":
    raise SystemExit(1 if _run_standalone() else 0)
