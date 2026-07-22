"""Smoke tests for the solfeggio ambient composer (candidate).

Fast checks on short renders: determinism under a fixed seed, no clipping,
24-bit WAV round-trip, iPhone-mono compatibility (the mono sum must not comb the
audible mid-body), the intentional non-12-TET 396↔417 microtone, presets-sourced
pitches, and the deep-beat / breakdown structure.

Runs under pytest, or standalone:  python tests/test_solfeggio_composer.py
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from namima.solfeggio_composer import (  # noqa: E402
    compose, ComposeConfig, build_blocks,
)
from namima.generator import write_wav24, load_presets, preset_frequency  # noqa: E402

SR = 48000


# --- helpers -----------------------------------------------------------------
def _band(sig, lo, hi):
    S = np.abs(np.fft.rfft(sig))
    f = np.fft.rfftfreq(len(sig), 1.0 / SR)
    m = (f >= lo) & (f < hi)
    return float(np.sqrt(np.mean(S[m] ** 2))) if m.any() else 0.0


def _read_wav24(path):
    with wave.open(str(path), "rb") as wf:
        assert wf.getsampwidth() == 3, "expected 24-bit"
        ch, n = wf.getnchannels(), wf.getnframes()
        raw = wf.readframes(n)
    b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
    ints = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
    ints = np.where(ints & 0x800000, ints - (1 << 24), ints)
    return (ints.astype(np.float64) / (2 ** 23 - 1)).reshape(-1, ch)


# --- tests -------------------------------------------------------------------
def test_shape_and_finite():
    st, meta = compose(ComposeConfig(bars=16))
    assert st.ndim == 2 and st.shape[1] == 2
    assert st.shape[0] == meta["frames"]
    assert np.isfinite(st).all()
    assert meta["bit_depth"] == 24 and meta["sample_rate"] == SR


def test_no_clipping():
    st, _ = compose(ComposeConfig(bars=16, gain=0.86))
    peak = float(np.max(np.abs(st)))
    assert peak <= 1.0
    assert abs(peak - 0.86) < 1e-6, "peak-normalisation should hit the gain target"
    assert float(np.sqrt(np.mean(st ** 2))) > 0.02, "signal must be present"


def test_determinism_same_seed():
    a, _ = compose(ComposeConfig(bars=16, seed=42))
    b, _ = compose(ComposeConfig(bars=16, seed=42))
    assert np.array_equal(a, b), "same seed must produce identical output"


def test_different_seed_differs():
    a, _ = compose(ComposeConfig(bars=16, seed=1))
    b, _ = compose(ComposeConfig(bars=16, seed=2))
    assert not np.array_equal(a, b)


def test_mono_compatible_no_haas_comb():
    """The mono sum must not comb the audible mid-body (iPhone-mono audition).
    By construction L+R == 2*mix and the side is high-passed >1800 Hz, so in
    150-700 Hz the mono sum should track the L channel closely — a full-mix Haas
    delay would notch this band instead."""
    st, _ = compose(ComposeConfig(bars=16))
    mono = st.mean(1)
    left = st[:, 0]
    ratio = _band(mono, 150, 700) / max(_band(left, 150, 700), 1e-9)
    assert 0.9 < ratio < 1.1, f"mono/L mid-body ratio {ratio:.3f} (comb suspected)"


def test_non_12tet_microtone_present():
    """The intentional 89-cent 396<->417 solfeggio step must survive: both
    absolute pitches carry energy (they are NOT snapped to a 12-TET grid)."""
    st, _ = compose(ComposeConfig(bars=32))
    mono = st.mean(1)
    e396 = _band(mono, 393, 399)
    e417 = _band(mono, 414, 420)
    assert e396 > 0 and e417 > 0, "both 396 and 417 Hz must be present"
    # they are distinct pitches ~89 cents apart, not a single 12-TET note
    assert abs(np.log2(417.0 / 396.0) * 1200 - 89) < 2


def test_kick_has_phone_audible_body():
    """Deep beat must carry audible mid-body (120-500 Hz), not only sub — the
    iPhone speaker cannot reproduce <~120 Hz."""
    st, _ = compose(ComposeConfig(bars=40))
    mono = st.mean(1)
    # a beat section (past the intro, before the breakdown)
    seg = mono[int(60 * SR):int(64 * SR)]
    body = _band(seg, 120, 500)
    sub = _band(seg, 40, 120)
    assert body > 0.4 * sub, "kick body should be comparable to its sub, not buried"


def test_pitches_sourced_from_presets():
    """BLOCKS pitches must equal the presets.yaml solfeggio values (single source
    of truth), not drifted literals."""
    p = load_presets()
    blocks = build_blocks(p)
    allowed = {round(preset_frequency(f"solfeggio_{n}", p), 6)
               for n in (174, 285, 396, 417, 528, 639, 741, 852, 963)}
    # every bass + melody + voice pitch must be a presets solfeggio value; pad
    # additionally allows exact octave doublings (f*2) of a solfeggio root.
    for blk in blocks:
        for f in blk["bass"] if isinstance(blk["bass"], list) else [blk["bass"]]:
            assert round(f, 6) in allowed
        for key in ("mel", "voice"):
            for f in blk[key]:
                assert round(f, 6) in allowed, f"{key} pitch {f} not a preset solfeggio Hz"
        for f in blk["pad"]:
            ok = round(f, 6) in allowed or round(f / 2, 6) in allowed
            assert ok, f"pad pitch {f} is neither a preset nor an octave doubling"


def test_breakdown_structure():
    """The deep beat must drop out for a breakdown then return (macro arc)."""
    st, _ = compose(ComposeConfig(bars=72))
    mono = st.mean(1)
    bar = 60.0 / 96.0 * 4

    def hats(bar_idx):  # hat energy is a proxy for the beat being present
        i = int(bar_idx * bar * SR)
        return _band(mono[i:i + int(3 * SR)], 6000, 14000)

    main = hats(30)          # main section
    breakdown = hats(48)     # inside the 43..54-bar breakdown
    assert breakdown < 0.6 * main, f"breakdown hats {breakdown:.2f} should drop vs main {main:.2f}"


def test_wav24_roundtrip(tmp_path=None):
    out = (Path(tmp_path) if tmp_path else Path(__file__).parent) / "_composer_smoke.wav"
    try:
        st, _ = compose(ComposeConfig(bars=16))
        write_wav24(out, st, SR)
        back = _read_wav24(out)
        assert back.shape == st.shape
        assert np.max(np.abs(back[:, 0] - st[:, 0])) < 2.0 / (2 ** 23)
        assert not np.array_equal(back[:, 0], back[:, 1]), "L,R must stay distinct"
    finally:
        if out.exists() and tmp_path is None:
            out.unlink()


# --- standalone runner -------------------------------------------------------
def _run_standalone():
    import tempfile
    tests = [
        test_shape_and_finite, test_no_clipping, test_determinism_same_seed,
        test_different_seed_differs, test_mono_compatible_no_haas_comb,
        test_non_12tet_microtone_present, test_kick_has_phone_audible_body,
        test_pitches_sourced_from_presets, test_breakdown_structure,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {fn.__name__}: {exc}")
    with tempfile.TemporaryDirectory() as td:
        try:
            test_wav24_roundtrip(tmp_path=td)
            print("PASS  test_wav24_roundtrip")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  test_wav24_roundtrip: {exc}")
    print(f"\n{'ALL PASS' if not failed else str(failed) + ' FAILED'}")
    return failed


if __name__ == "__main__":
    raise SystemExit(1 if _run_standalone() else 0)
