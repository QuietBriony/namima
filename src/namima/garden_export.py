"""Export the music-to-garden contract JSON for a hazama dream-garden render.

Why this exists
---------------
`hazama-studio/docs/MUSIC-GARDEN-INPUT.md` designed the contract and then said
"the future exporter will satisfy the following". This is that exporter. Until
it existed, the garden animation had to guess where the music changed; with it,
the sky can turn on the frame the harmonic scene actually turns.

Everything here is DERIVED, not invented:

* `duration_seconds` and `sections` come from ``DRIFT_CHARACTER`` and
  ``solfeggio_composer.block_ranges`` - the same numbers the renderer used.
* `tension_curve` is the pitch span of each harmonic block (how many octaves
  separate its lowest and highest voice). For 174 through 639 this arches on
  block 3, because block 3 is where ``drift_blocks_for`` adds the triad's top
  partial. For 741, 852 and 963 it does NOT arch: their melody pool already
  reaches 963 Hz - the ceiling of the solfeggio set - in every block, so the
  added partial changes nothing and the span is decided entirely by the
  alternating bass. The curve therefore alternates rather than arches there.
  That is a fact about the music, not a defect in the export; if those three
  want an arch, the fix belongs in ``drift_blocks_for``, not here.
* `energy_curve` is the RMS envelope of the rendered WAV when one is supplied.
  Without a WAV it falls back to the section structure and says so in the
  track id, because a guessed envelope must not be mistaken for a measured one.
* `garden_motif` and `palette_hint` come from the nine gardens documented in
  `hazama-studio/docs/UNIVERSE.md`. The hex values are a starting point derived
  from each garden's documented hour; the renderer is free to override them.

The contract's own rules (ordering, no overlapping sections, curve endpoints,
same track+version giving the same values) are enforced in ``validate`` rather
than trusted, and the tests hold them.

`frequency_hz` is a creative reference only. No feature here carries a medical
meaning - that is a contract rule, not a disclaimer.

    python -m namima.garden_export 174 --audio drift.wav --out garden-174.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from . import solfeggio_composer as sc
from .generator import load_presets, preset_frequency
from .hazama_release import DRIFT_CHARACTER, drift_blocks_for

__version__ = "1.0.0"
CONTRACT_VERSION = "1.0"

# The nine gardens, from hazama-studio/docs/UNIVERSE.md. Colours are seeded from
# each garden's documented hour; they are a hint, not a lock.
GARDENS = {
    174: dict(motif="deep_moss_garden", hour="before dawn, fog",
              tags=["moss", "boulders", "after-rain", "fog", "pre-dawn"],
              colors=["#12182B", "#2A3348", "#4C5A4A", "#C46A3A"]),
    285: dict(motif="karesansui_ripples", hour="early morning, raking light",
              tags=["raked-sand", "concentric-ripples", "low-sun"],
              colors=["#1B2338", "#6B6350", "#C8B996", "#E0A45C"]),
    396: dict(motif="bamboo_garden", hour="morning",
              tags=["bamboo", "columns", "wind-path"],
              colors=["#22301F", "#4E6B3A", "#8FA86B", "#D8DCC0"]),
    417: dict(motif="water_garden", hour="late morning",
              tags=["yarimizu", "stepping-stones", "flowing-water"],
              colors=["#1D3340", "#3E6B78", "#84A9A5", "#D6E2DC"]),
    528: dict(motif="new_green_garden", hour="midday, dappled light",
              tags=["moss-mounds", "new-shoots", "dappled-light"],
              colors=["#243A20", "#4F7A32", "#8FBF5A", "#E3EBC8"]),
    639: dict(motif="roji_tea_garden", hour="evening",
              tags=["tsukubai", "lantern", "waiting-bench", "between-people"],
              colors=["#2A2418", "#5A4326", "#A8763C", "#E0B072"]),
    741: dict(motif="stone_garden", hour="sunset",
              tags=["standing-stones", "long-shadows"],
              colors=["#331F1C", "#6B3A2E", "#B4643C", "#E8A46A"]),
    852: dict(motif="garden_above_clouds", hour="dusk",
              tags=["clipped-clouds", "haze-islands"],
              colors=["#241D3A", "#4A4370", "#8A86A8", "#D8CFE0"]),
    963: dict(motif="garden_of_light", hour="night, full moon",
              tags=["white-sand", "moonlight", "geometric-sky"],
              colors=["#0E1224", "#2C3660", "#8894C0", "#EDEFF8"]),
}

SECTION_IDS = ("settle", "drift", "open", "return")


def _config_for(frequency: int):
    character = dict(DRIFT_CHARACTER[frequency])
    return sc.ComposeConfig(seed=200000 + frequency, **character)


def _block_span_octaves(block) -> float:
    """How far the block's highest voice sits above its lowest, in octaves."""
    pitches = [block["bass"], *block["pad"], *block["mel"], *block["voice"]]
    pitches = [p for p in pitches if p > 0]
    return math.log2(max(pitches) / min(pitches))


