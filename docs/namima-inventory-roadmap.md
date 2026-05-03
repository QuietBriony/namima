# Namima inventory roadmap

## Purpose

Namima is the active Public-Friendly Ambient Player in the music stack.

This roadmap translates useful ideas from the local `github-inventory/music-stack`
repos into namima-safe growth work. It does not make namima a light version of
Music, and it does not reopen namima-lab as the active runtime.

## Repository roles

| Repository | Namima decision |
| --- | --- |
| `Music` | Adopt only reference-driven thinking, safe AutoMix ideas, and stability checklists. Do not import dark IDM, glitch density, heavy low end, or experimental pad operation. |
| `chill` | Adopt long-form listening, recipe thinking, deterministic preview mindset, and quiet recovery. Keep piano/lofi identity in chill instead of moving it into namima. |
| `drum-floor` | Adopt evaluation rubric, human-gated review, safety guard, and stable operation habits. Do not import groove generation or stage rig assumptions. |
| `namima-lab` | Treat as harvested archive/reference. v2 safe ambient interaction and v3 visual-only grammar have been moved into namima. |
| `test` | No active namima harvest for now. Keep as archive candidate unless a clear future purpose appears. |
| `namima` | Active public Pages runtime for water-like, garden-like, family-safe ambient listening. |

## Adopt into namima

- Start / Auto / Mood / Visual as the smallest public UI shape.
- Mood profiles as the source of ambient intent.
- Touch as gentle water-surface interaction, not performance control.
- Water / Orbit as visual modes that remain calm and background-safe.
- Reference intake as production translation only, never audio or sample storage.
- Listening review as human-gated notes before runtime tuning.
- Stability checks for start overlay, iOS-safe audio start, long listening, and console safety.

## Do not adopt

- Music's dark glitch or heavy bass direction.
- chill's piano/lofi recipe identity as namima's main sound.
- drum-floor's band groove generator or live stage workflow.
- namima-lab v3 audio reactor, BitCrusher, FMSynth, NoiseSynth, or Tone.Transport behavior.
- audio files, samples, lyrics, copied motifs, or dependency-heavy workflows.

## Near-term PR sequence

1. Safe Auto Mood design.
2. Ambient listening scorecard.
3. Start / Auto / Mood shell.
4. Mood profile runtime adapter.
5. Namima reference intake template.
6. Session trace recorder design.

## Runtime boundary

Runtime PRs should stay small and preserve public-friendly safety. If a feature
makes namima more impressive but less comfortable for daytime/family listening,
it belongs outside the default path.
