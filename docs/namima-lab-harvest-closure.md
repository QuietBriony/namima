# namima-lab harvest closure

## Purpose

`namima-lab` is now treated as an archive/reference line.

Active development continues in `QuietBriony/namima`, with namima kept as a
Public-Friendly Ambient Player for daytime, family-safe, water-like, garden-like,
soft continuous listening.

This document records which `namima-lab` ideas are harvested, which are rejected,
and where future runtime work should happen.

## Source status

| Source | Status | Decision |
| --- | --- | --- |
| A-min stable | Reference only | namima already carries the stable public-facing base direction. |
| v2 | Harvested safely | Safe ambient trail, velocity line, glow, air layer, and shimmer delay are adopted in namima. |
| v3 visuals | Candidate for visual-only harvest | Light-body motion, interference lines, and ring glow may become a calm second visual mode. |
| v3 audio | Rejected | BitCrusher, FMSynth, NoiseSynth, Tone.Transport, dark reactor behavior, and harsh glitch are out of scope. |
| v4 | No active harvest | No useful local implementation is currently identified for namima. |

## Adopted from v2

- Softer visual trail.
- Velocity-line motion instead of dense hard circles.
- Limited additive glow.
- Deeper but still calm space.
- Air/shimmer audio support without heavy low-end pressure.

These ideas are adopted only where they support namima's public-friendly ambient
direction.

## v3 visual-only candidate

v3 can contribute visual grammar, not its audio engine.

Allowed future harvest:

- Calm light bodies.
- Thin interference lines.
- Soft multi-ring glow.
- Slow orbit-like motion.
- Touch nudges that remain gentle.

Rejected future harvest:

- Bit-crushed texture.
- FM/metallic reactor behavior.
- Noise-based aggressive hits.
- Transport-driven dense repeats.
- Sudden pitch jumps.
- Dark glitch as the default character.

## Runtime boundary

Future runtime work should happen in namima, not in namima-lab.

Any import from namima-lab must be translated into namima's current structure.
Code should not be copied wholesale, and public-friendly safety takes priority
over feature parity.

## Closure rule

After this harvest record is merged, `namima-lab` can be closed as an
archive/reference source.

The remaining useful follow-up is a small namima PR that adds a calm v3-derived
visual mode while keeping audio, dependencies, samples, and workflows unchanged.

