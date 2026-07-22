"""namima offline ambient renderer (candidate).

A dependency-light (numpy + scipy) offline renderer for frequency-based ambient
drones — 128 Hz / solfeggio / binaural — as deterministic 48 kHz / 24-bit WAV.

Spec + single source of truth: ../../SKILL.md and ../../presets.yaml.
This is a *candidate* subsystem: nothing here is wired into the namima runtime
(sketch.js / audio.js) and no generated audio is committed to the repo.
"""

from .generator import (
    render,
    write_wav24,
    load_presets,
    note_to_freq,
    preset_frequency,
    add_reference_layer,
    RenderConfig,
    __version__,
)
from .solfeggio_composer import compose, ComposeConfig, build_blocks

__all__ = [
    "render",
    "write_wav24",
    "load_presets",
    "note_to_freq",
    "preset_frequency",
    "add_reference_layer",
    "RenderConfig",
    "compose",
    "ComposeConfig",
    "build_blocks",
    "__version__",
]
