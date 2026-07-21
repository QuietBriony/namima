"""Smoke tests for the namima offline ambient renderer (candidate).

Fast (5-second) checks: waveform length, no clipping, correct fundamental via
FFT, determinism under a fixed seed, 24-bit WAV round-trip, binaural separation,
and presets.yaml ↔ SKILL.md frequency-table sync.

Runs under pytest, or standalone:  python tests/test_generator.py
"""

from __future__ import annotations

import re
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from namima import generator as gen  # noqa: E402

SR = 48000
SMOKE_S = 5.0
BASE = 128.0


# --- helpers -----------------------------------------------------------------
def _read_wav24(path):
    """Read a 24-bit PCM WAV back to a float array of shape (n, channels)."""
    with wave.open(str(path), "rb") as wf:
        assert wf.getsampwidth() == 3, "expected 24-bit"
        ch, sr, n = wf.getnchannels(), wf.getframerate(), wf.getnframes()
        raw = wf.readframes(n)
    b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
    ints = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
    ints = np.where(ints & 0x800000, ints - (1 << 24), ints)  # sign-extend int24
    x = ints.astype(np.float64) / (2 ** 23 - 1)
    return x.reshape(-1, ch), sr


def _dominant_freq(sig, sr):
    mag = np.abs(np.fft.rfft(sig * np.hanning(len(sig))))
    freqs = np.fft.rfftfreq(len(sig), 1.0 / sr)
    return float(freqs[int(np.argmax(mag))])


def _band_energy(sig, sr, f, half_hz=3.0):
    """Summed spectral magnitude in [f-half, f+half] — robust to detune spread
    (a single-bin peak can be misleading once partials cluster)."""
    spec = np.abs(np.fft.rfft(sig * np.hanning(len(sig))))
    freqs = np.fft.rfftfreq(len(sig), 1.0 / sr)
    mask = (freqs >= f - half_hz) & (freqs <= f + half_hz)
    return float(np.sum(spec[mask]))


def _skill_md_frequencies():
    """Parse the frequency table straight out of SKILL.md (the source of truth)."""
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    table = {}
    for line in skill.splitlines():
        m = re.match(r"\|\s*`(\w+)`\s*\|\s*([\d.]+)\s*\|", line)
        if m:
            table[m.group(1)] = float(m.group(2))
    return table


# --- tests -------------------------------------------------------------------
def test_length_and_shape():
    stereo, meta = gen.render(BASE, duration=SMOKE_S, sample_rate=SR, seed=0)
    assert stereo.shape == (int(SMOKE_S * SR), 2)
    assert meta["frames"] == int(SMOKE_S * SR)
    assert np.isfinite(stereo).all()


def test_no_clipping_and_signal_present():
    stereo, _ = gen.render(BASE, duration=SMOKE_S, sample_rate=SR, gain=0.5, seed=0)
    peak = float(np.max(np.abs(stereo)))
    assert peak <= 1.0, "must not exceed full scale"
    assert abs(peak - 0.5) < 1e-6, "peak-normalisation should hit the gain target"
    assert float(np.sqrt(np.mean(stereo ** 2))) > 0.05, "signal must be present"


def test_fundamental_fft():
    # The fundamental band must carry more energy than either octave partial
    # (band energy, not single-bin peak — detune spread makes peaks fragile).
    stereo, _ = gen.render(BASE, duration=SMOKE_S, sample_rate=SR, seed=0)
    ch = stereo[:, 0]
    e_fund = _band_energy(ch, SR, BASE)
    assert e_fund > _band_energy(ch, SR, BASE * 2), "fundamental should beat the upper octave"
    assert e_fund > _band_energy(ch, SR, BASE / 2), "fundamental should beat the lower octave"


def test_determinism_same_seed():
    a, _ = gen.render(BASE, duration=SMOKE_S, sample_rate=SR, seed=42)
    b, _ = gen.render(BASE, duration=SMOKE_S, sample_rate=SR, seed=42)
    assert np.array_equal(a, b), "same seed must produce identical output"


def test_different_seed_differs():
    a, _ = gen.render(BASE, duration=SMOKE_S, sample_rate=SR, seed=1)
    b, _ = gen.render(BASE, duration=SMOKE_S, sample_rate=SR, seed=2)
    assert not np.array_equal(a, b), "different seeds should differ"


