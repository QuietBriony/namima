"""Write a sustained MIDI that plays the real solfeggio pitches in a DAW.

Why this is not just "a few long notes"
---------------------------------------
Two problems have to be solved together. A DAW instrument is a 12-TET keyboard,
so the pitches must be routed through the tuning table in ``namima.tuning`` - a
plain C-major sketch would silently replace 174 Hz with 174.61. And the 6.7 s
diagnostic MIDI that came with the Sonar handoff is far too short to judge a pad
or a drone: an ambient voice does not show its character until it has been held.

So this writes the pitches the drift composer ACTUALLY uses for a given
frequency, on the MIDI keys that the .tun/.scl mapping turns back into those
exact hertz, held long enough to hear.

Channel 1 carries the low voices (bass and pad), channel 2 the melody pool, so
one file can drive two instruments at once and they can be exported separately.

Requires the matching tuning file to be loaded in the instrument. Without it the
notes are simply wrong, which is the whole reason ``namima.tuning`` exists.

    python -m namima.midi_export 174 --out sustained-174.mid --seconds 48
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

from .generator import load_presets
from .hazama_release import drift_blocks_for
from .tuning import NOTES_PER_OCTAVE, REFERENCE_KEY, build_scale

__version__ = "1.0.0"
TICKS_PER_BEAT = 480


def key_for_frequency(frequency, presets=None, tolerance_cents=0.5):
    """The MIDI key that sounds ``frequency`` under the tuning table."""
    scale = build_scale(presets)
    base = scale[0][0]
    best_key, best_error = None, None
    for key in range(0, 128):
        offset = key - REFERENCE_KEY
        octave, degree = divmod(offset, NOTES_PER_OCTAVE)
        sounded = scale[degree][0] * (2.0 ** octave) * (base / scale[0][0])
        error = abs(1200.0 * (sounded / frequency - 1.0) / 1.0)   # ~cents near 1
        if best_error is None or error < best_error:
            best_key, best_error = key, error
        if abs(sounded - frequency) < 1e-6:
            return key
    if best_error is not None and best_error <= tolerance_cents:
        return best_key
    raise ValueError(f"no key sounds {frequency} Hz under this tuning")


def _varlen(value):
    out = bytearray([value & 0x7F])
    value >>= 7
    while value:
        out.insert(0, (value & 0x7F) | 0x80)
        value >>= 7
    return bytes(out)


def _track(events):
    """events: list of (delta_ticks, status, data1, data2)."""
    data = bytearray()
    for delta, status, d1, d2 in events:
        data += _varlen(delta) + bytes([status, d1, d2])
    data += _varlen(0) + b"\xFF\x2F\x00"                # end of track
    return b"MTrk" + struct.pack(">I", len(data)) + bytes(data)


def block_voices(block):
    """Split one harmonic block into (low pitches, high pitches).

    The composer's `mel` is a pool to pick from, not a chord, and for most
    frequencies it contains the centre pitch that the pad already holds.
    Sounding both at once would double the bottom and muddy it, so the high
    part takes the melody pitches this block's low part does NOT have, from the
    top down. Across the whole track a pitch can still be low in one block and
    high in another - that is the harmony moving, not a collision.
    """
    low = sorted({block["bass"], *block["pad"]})
    high = sorted(set(block["mel"]) - set(low))[-3:]
    if not high:
        high = sorted(set(block["mel"]))[-1:]
    return low, high


def build_midi(frequency, seconds=48.0, presets=None, velocity=72):
    """One block per quarter of the duration, matching the composer's scenes."""
    presets = presets or load_presets()
    blocks = drift_blocks_for(frequency, presets)
    block_seconds = seconds / len(blocks)
    # 120 bpm nominal: a DAW shows sane bars, and the note lengths are what
    # matters here, not the grid.
    ticks_per_second = TICKS_PER_BEAT * 2.0
    block_ticks = int(block_seconds * ticks_per_second)

    low_events, high_events = [], []
    for block in blocks:
        low, high = block_voices(block)
        for pitches, channel, events in (
            (low, 0, low_events), (high, 1, high_events),
        ):
            keys = []
            for pitch in pitches:
                try:
                    keys.append(key_for_frequency(pitch, presets))
                except ValueError:
                    continue
            keys = sorted(set(keys))
            if not keys:
                events.append((block_ticks, 0x80 | channel, 60, 0))
                continue
            for index, key in enumerate(keys):
                events.append((0, 0x90 | channel, key, velocity if index == 0
                               else max(velocity - 12, 1)))
            events.append((block_ticks, 0x80 | channel, keys[0], 0))
            for key in keys[1:]:
                events.append((0, 0x80 | channel, key, 0))

    header = b"MThd" + struct.pack(">IHHH", 6, 1, 2, TICKS_PER_BEAT)
    return header + _track(low_events) + _track(high_events)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("frequency", type=int)
    parser.add_argument("--out", required=True)
    parser.add_argument("--seconds", type=float, default=48.0)
    args = parser.parse_args(argv)

    presets = load_presets()
    data = build_midi(args.frequency, seconds=args.seconds, presets=presets)
    Path(args.out).write_bytes(data)
    print(f"wrote {args.out}  ({len(data)} bytes, {args.seconds:.0f}s)")

    blocks = drift_blocks_for(args.frequency, presets)
    print("pitch -> MIDI key (needs hazama-solfeggio-9.tun / .scl loaded):")
    seen = set()
    for block in blocks:
        for pitch in sorted({block["bass"], *block["pad"], *block["mel"]}):
            if round(pitch, 4) in seen:
                continue
            seen.add(round(pitch, 4))
            try:
                print(f"  {pitch:8.2f} Hz -> key {key_for_frequency(pitch, presets):3d}")
            except ValueError:
                print(f"  {pitch:8.2f} Hz -> (not on the scale; skipped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
