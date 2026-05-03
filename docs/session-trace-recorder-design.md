# Session Trace Recorder Design

## Purpose

Namima's first recorder should record interaction traces, not audio.

The goal is to help future listening review remember how a session behaved while
preserving the no samples / no audio files policy. Trace data should support
human-gated review and small PR tuning, not automatic optimization.

## Non-goals

Do not record or store:

- audio files
- samples
- waveform excerpts
- microphone input
- lyrics
- copied motifs
- personal identifying data
- external analytics events by default

## Trace candidates

A future local trace may include:

- `session_id`
- `started_at`
- `duration_intent`
- `active_mood`
- `visual_mode`
- `auto_enabled`
- `touch_energy_band`
- `x_position_band`
- `gesture_rate_band`
- `mood_changes`
- `visual_changes`
- `listening_notes`

## Bands instead of raw detail

Store coarse bands rather than exact gesture streams.

| Raw concept | Stored band |
| --- | --- |
| touch intensity | `low`, `medium`, `high` |
| x position | `left_warm`, `center_stable`, `right_bright` |
| gesture rate | `still`, `slow`, `active`, `too_fast_clamped` |
| session duration | `short`, `medium`, `long` |

This keeps the recorder useful for tuning without turning namima into telemetry
or a performance capture tool.

## Local-first storage

The first implementation should use `localStorage` only.

Suggested key:

```text
namima:session-trace:v1
```

The value should be a small list of recent trace summaries. The runtime should
cap list size and fail silently if storage is unavailable.

## Review flow

1. Start namima.
2. Select Mood and Visual mode.
3. Listen normally.
4. Optionally add a listening note.
5. Save a local trace summary.
6. Use the trace with the ambient listening scorecard.
7. Convert the human review into a small PR.

## Safety behavior

The recorder must not change sound directly.

Allowed:

- remember the selected mood
- remember visual mode
- remember Auto on/off
- summarize touch energy bands
- keep local notes for human review

Disallowed:

- automatically tune mood profiles
- upload traces
- store raw pointer paths by default
- store exact timestamps for every touch
- store audio or microphone data
- use traces to increase loudness, low end, or density

## Future runtime boundary

A first recorder runtime PR should add only:

- local trace object construction
- small capped localStorage persistence
- copyable summary text if needed
- clear opt-in UI if notes are editable

Anything involving export, upload, sharing, or long-term analytics needs a
separate explicit design PR first.
