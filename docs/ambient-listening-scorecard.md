# Ambient Listening Scorecard

## Purpose

This scorecard adapts drum-floor's human-gated evaluation habit for namima.

Namima should improve through listening notes, not through louder output, denser
interaction, or more impressive effects. The scorecard is metadata-only and does
not store audio, samples, lyrics, or copied motifs.

## Review axes

Score each axis from 1 to 5.

| Axis | Question | Good signal | Watch for |
| --- | --- | --- | --- |
| `family_safe` | Can this play around family without feeling risky? | soft level, no harsh surprise, no dark pressure | startling taps, edgy texture, aggressive bass |
| `daytime_fit` | Can this run during the day without pulling focus? | clear, light, comfortable | night-club mood, gloomy color, heavy pulse |
| `water_feel` | Does it feel like water surface motion? | shimmer, ripple, gentle continuity | metallic glitch, sharp clicking, dry machine feel |
| `garden_air` | Does it carry soft outdoor/room air? | breath, green calm, transparent space | stale drone, crowded pad, brittle high end |
| `background_comfort` | Can it stay on for a long time? | low fatigue, stable loudness, slow change | density creep, repeated motif, too much melody |
| `touch_response_softness` | Does touch feel like nudging water, not playing an instrument? | smooth ripple, small tone bias, soft return | pitch jumps, fast repeats, foreground lead behavior |
| `long_listening_stability` | Does it remain stable over time? | no console errors, no runaway motion, no stuck tone | audio stop, UI freeze, repeated warnings |

## Listening note template

```text
mood:
visual mode:
auto on/off:
duration:

family_safe:
daytime_fit:
water_feel:
garden_air:
background_comfort:
touch_response_softness:
long_listening_stability:

what worked:
what felt intrusive:
what to reduce next:
what to add gently next:
```

## Acceptance guidance

A runtime change is ready only if:

- `family_safe` and `background_comfort` stay high.
- `touch_response_softness` does not regress.
- `long_listening_stability` has no obvious failure.
- any new interesting behavior still supports water/garden/daytime listening.

A change should be revised or split if:

- it makes touch feel like performance control
- Auto increases loudness, low end, or density directly
- melody becomes a foreground hook for too long
- the visualizer becomes the main event instead of ambient support
- the safest mood, `family_room`, no longer feels safe

## Human-gated loop

1. Make a small PR.
2. Listen on local or Pages.
3. Fill this scorecard manually.
4. Convert notes into the next small PR.
5. Do not auto-promote listening notes into runtime changes.

## Storage boundary

Future recorder work may store scorecard metadata locally, but it must not store
or upload audio by default.

Allowed future data:

- mood
- visual mode
- Auto state
- rough touch energy
- listening duration
- score values
- reviewer notes

Disallowed future data:

- audio files
- samples
- waveform excerpts
- lyrics
- copied melodies or motifs
- external tracking without explicit approval