def sections_for(frequency: int):
    cfg = _config_for(frequency)
    ranges = sc.block_ranges(cfg)
    return [
        {
            "id": SECTION_IDS[index],
            "start_seconds": round(start * cfg.bar, 6),
            "end_seconds": round(end * cfg.bar, 6),
        }
        for index, (start, end) in enumerate(ranges)
    ]


def tension_curve_for(frequency: int, presets=None):
    """One point per section boundary; value = normalised pitch span."""
    cfg = _config_for(frequency)
    blocks = drift_blocks_for(frequency, presets or load_presets())
    spans = [_block_span_octaves(block) for block in blocks]
    low, high = min(spans), max(spans)
    spread = high - low
    normalised = [0.5 if spread <= 1e-9 else (s - low) / spread for s in spans]

    sections = sections_for(frequency)
    points = [{"time_seconds": 0.0, "value": round(normalised[0], 4)}]
    for index, section in enumerate(sections):
        points.append({
            "time_seconds": round(section["start_seconds"], 6),
            "value": round(normalised[index], 4),
        })
    points.append({
        "time_seconds": round(sections[-1]["end_seconds"], 6),
        "value": round(normalised[-1], 4),
    })
    # A section boundary and t=0 can coincide; keep the first of any tie so the
    # curve stays strictly non-decreasing in time.
    deduped = []
    for point in points:
        if deduped and point["time_seconds"] <= deduped[-1]["time_seconds"]:
            continue
        deduped.append(point)
    return deduped


def energy_curve_from_audio(samples, sample_rate, duration_seconds, points=48):
    """RMS envelope of a render, normalised to its own peak."""
    mono = samples.mean(axis=1) if samples.ndim > 1 else samples
    window = max(int(len(mono) / points), 1)
    usable = len(mono) // window * window
    frames = mono[:usable].reshape(-1, window)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    peak = rms.max()
    values = rms / peak if peak > 0 else rms
    times = np.arange(len(values)) * window / sample_rate
    curve = [{"time_seconds": round(float(t), 6), "value": round(float(v), 4)}
             for t, v in zip(times, values) if t <= duration_seconds]
    if curve[0]["time_seconds"] > 0.0:
        curve.insert(0, {"time_seconds": 0.0, "value": curve[0]["value"]})
    if curve[-1]["time_seconds"] < duration_seconds:
        curve.append({"time_seconds": round(duration_seconds, 6),
                      "value": curve[-1]["value"]})
    return curve


def energy_curve_from_structure(frequency: int):
    """Fallback shape when no render is supplied: sections only, no measurement."""
    sections = sections_for(frequency)
    shape = (0.30, 0.62, 0.85, 0.45)
    curve = [{"time_seconds": 0.0, "value": shape[0]}]
    for index, section in enumerate(sections):
        midpoint = (section["start_seconds"] + section["end_seconds"]) / 2.0
        curve.append({"time_seconds": round(midpoint, 6), "value": shape[index]})
    curve.append({"time_seconds": round(sections[-1]["end_seconds"], 6),
                  "value": 0.18})
    return curve


def camera_hint_for(frequency: int):
    """Derived from the track's own character, not chosen by hand.

    ``space`` is the reverb depth and ``swell`` the length of each melodic
    breath, so a long-tailed, slow-breathing track wants a stiller camera.
    """
    character = DRIFT_CHARACTER[frequency]
    mode = {"none": "drift", "heartbeat": "push_in", "deep": "orbit"}[
        character["beat_mode"]]
    spaces = [c["space"] for c in DRIFT_CHARACTER.values()]
    lo, hi = min(spaces), max(spaces)
    stillness = (character["space"] - lo) / (hi - lo) if hi > lo else 0.5
    amount = round(0.05 + 0.30 * (1.0 - stillness), 3)
    if character["beat_mode"] == "none" and stillness > 0.85:
        mode = "static"
    return {"mode": mode, "amount": amount}


