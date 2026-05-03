# Namima Reference Intake Template

## Purpose

Namima can use reference-driven research only as safe production translation.

A reference is not a source to copy. It is a listening prompt for describing
public-friendly ambient qualities that may become mood or parameter ideas.

## Save only metadata

Allowed fields:

- `reference_label`
- `listening_context`
- `taste_notes`
- `production_translation`
- `mood_candidate`
- `avoid_notes`
- `implementation_hint`
- `review_status`

Do not save:

- audio files
- samples
- stems
- preview URLs
- lyrics
- copied melodies
- copied chord progressions
- copied rhythmic motifs
- screenshots of proprietary players

## Template

```json
{
  "reference_label": "short human label",
  "listening_context": "daytime / family room / garden / water / sleep / evening",
  "taste_notes": [
    "what the reference makes clear as a feeling"
  ],
  "production_translation": {
    "foreground_vs_bed": "bed",
    "pulse_visibility": "low",
    "particle_material": "water / air / soft grain",
    "low_mid_behavior": "light and controlled",
    "tail_behavior": "slow fade, no hard cut",
    "gesture_role": "touch gently bends the mood"
  },
  "mood_candidate": "water_day",
  "avoid_notes": [
    "no heavy low end",
    "no harsh glitch",
    "no recognizable motif"
  ],
  "implementation_hint": "optional safe runtime idea, not copied material",
  "review_status": "candidate"
}
```

## Translation axes

| Axis | Namima-safe question |
| --- | --- |
| `foreground_vs_bed` | Should this stay background-safe or briefly foreground? |
| `pulse_visibility` | Is pulse nearly hidden, soft, or lightly visible? |
| `particle_material` | Does the texture feel like water, air, garden, glass, or dust? |
| `low_mid_behavior` | Does the body stay warm without pressure? |
| `tail_behavior` | How does sound fade back into the room? |
| `gesture_role` | Does touch nudge, brighten, shimmer, or briefly answer? |

## Mood mapping

- `water_day`: clear water motion, shimmer, gentle pulse.
- `garden_morning`: air, softness, organic movement.
- `family_room`: warm low-volume background safety.
- `soft_sleep`: minimum pulse, low brightness, long fade.
- `transparent_evening`: cooler clear space and reflective air.

## Review rule

A reference can influence namima only after it is translated into safe parameters
and checked against the ambient listening scorecard.

If the strongest idea requires dark glitch, heavy bass, dense repeats, copied
motif, or audio/sample storage, it does not belong in namima's default path.
