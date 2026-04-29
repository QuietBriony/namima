# Ambient Interaction Contract

## Purpose

This document defines the interaction contract between `ripple interaction` and `mood profile` for Namima.

Namima is a **Public-Friendly Ambient Player**. Touch should feel like tracing a water surface, not performing an experimental instrument. Future runtime work should use this contract before adding interaction behavior.

This is not a runtime implementation. It is a docs-only boundary for future implementation.

## Inputs

Future runtime work may expose these interaction inputs:

- `touch_start`: first pointer/touch contact that creates a temporary ripple source
- `touch_hold`: continued contact or slow drag that sustains low interaction energy
- `touch_release`: end of contact, used to begin a soft fade back to the mood baseline
- `x_position`: normalized horizontal position, from left `0.0` to right `1.0`
- `ripple_energy`: normalized ripple intensity from touch force, repeated taps, or visual field response
- `gesture_rate`: how quickly repeated touches or drags arrive

These inputs should remain metadata-like control signals. They must not require audio files, samples, external dependencies, or copied `namima-lab` code.

## Internal Concepts

The interaction layer should translate inputs into ambient concepts, not directly into loudness or bass pressure.

- `water_shimmer`: fine surface movement, mostly affecting water-like texture
- `air_lift`: subtle brightness and openness in the air layer
- `soft_pulse_visibility`: how noticeable the gentle pulse is
- `melody_fragment_probability`: chance of short, sparse melodic fragments
- `fade_back_time`: time needed to return from touch response to the mood baseline

`ripple_energy` should primarily affect `water_shimmer`, `air_lift`, `soft_pulse_visibility`, and `melody_fragment_probability`. It should not directly increase master output or low-end weight.

## Fixed Mapping Rules

- Low `ripple_energy` should add small water movement and a little air.
- Medium `ripple_energy` may add a gentle pulse and rare melody fragments.
- High `ripple_energy` should be clamped into a safe response, not converted into harsh events.
- `gesture_rate` may shorten the perceived reaction, but must not create dense repeats.
- `touch_release` should always move toward a soft fade, never a hard cut.

`x_position` is a gentle tone selector:

- Left: lower and warmer tone tendency
- Center: stable and balanced tone tendency
- Right: slightly brighter tone tendency

The runtime must avoid sudden pitch jumps, octave jumps, or performance-like note runs even when touch input is fast.

## Mood Relationship

Each mood profile should bias the same interaction contract differently.

- `water_day`: prioritize `water_shimmer`, clear air, and light pulse; keep loudness conservative
- `garden_morning`: prioritize `air_lift`, soft organic movement, and slow fade-back
- `family_room`: keep all responses low-volume and background-safe
- `soft_sleep`: minimize `ripple_energy`, `x_position`, and pulse response; favor long fade-back
- `transparent_evening`: allow slightly cooler shimmer and clear air, but avoid sharp top-end events

Mood profiles remain the source of intent. Interaction input should bend the current mood, not replace it.

## Safety Ceilings

All future runtime work using this contract must preserve these ceilings:

- no harsh glitch
- no heavy low-end pressure
- no sudden pitch jumps
- no octave jumps
- no dense repeat bursts
- no hard cuts
- no dark or violent default aesthetic
- no samples
- no audio files
- no added dependencies for the interaction contract itself

If an interaction would exceed these ceilings, the runtime should clamp, smooth, or ignore that portion of the input.

## Future Runtime Boundary

Future implementation should treat this document as a contract between:

- visual/touch state
- mood profile state
- safe ambient audio parameters

The first runtime implementation should be small:

- read the active mood profile
- accept normalized interaction inputs
- compute safe ambient concept values
- smooth all output changes
- preserve limiter and family-safe defaults

Do not implement Music-style dark IDM, heavy bass, glitch fragments, or experimental pad operation as part of this contract.

## Validation Checklist

Before merging a future runtime PR based on this contract, confirm:

- `water_day` still feels like clear water motion
- `garden_morning` still feels soft and green
- `family_room` can stay in the background
- `soft_sleep` remains slow and quiet
- `transparent_evening` stays clear without sharpness
- fast touch does not cause harsh glitch, pitch jumps, octave jumps, or dense repeats
- no audio files, samples, dependencies, or workflow changes are introduced unless explicitly approved in a separate PR