def test_wav24_roundtrip(tmp_path=None):
    out = (Path(tmp_path) if tmp_path else Path(gen.__file__).parent) / "_smoke_out.wav"
    try:
        # binaural so L != R — this exercises the WAV L,R interleave, which an
        # L==R fixture cannot (a channel swap/duplication would go unnoticed).
        stereo, meta = gen.render(
            BASE, duration=SMOKE_S, sample_rate=SR, binaural_offset=4.0, seed=0, out_path=out
        )
        assert meta["bit_depth"] == 24 and meta["sample_rate"] == SR
        back, sr = _read_wav24(out)
        assert sr == SR
        assert back.shape == stereo.shape
        # each channel round-trips independently within 24-bit quantisation error
        assert np.max(np.abs(back[:, 0] - stereo[:, 0])) < 2.0 / (2 ** 23)
        assert np.max(np.abs(back[:, 1] - stereo[:, 1])) < 2.0 / (2 ** 23)
        assert not np.array_equal(back[:, 0], back[:, 1]), "L,R must stay distinct through the WAV"
    finally:
        if out.exists() and tmp_path is None:
            out.unlink()


def test_binaural_separates_channels():
    stereo, meta = gen.render(BASE, duration=SMOKE_S, sample_rate=SR, binaural_offset=4.0, seed=0)
    assert meta["binaural_offset_hz"] == 4.0
    assert not np.array_equal(stereo[:, 0], stereo[:, 1]), "binaural L and R must differ"
    mono, _ = gen.render(BASE, duration=SMOKE_S, sample_rate=SR, binaural_offset=0.0, seed=0)
    assert np.array_equal(mono[:, 0], mono[:, 1]), "0 offset must keep L == R"


def test_binaural_beat_rate():
    offset = 4.0
    # Isolate the fundamentals (no octaves, no detune) so the L/R beat is a clean
    # single-tone difference of `offset` Hz.
    stereo, _ = gen.render(
        BASE, duration=SMOKE_S, sample_rate=SR, octaves=(), detune_cents=0.0,
        binaural_offset=offset, seed=0,
    )
    lf = _dominant_freq(stereo[:, 0], SR)
    rf = _dominant_freq(stereo[:, 1], SR)
    assert abs((rf - lf) - offset) < 1.0, f"R-L fundamental gap {rf - lf:.2f} should be ~{offset} Hz"


def test_note_to_freq_matches_presets():
    # equal-tempered values (NOT the rounded presets): C3@432 = 128.43 Hz,
    # C5@444 ≈ 528.0 Hz. The c3_128 preset (128.0) is the nominal value.
    assert abs(gen.note_to_freq("C3", 432) - 128.434) < 0.01
    assert abs(gen.note_to_freq("C5", 444) - 528.0) < 0.05


def test_presets_match_skill_table():
    """presets.yaml frequencies MUST equal the table parsed live from SKILL.md."""
    skill = _skill_md_frequencies()
    assert len(skill) == 11, f"expected 11 rows parsed from SKILL.md, got {len(skill)}"
    presets = gen.load_presets()
    assert {k: float(v) for k, v in presets["frequencies"].items()} == skill
    assert sorted(presets["tunings"]) == [432, 440, 444]


def test_defaults_present_and_typed():
    d = gen.load_presets()["defaults"]
    assert isinstance(d["sample_rate"], int) and d["sample_rate"] == 48000
    assert d["duration_s"] > 0 and d["smoke_duration_s"] > 0
    assert isinstance(d["octaves"], list) and all(isinstance(o, int) for o in d["octaves"])
    assert 0 < d["gain"] <= 1


def test_load_presets_rejects_bad_defaults(tmp_path=None):
    import tempfile
    bad = "tunings: [432]\nfrequencies:\n  x: 100.0\ndefaults:\n  sample_rate: 0\n"
    fd = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
    fd.write(bad)
    fd.close()
    try:
        raised = False
        try:
            gen.load_presets(fd.name)
        except ValueError:
            raised = True
        assert raised, "load_presets should reject sample_rate: 0"
    finally:
        import os
        os.unlink(fd.name)


def test_add_reference_layer_is_reserved():
    try:
        gen.add_reference_layer(np.zeros((10, 2)), "x.wav", 128.0)
    except NotImplementedError:
        return
    raise AssertionError("add_reference_layer should raise NotImplementedError (reserved)")


# --- standalone runner (no pytest required) ----------------------------------
def _run_standalone():
    import tempfile
    tests = [
        test_length_and_shape, test_no_clipping_and_signal_present, test_fundamental_fft,
        test_determinism_same_seed, test_different_seed_differs,
        test_binaural_separates_channels, test_binaural_beat_rate,
        test_note_to_freq_matches_presets, test_presets_match_skill_table,
        test_defaults_present_and_typed, test_load_presets_rejects_bad_defaults,
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
    # add_reference_layer reserved-interface check (no pytest dependency)
    try:
        gen.add_reference_layer(np.zeros((10, 2)), "x.wav", 128.0)
        failed += 1
        print("FAIL  test_add_reference_layer_is_reserved: did not raise")
    except NotImplementedError:
        print("PASS  test_add_reference_layer_is_reserved")
    print(f"\n{'ALL PASS' if not failed else str(failed) + ' FAILED'}")
    return failed


if __name__ == "__main__":
    raise SystemExit(1 if _run_standalone() else 0)
