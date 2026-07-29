"""Tests for laying an external texture bed under a rendered track.

The failure this guards against is quiet: a bed that piles onto the root does
not sound broken, it sounds "fuller", while the exact frequency the track is
named after is buried. So the root band is measured, not assumed.

Sources are synthesised here - namima rule 5, no sample files in the repo.

Runs under pytest, or standalone:  python tests/test_texture_layer.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from namima.texture_layer import (  # noqa: E402
    DEFAULT_HIGHPASS_HZ, ROOT_BAND_CENTS, highpass_for, layer, resample_to,
    root_impact, seamless_loop, tile_to, trim_edges,
)

SOLFEGGIO = (174, 285, 396, 417, 528, 639, 741, 852, 963)

SR = 44100
ROOT = 174.0


def core_track(seconds=4.0):
    """A 174 Hz fundamental with a couple of partials - the thing to protect."""
    t = np.arange(int(SR * seconds)) / SR
    x = (np.sin(2 * np.pi * ROOT * t)
         + 0.4 * np.sin(2 * np.pi * ROOT * 2 * t)
         + 0.2 * np.sin(2 * np.pi * ROOT * 3 * t))
    x /= np.abs(x).max()
    return np.stack([x, x], axis=1)


def bed_clip(seconds=3.0, seed=5, with_fades=True):
    """Bass-heavy noise with a metallic partial, faded like a generator's clip."""
    rng = np.random.default_rng(seed)
    n = int(SR * seconds)
    t = np.arange(n) / SR
    x = (0.9 * np.sin(2 * np.pi * 87.0 * t)          # the collision: 174 / 2
         + 0.25 * rng.standard_normal(n)
         + 0.3 * np.sin(2 * np.pi * 2900.0 * t))
    x /= np.abs(x).max()
    if with_fades:
        fade = int(SR * 0.5)
        x[:fade] *= np.linspace(0, 1, fade)
        x[-fade:] *= np.linspace(1, 0, fade)
    return np.stack([x, x], axis=1)


def test_highpass_clears_the_root_band_for_every_frequency():
    """The bug this caught: a fixed 800 Hz corner sits inside the root band of
    741, 852 and 963, so the bed landed on the fundamental for the top three."""
    for hz in SOLFEGGIO:
        band_top = hz * 2.0 ** (ROOT_BAND_CENTS / 1200.0)
        assert highpass_for(hz) > band_top, (hz, highpass_for(hz), band_top)


def test_highpass_keeps_the_approved_value_where_it_already_worked():
    """174-528 were approved by ear at 800 Hz; the fix must not move them."""
    for hz in (174, 285, 396, 417, 528):
        assert highpass_for(hz) == DEFAULT_HIGHPASS_HZ, hz
    for hz in (639, 741, 852, 963):
        assert highpass_for(hz) > DEFAULT_HIGHPASS_HZ, hz


def test_root_band_is_left_alone():
    core, bed = core_track(), bed_clip()
    mixed, _ = layer(core, bed, SR, ROOT, level_db=-18.0)
    delta = root_impact(core, mixed, SR, ROOT)["root_delta_db"]
    assert abs(delta) < 1.0, f"{delta:+.2f} dB on the root band"


def test_an_87hz_bed_cannot_reach_the_root_even_when_loud():
    """The bed used here is dominated by 87 Hz, one octave under the root."""
    core, bed = core_track(), bed_clip()
    mixed, _ = layer(core, bed, SR, ROOT, level_db=-6.0)
    delta = root_impact(core, mixed, SR, ROOT)["root_delta_db"]
    assert abs(delta) < 1.5, f"{delta:+.2f} dB with the bed at -6 dB"


def test_core_is_never_filtered_or_widened():
    core, bed = core_track(), bed_clip()
    mixed, prepared = layer(core, bed, SR, ROOT, level_db=-80.0)
    # At -80 dB the bed is inaudible, so the mix must be the core itself.
    # (-60 is not enough for a 1e-3 tolerance: the level is matched by RMS and
    # the bed's peak sits several times above its own RMS.)
    assert np.allclose(mixed, core, atol=1e-3)
    assert prepared.shape == (len(core), 2)


def test_louder_bed_moves_the_mix_more():
    core, bed = core_track(), bed_clip()
    quiet, _ = layer(core, bed, SR, ROOT, level_db=-30.0)
    loud, _ = layer(core, bed, SR, ROOT, level_db=-12.0)
    assert (np.abs(loud - core)).mean() > (np.abs(quiet - core)).mean()


def test_trim_removes_the_fades():
    faded = bed_clip(with_fades=True)
    trimmed = trim_edges(faded, SR)
    assert len(trimmed) < len(faded)
    edge = int(SR * 0.05)
    head = np.sqrt((trimmed[:edge].mean(axis=1) ** 2).mean())
    tail = np.sqrt((trimmed[-edge:].mean(axis=1) ** 2).mean())
    assert 0.25 < head / max(tail, 1e-9) < 4.0, (head, tail)


def test_seamless_loop_joins_to_itself():
    x = trim_edges(bed_clip(), SR)
    looped = seamless_loop(x, SR, crossfade_s=0.5)
    assert len(looped) < len(x)
    edge = int(SR * 0.05)
    joined = np.concatenate([looped, looped], axis=0)
    seam = len(looped)
    # No click: the step across the join is comparable to a step mid-clip.
    across = np.abs(np.diff(joined[seam - edge:seam + edge].mean(axis=1))).max()
    inside = np.abs(np.diff(joined[seam // 2 - edge:seam // 2 + edge].mean(axis=1))).max()
    assert across < 5.0 * inside, (across, inside)


def test_tile_matches_length_exactly():
    x = bed_clip(seconds=1.0)
    for want in (100, len(x) - 1, len(x), len(x) * 3 + 7):
        assert len(tile_to(x, want)) == want


def test_resample_preserves_duration_and_pitch():
    t = np.arange(SR) / SR
    x = np.sin(2 * np.pi * 2000.0 * t)[:, None]
    out = resample_to(x, SR, 48000)
    assert abs(len(out) / 48000.0 - 1.0) < 0.01
    spectrum = np.abs(np.fft.rfft(out[:, 0] * np.hanning(len(out))))
    peak_hz = np.fft.rfftfreq(len(out), 1 / 48000.0)[np.argmax(spectrum)]
    assert abs(peak_hz - 2000.0) < 5.0, peak_hz


def test_deterministic():
    core, bed = core_track(), bed_clip()
    first, _ = layer(core, bed, SR, ROOT, seed=174)
    second, _ = layer(core, bed, SR, ROOT, seed=174)
    assert np.array_equal(first, second)


def test_mono_core_is_accepted():
    core = core_track()[:, :1]
    mixed, _ = layer(core, bed_clip(), SR, ROOT)
    assert mixed.shape == (len(core), 2)
    assert np.isfinite(mixed).all()


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
