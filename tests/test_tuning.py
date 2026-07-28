"""Tests for the solfeggio tuning tables (Scala .scl/.kbm + AnaMark .tun).

The whole point of these files is that a DAW instrument plays the solfeggio
frequencies EXACTLY. A rounding slip here is silent — the patch still makes a
nice sound, it is just no longer 528 Hz — so the exactness is asserted hard.

Runs under pytest, or standalone:  python tests/test_tuning.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from namima.tuning import (  # noqa: E402
    MIDI_0_HZ, NOTES_PER_OCTAVE, REFERENCE_KEY, build_scale, fold_to_octave,
    midi_frequency, nearest_12tet, render_kbm, render_scl, render_tun,
    scale_cents, solfeggio_frequencies, true_pitch_keys, write_all,
)
from namima.generator import load_presets, preset_frequency  # noqa: E402


def test_every_solfeggio_sounds_exactly():
    """Each of the nine is reachable at its true absolute Hz."""
    rows = true_pitch_keys()
    assert len(rows) == 9
    for key, sounded, source in rows:
        assert abs(sounded - source) < 1e-9, f"key {key}: {sounded} != {source}"


def test_mapped_pitches_match_presets():
    """Pitches are sourced from presets.yaml, not re-typed in tuning.py."""
    presets = load_presets()
    expected = {preset_frequency(f"solfeggio_{n}", presets)
                for n in (174, 285, 396, 417, 528, 639, 741, 852, 963)}
    assert {source for _, _, source in true_pitch_keys()} == expected


def test_scale_is_octave_periodic():
    """Nine notes per octave: key n+9 is exactly twice key n."""
    for key in range(24, 100):
        assert abs(midi_frequency(key + NOTES_PER_OCTAVE) - 2.0 * midi_frequency(key)) < 1e-9


def test_reference_key_is_the_lowest_solfeggio():
    assert abs(midi_frequency(REFERENCE_KEY) - min(solfeggio_frequencies())) < 1e-9


def test_fold_lands_inside_the_octave():
    base = min(solfeggio_frequencies())
    for frequency in solfeggio_frequencies():
        folded = fold_to_octave(frequency, base)
        assert base <= folded < base * 2.0
        ratio = frequency / folded
        assert abs(ratio - round(ratio)) < 1e-9      # a whole number of octaves
        assert abs(math.log2(ratio) - round(math.log2(ratio))) < 1e-9


def test_scale_degrees_are_sorted_and_period_is_an_octave():
    cents = scale_cents()
    assert len(cents) == NOTES_PER_OCTAVE
    assert cents == sorted(cents)
    assert abs(cents[-1] - 1200.0) < 1e-9
    assert all(0.0 < value < 1200.0 for value in cents[:-1])


def test_tun_round_trips_to_the_same_frequencies():
    """A .tun line is cents from MIDI 0; re-deriving must give the mapping back."""
    lines = [line for line in render_tun().splitlines() if line.startswith("note ")]
    assert len(lines) == 128
    for line in lines:
        key_text, cents_text = line[len("note "):].split("=")
        key = int(key_text)
        frequency = MIDI_0_HZ * (2.0 ** (float(cents_text) / 1200.0))
        # relative: a .tun stores cents, so absolute error grows with pitch.
        # 8 decimal places of a cent is ~6e-12 relative — nowhere near audible.
        assert math.isclose(frequency, midi_frequency(key), rel_tol=1e-9), key


def test_scl_and_kbm_headers():
    scl = [line for line in render_scl().splitlines()
           if line.strip() and not line.startswith("!")]
    assert scl[0].strip() != ""                       # description line
    assert scl[1].strip() == str(NOTES_PER_OCTAVE)
    assert len(scl) == 2 + NOTES_PER_OCTAVE

    kbm = [line for line in render_kbm().splitlines() if not line.startswith("!")]
    assert kbm[0] == str(NOTES_PER_OCTAVE)            # map size
    assert kbm[1] == "0" and kbm[2] == "127"          # retune range
    assert kbm[3] == str(REFERENCE_KEY)               # middle note
    assert kbm[4] == str(REFERENCE_KEY)               # reference note
    assert abs(float(kbm[5]) - min(solfeggio_frequencies())) < 1e-6
    assert kbm[6] == str(NOTES_PER_OCTAVE)            # formal octave
    assert kbm[7:] == [str(degree) for degree in range(NOTES_PER_OCTAVE)]


def test_12tet_substitution_really_is_wrong():
    """Guards the claim in TUNING-TABLE.md: this is not a rounding quibble."""
    deviations = {source: abs(nearest_12tet(source)[1])
                  for _, _, source in true_pitch_keys()}
    assert max(deviations.values()) > 40.0, deviations
    assert sum(value > 40.0 for value in deviations.values()) >= 4, deviations
    assert abs(deviations[528.0] - 15.6) < 0.2      # the documented A444 case


def test_output_is_deterministic(tmp_path):
    first = {path.name: path.read_bytes() for path in write_all(tmp_path / "a")}
    second = {path.name: path.read_bytes() for path in write_all(tmp_path / "b")}
    assert first == second
    assert set(first) == {
        "hazama-solfeggio-9.scl", "hazama-solfeggio-9.kbm",
        "hazama-solfeggio-9.tun", "TUNING-TABLE.md",
    }


def test_folded_set_has_no_collisions():
    scale = build_scale()
    assert len(scale) == NOTES_PER_OCTAVE
    assert len({round(folded, 9) for folded, _ in scale}) == NOTES_PER_OCTAVE


if __name__ == "__main__":
    import tempfile

    failures = 0
    for name, function in sorted(globals().items()):
        if not name.startswith("test_") or not callable(function):
            continue
        try:
            if "tmp_path" in function.__code__.co_varnames[:function.__code__.co_argcount]:
                with tempfile.TemporaryDirectory() as directory:
                    function(Path(directory))
            else:
                function()
            print(f"ok   {name}")
        except AssertionError as error:
            failures += 1
            print(f"FAIL {name}: {error}")
    raise SystemExit(1 if failures else 0)
