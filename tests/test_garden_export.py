"""Tests for the music-to-garden contract exporter.

The renderer on the hazama side re-validates its input and refuses bad data, so
a malformed export does not corrupt anything - it just stops the pipeline at the
far end, where the cause is hardest to see. These tests keep the failure here.

Beyond shape, two things are worth asserting because they are the reason the
exporter exists at all: the section boundaries must match the times the composer
actually changes harmonic scene, and the same track must export the same values
every time (contract rule 4).

Runs under pytest, or standalone:  python tests/test_garden_export.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from namima import solfeggio_composer as sc  # noqa: E402
from namima.garden_export import (  # noqa: E402
    CONTRACT_VERSION, GARDENS, SECTION_IDS, _config_for, build,
    camera_hint_for, energy_curve_from_audio, sections_for, tension_curve_for,
    validate,
)
from namima.hazama_release import DRIFT_CHARACTER, drift_blocks_for  # noqa: E402

ALL_HZ = sorted(DRIFT_CHARACTER)
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
SECTION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def test_every_frequency_exports_and_validates():
    for hz in ALL_HZ:
        document = build(hz)
        validate(document)


def test_required_fields_and_patterns():
    for hz in ALL_HZ:
        d = build(hz)
        assert d["contract_version"] == CONTRACT_VERSION
        assert ID_PATTERN.match(d["source_track_id"]), d["source_track_id"]
        assert d["frequency_hz"] == float(hz)
        assert 0 <= d["deterministic_seed"] <= 2147483647
        assert d["duration_seconds"] > 0
        assert 1 <= len(d["palette_hint"]["colors_srgb"]) <= 8
        assert all(HEX_PATTERN.match(c) for c in d["palette_hint"]["colors_srgb"])
        assert len(d["palette_hint"]["mood_tags"]) <= 8
        assert d["camera_motion_hint"]["mode"] in (
            "static", "drift", "push_in", "pull_back", "orbit")
        assert 0.0 <= d["camera_motion_hint"]["amount"] <= 1.0
        assert SECTION_PATTERN.match(d["garden_motif"]["id"]), d["garden_motif"]["id"]
        assert len(d["garden_motif"]["tags"]) <= 12
        for section in d["sections"]:
            assert SECTION_PATTERN.match(section["id"]), section["id"]


def test_sections_match_the_composer_scene_changes():
    """The whole point: the sky may turn where the harmony turns, not elsewhere."""
    for hz in ALL_HZ:
        cfg = _config_for(hz)
        expected = [(a * cfg.bar, b * cfg.bar) for a, b in sc.block_ranges(cfg)]
        actual = [(s["start_seconds"], s["end_seconds"]) for s in sections_for(hz)]
        assert len(actual) == len(expected) == len(SECTION_IDS)
        for (want_a, want_b), (got_a, got_b) in zip(expected, actual):
            assert abs(want_a - got_a) < 1e-5
            assert abs(want_b - got_b) < 1e-5


def test_sections_tile_the_track_without_gaps():
    for hz in ALL_HZ:
        d = build(hz)
        sections = d["sections"]
        assert sections[0]["start_seconds"] == 0.0
        for earlier, later in zip(sections, sections[1:]):
            assert abs(earlier["end_seconds"] - later["start_seconds"]) < 1e-6
        assert abs(sections[-1]["end_seconds"] - d["duration_seconds"]) < 1e-3


# 741, 852 and 963 already reach 963 Hz - the top of the solfeggio set - in
# every block, so block 3's added partial cannot widen them and their span is
# set by the alternating bass alone.
CEILING_SATURATED = (741, 852, 963)


def test_tension_opens_on_the_third_block_where_the_music_opens():
    for hz in ALL_HZ:
        if hz in CEILING_SATURATED:
            continue
        curve = tension_curve_for(hz)
        assert max(point["value"] for point in curve) == 1.0
        peak_time = max(curve, key=lambda p: p["value"])["time_seconds"]
        third = sections_for(hz)[2]
        assert third["start_seconds"] - 1e-6 <= peak_time <= third["end_seconds"], hz


def test_the_top_three_are_ceiling_saturated_not_broken():
    """Pin the reason those three are excluded, so a real regression still fails."""
    presets = None
    for hz in CEILING_SATURATED:
        blocks = drift_blocks_for(hz, presets or __import__(
            "namima.generator", fromlist=["load_presets"]).load_presets())
        tops = []
        for block in blocks:
            pitches = [block["bass"], *block["pad"], *block["mel"], *block["voice"]]
            tops.append(max(pitches))
        assert len(set(round(t, 6) for t in tops)) == 1, (hz, tops)
        assert abs(tops[0] - 963.0) < 1e-6, (hz, tops[0])


def test_tension_curve_always_spans_zero_to_one():
    for hz in ALL_HZ:
        curve = tension_curve_for(hz)
        values = [point["value"] for point in curve]
        assert max(values) == 1.0 and min(values) == 0.0, hz


def test_export_is_deterministic():
    for hz in (174, 528, 963):
        first = json.dumps(build(hz), sort_keys=True)
        second = json.dumps(build(hz), sort_keys=True)
        assert first == second


def test_measured_and_guessed_tracks_are_labelled_differently():
    """A guessed envelope must never be mistaken for a measured one."""
    guessed = build(174)
    sr = 48000
    audio = np.sin(np.linspace(0, 400.0, sr * 4))[:, None]
    measured = build(174, audio=audio, sample_rate=sr)
    assert guessed["source_track_id"].endswith("-unmeasured")
    assert not measured["source_track_id"].endswith("-unmeasured")


def test_energy_curve_from_audio_spans_the_track():
    sr = 8000
    duration = 20.0
    t = np.arange(int(sr * duration)) / sr
    audio = (np.sin(2 * np.pi * 100 * t) * np.linspace(0.1, 1.0, len(t)))[:, None]
    curve = energy_curve_from_audio(audio, sr, duration)
    assert curve[0]["time_seconds"] == 0.0
    assert abs(curve[-1]["time_seconds"] - duration) < 1.0
    assert all(0.0 <= point["value"] <= 1.0 for point in curve)
    assert curve[-1]["value"] > curve[0]["value"]      # the ramp is visible


def test_camera_hint_is_stiller_for_the_deepest_spaces():
    """963 has the longest tail of the nine; it must not be the busiest camera."""
    deepest = camera_hint_for(963)
    tightest = camera_hint_for(741)          # smallest `space`
    assert deepest["amount"] < tightest["amount"]


def test_validate_rejects_overlapping_sections():
    document = build(174)
    document["sections"][1]["start_seconds"] -= 5.0
    try:
        validate(document)
    except ValueError as error:
        assert "overlaps" in str(error)
    else:
        raise AssertionError("overlap was accepted")


def test_validate_rejects_a_curve_that_does_not_start_at_zero():
    document = build(174)
    document["energy_curve"][0]["time_seconds"] = 1.0
    try:
        validate(document)
    except ValueError as error:
        assert "start at 0" in str(error)
    else:
        raise AssertionError("late curve start was accepted")


def test_validate_rejects_a_curve_running_past_the_track():
    document = build(174)
    document["tension_curve"][-1]["time_seconds"] = document["duration_seconds"] + 10
    try:
        validate(document)
    except ValueError as error:
        assert "after duration_seconds" in str(error)
    else:
        raise AssertionError("overlong curve was accepted")


def test_all_nine_gardens_are_described():
    assert sorted(GARDENS) == ALL_HZ
    ids = [GARDENS[hz]["motif"] for hz in ALL_HZ]
    assert len(set(ids)) == len(ids), "garden motif ids must be unique"


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