def build(frequency: int, audio=None, sample_rate=None, presets=None,
          track_id=None):
    if frequency not in DRIFT_CHARACTER:
        raise KeyError(f"no drift character for {frequency} Hz")
    presets = presets or load_presets()
    cfg = _config_for(frequency)
    duration = cfg.bars * cfg.bar
    garden = GARDENS[frequency]
    measured = audio is not None

    if track_id is None:
        track_id = f"hazama-{frequency}-drift" if measured \
            else f"hazama-{frequency}-drift-unmeasured"

    document = {
        "contract_version": CONTRACT_VERSION,
        "source_track_id": track_id,
        "frequency_hz": preset_frequency(f"solfeggio_{frequency}", presets),
        "deterministic_seed": cfg.seed,
        "duration_seconds": round(duration, 6),
        "sections": sections_for(frequency),
        "energy_curve": (energy_curve_from_audio(audio, sample_rate, duration)
                         if measured else energy_curve_from_structure(frequency)),
        "tension_curve": tension_curve_for(frequency, presets),
        "palette_hint": {
            "colors_srgb": list(garden["colors"]),
            "mood_tags": [garden["hour"]] + garden["tags"][:2],
        },
        "camera_motion_hint": camera_hint_for(frequency),
        "garden_motif": {"id": garden["motif"], "tags": list(garden["tags"])},
    }
    validate(document)
    return document


def validate(document):
    """The contract's rules that JSON Schema cannot express.

    Schema catches types and ranges. It cannot say "sections must be in order
    and must not overlap" or "the curve must start at zero and end no later
    than the track", and those are exactly the mistakes an exporter makes.
    """
    errors = []
    duration = document["duration_seconds"]

    previous_end = None
    for section in document["sections"]:
        if section["end_seconds"] <= section["start_seconds"]:
            errors.append(f"section {section['id']}: end is not after start")
        if previous_end is not None and section["start_seconds"] < previous_end - 1e-6:
            errors.append(f"section {section['id']}: overlaps the previous one")
        previous_end = section["end_seconds"]
    if previous_end is not None and previous_end > duration + 1e-6:
        errors.append("last section ends after duration_seconds")

    for name in ("energy_curve", "tension_curve"):
        curve = document[name]
        if len(curve) < 2:
            errors.append(f"{name}: needs at least two points")
            continue
        if abs(curve[0]["time_seconds"]) > 1e-9:
            errors.append(f"{name}: must start at 0 seconds")
        if curve[-1]["time_seconds"] > duration + 1e-6:
            errors.append(f"{name}: ends after duration_seconds")
        times = [point["time_seconds"] for point in curve]
        if times != sorted(times) or len(set(times)) != len(times):
            errors.append(f"{name}: times must strictly ascend")
        if any(not 0.0 <= point["value"] <= 1.0 for point in curve):
            errors.append(f"{name}: values must sit in 0..1")

    if errors:
        raise ValueError("GARDEN_EXPORT_INVALID: " + "; ".join(errors))
    return document


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("frequency", type=int, choices=sorted(DRIFT_CHARACTER))
    parser.add_argument("--audio", default=None,
                        help="rendered WAV; without it the energy curve is a guess")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    audio = sample_rate = None
    if args.audio:
        from scipy.io import wavfile
        sample_rate, data = wavfile.read(args.audio)
        audio = data.astype(np.float64)
        if np.issubdtype(data.dtype, np.integer):
            audio /= float(np.iinfo(data.dtype).max)

    document = build(args.frequency, audio=audio, sample_rate=sample_rate)
    text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
    else:
        print(text, end="")
    sections = document["sections"]
    print(f"  {document['duration_seconds']:.1f} s, {len(sections)} sections, "
          f"energy {'measured' if args.audio else 'GUESSED (no --audio)'}")
    for section in sections:
        print(f"    {section['id']:<8} {section['start_seconds']:8.2f} -> "
              f"{section['end_seconds']:8.2f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
