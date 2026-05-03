# Safe Auto Mood Design

## Purpose

Auto in namima is not composition, generation density, or performance mode.

Auto is a slow public-friendly drift between safe ambient moods so the player can
stay on in a family room, daytime workspace, garden-like room, or quiet evening
without demanding attention.

## Default route

The default Auto route is:

```text
water_day -> garden_morning -> family_room -> transparent_evening
```

Each step should last roughly 3 to 8 minutes. The runtime may add small timing
variation, but it should not jump rapidly or create a foreground performance.

`soft_sleep` is not part of the default Auto route. It should be entered deeply
only when the listener explicitly chooses it.

## Mood behavior

| Mood | Auto role |
| --- | --- |
| `water_day` | Clear water motion, gentle shimmer, light pulse. Good starting point. |
| `garden_morning` | Soft air, green calm, subtle organic movement. |
| `family_room` | Lowest-risk background state, warm and safe at low volume. |
| `transparent_evening` | Clearer and slightly cooler, but not sharp or dark. |
| `soft_sleep` | Explicit quiet mode with minimum response and long fades. |

## Mapping rules

Auto may slowly bias:

- pad openness
- water shimmer
- air layer brightness
- soft pulse visibility
- melody fragment probability
- room space
- visual trail softness

Auto must not directly boost:

- master gain
- low-end pressure
- rhythm density
- gesture repeat rate
- pitch range
- visual intensity beyond the current public-friendly ceiling

## Visual relationship

Visual mode may follow mood softly, but Auto must not switch visual mode in a
surprising way.

Allowed behavior:

- `water_day` can make Water feel clearer.
- `garden_morning` can make Water or Orbit feel softer and greener.
- `family_room` can reduce contrast and keep movement low.
- `transparent_evening` can make Orbit slightly cooler and more spacious.
- `soft_sleep` can dim both modes.

Disallowed behavior:

- sudden Water / Orbit switching without user intent
- flashing, strobing, or dense visual bursts
- dark reactor behavior
- aggressive particle acceleration

## Touch relationship

Touch remains a gentle surface disturbance while Auto is on.

- Repeated touch may add shimmer and air, but not dense repeats.
- `x_position` may bias tone warmth/brightness, but not jump octaves.
- High gesture rate should clamp into safe response.
- Release should always fade back toward the current Auto mood.

## Safety ceilings

Auto must preserve:

- no harsh glitch
- no heavy low-end pressure
- no sudden pitch jumps
- no octave jumps
- no dense repeat bursts
- no hard cuts
- no dark or violent default aesthetic
- no samples
- no audio files
- no added dependencies

## First runtime target

The first Auto implementation should be intentionally modest:

- expose an `Auto` toggle
- keep the active mood visible
- drift between the default route slowly
- smooth every parameter change
- fall back to `water_day` if profile loading fails
- keep `soft_sleep` manual-only
