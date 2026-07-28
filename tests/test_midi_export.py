"""Tests for the sustained solfeggio MIDI writer.

The failure that matters is silent: a note that lands on the wrong key still
plays, still sounds musical, and is simply no longer the frequency the whole
catalogue is built on. So every key this writes is checked back through the
tuning table.

Runs under pytest, or standalone:  python tests/test_midi_export.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from namima.generator import load_presets  # noqa: E402
from namima.hazama_release import DRIFT_CHARACTER, drift_blocks_for  # noqa: E402
from namima.midi_export import (  # noqa: E402
    TICKS_PER_BEAT, block_voices, build_midi, key_for_frequency,
)
from namima.tuning import midi_frequency  # noqa: E402


def parse(data):
    """Minimal SMF reader: returns (format, ntracks, division, [track_bytes])."""
    assert data[:4] == b"MThd", data[:4]
    length, fmt, ntracks, division = struct.unpack(">IHHH", data[4:14])
    assert length == 6
    tracks, offset = [], 14
    while offset < len(data):
        assert data[offset:offset + 4] == b"MTrk", data[offset:offset + 4]
        size = struct.unpack(">I", data[offset + 4:offset + 8])[0]
        tracks.append(data[offset + 8:offset + 8 + size])
        offset += 8 + size
    return fmt, ntracks, division, tracks


def note_ons(track):
    """(key, channel) for every note-on with velocity > 0."""
    out, index = [], 0
    while index < len(track):
        delta = 0
        while track[index] & 0x80:
            delta = (delta << 7) | (track[index] & 0x7F)
            index += 1
        delta = (delta << 7) | track[index]
        index += 1
        status = track[index]
        if status == 0xFF:
            index += 1
            meta_len = track[index + 1]
            index += 2 + meta_len
            continue
        key, velocity = track[index + 1], track[index + 2]
        if status & 0xF0 == 0x90 and velocity > 0:
            out.append((key, status & 0x0F))
        index += 3
    return out


def test_header_is_a_two_track_smf():
    fmt, ntracks, division, tracks = parse(build_midi(174, seconds=8.0))
    assert fmt == 1
    assert ntracks == 2 and len(tracks) == 2
    assert division == TICKS_PER_BEAT


def test_every_key_sounds_a_pitch_the_composer_uses():
    presets = load_presets()
    for hz in (174, 528, 963):
        wanted = set()
        for block in drift_blocks_for(hz, presets):
            wanted |= {round(p, 4) for p in
                       (block["bass"], *block["pad"], *block["mel"])}
        _, _, _, tracks = parse(build_midi(hz, seconds=8.0, presets=presets))
        keys = {key for track in tracks for key, _ in note_ons(track)}
        assert keys, hz
        for key in keys:
            sounded = round(midi_frequency(key, presets), 4)
            assert sounded in wanted, (hz, key, sounded)


def test_low_and_high_go_to_separate_channels():
    _, _, _, tracks = parse(build_midi(174, seconds=8.0))
    low = {channel for _, channel in note_ons(tracks[0])}
    high = {channel for _, channel in note_ons(tracks[1])}
    assert low == {0} and high == {1}


def test_no_block_doubles_a_pitch_across_the_two_parts():
    """Two instruments landing on one note just thickens the bottom.

    Asserted per BLOCK, not across the track: a pitch that is the pad's in one
    block can legitimately be the melody's in another - that is the harmony
    moving. Two rejected assertions got here first, both encoding an assumption
    the composer does not make: that the melody sits entirely above the pad
    (it does not - the pool is chosen by nearness to the centre), and that the
    two parts never share a key anywhere in the track (they do, in different
    blocks).
    """
    presets = load_presets()
    for hz in sorted(DRIFT_CHARACTER):
        for index, block in enumerate(drift_blocks_for(hz, presets)):
            low, high = block_voices(block)
            assert low and high, (hz, index)
            assert not (set(low) & set(high)), (hz, index, sorted(set(low) & set(high)))


def test_key_lookup_is_exact_or_refuses():
    presets = load_presets()
    assert abs(midi_frequency(key_for_frequency(174.0, presets), presets) - 174.0) < 1e-6
    assert abs(midi_frequency(key_for_frequency(963.0, presets), presets) - 963.0) < 1e-6
    try:
        key_for_frequency(1234.5678, presets)
    except ValueError:
        pass
    else:
        raise AssertionError("an off-scale pitch was silently snapped to a key")


def test_deterministic_and_covers_every_frequency():
    for hz in sorted(DRIFT_CHARACTER):
        first = build_midi(hz, seconds=8.0)
        second = build_midi(hz, seconds=8.0)
        assert first == second, hz
        assert len(first) > 60, hz


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
