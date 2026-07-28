"""Solfeggio tuning tables for hardware/DAW instruments (Scala + AnaMark).

Why this exists
---------------
``solfeggio_composer`` synthesises everything from Python and uses the nine
solfeggio pitches as ABSOLUTE Hz — deliberately not snapped to 12-TET (the
89-cent 396↔417 step is the point). Every DAW instrument worth reaching for
— Kontakt, Reaktor, VCV, Sonar — is A440 / 12-TET by default. Loading a
Kontakt patch and playing "C" would silently replace the solfeggio truth with
523.251 Hz, so the timbre upgrade would cost the entire premise.

These tables are the bridge: retune the instrument once, then every key plays a
real solfeggio frequency to the last decimal.

The layout
----------
Nine notes per octave. Each solfeggio frequency is folded (halved) into the
octave starting at 174 Hz, then the folded set is sorted:

    key 60 = 174.000   (174)      key 65 = 240.750   (963 / 4)
    key 61 = 185.250   (741 / 4)  key 66 = 264.000   (528 / 2)
    key 62 = 198.000   (396 / 2)  key 67 = 285.000   (285)
    key 63 = 208.500   (417 / 2)  key 68 = 319.500   (639 / 2)
    key 64 = 213.000   (852 / 4)  key 69 = 348.000   (174 * 2)

so key n+9 is exactly twice key n, and every one of the nine is reachable at
its TRUE absolute Hz by choosing the octave (see ``true_pitch_keys()``).

A flat "nine solfeggio on nine consecutive keys" map was rejected: 396 > 174*2,
so that layout is not monotonic in pitch and cannot be expressed as a Scala
scale at all — only as a raw 128-key table.

444 / 888 / 8888 Hz are documented accents, NOT solfeggio, and are deliberately
absent from the scale. The composer synthesises them at fixed pitch; do the
same in the DAW (a separate fixed-tuned layer), do not bend the scale to fit.

Frequencies come from ``presets.yaml`` via ``preset_frequency`` — never re-typed.

    python -m namima.tuning --out exports/tuning
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from .generator import load_presets, preset_frequency

__version__ = "0.1.0"

SOLFEGGIO = (174, 285, 396, 417, 528, 639, 741, 852, 963)
NOTES_PER_OCTAVE = len(SOLFEGGIO)
REFERENCE_KEY = 60          # MIDI note that sounds the scale's 1/1
MIDI_0_HZ = 8.1757989156    # AnaMark .tun cents are measured from here
TWELVE_TET_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def solfeggio_frequencies(presets: dict | None = None) -> tuple[float, ...]:
    """The nine absolute Hz, from presets.yaml (single source of truth)."""
    p = presets or load_presets()
    return tuple(preset_frequency(f"solfeggio_{n}", p) for n in SOLFEGGIO)


def fold_to_octave(frequency: float, base: float) -> float:
    """Halve/double ``frequency`` until it lands in [base, base * 2)."""
    folded = float(frequency)
    while folded >= base * 2.0:
        folded /= 2.0
    while folded < base:
        folded *= 2.0
    return folded


def build_scale(presets: dict | None = None) -> list[tuple[float, float]]:
    """Sorted [(folded_hz, source_hz), ...] — the nine scale degrees."""
    frequencies = solfeggio_frequencies(presets)
    base = min(frequencies)
    folded = [(fold_to_octave(f, base), f) for f in frequencies]
    folded.sort(key=lambda pair: pair[0])
    if len({round(pair[0], 9) for pair in folded}) != NOTES_PER_OCTAVE:
        raise ValueError(f"folded solfeggio set collided: {folded!r}")
    return folded


def scale_cents(presets: dict | None = None) -> list[float]:
    """Scala degrees 1..N in cents; the last entry is the 2/1 period."""
    scale = build_scale(presets)
    base = scale[0][0]
    cents = [1200.0 * math.log2(folded / base) for folded, _ in scale[1:]]
    return cents + [1200.0]


def midi_frequency(key: int, presets: dict | None = None) -> float:
    """Absolute Hz for a MIDI key under this mapping."""
    scale = build_scale(presets)
    base = scale[0][0]
    offset = key - REFERENCE_KEY
    octave, degree = divmod(offset, NOTES_PER_OCTAVE)
    return scale[degree][0] * (2.0 ** octave) * (base / scale[0][0])


def true_pitch_keys(presets: dict | None = None) -> list[tuple[int, float, float]]:
    """[(midi_key, sounded_hz, solfeggio_hz), ...] for all nine, exact."""
    scale = build_scale(presets)
    rows = []
    for degree, (folded, source) in enumerate(scale):
        octaves = round(math.log2(source / folded))
        key = REFERENCE_KEY + degree + octaves * NOTES_PER_OCTAVE
        rows.append((key, midi_frequency(key, presets), source))
    rows.sort()
    return rows


def nearest_12tet(frequency: float, tuning: float = 440.0) -> tuple[str, float]:
    """(note name with octave, cents deviation) against A4 = ``tuning``."""
    semitones = 12.0 * math.log2(frequency / tuning) + 69.0
    nearest = round(semitones)
    name = f"{TWELVE_TET_NAMES[nearest % 12]}{nearest // 12 - 1}"
    return name, (semitones - nearest) * 100.0


# ---------------------------------------------------------------- file writers
def render_scl(presets: dict | None = None) -> str:
    cents = scale_cents(presets)
    scale = build_scale(presets)
    lines = [
        "! hazama-solfeggio-9.scl",
        "!",
        "hazama solfeggio 9-per-octave (absolute Hz, non-12-TET)",
        f" {NOTES_PER_OCTAVE}",
        "!",
    ]
    for index, value in enumerate(cents):
        source = scale[index + 1][1] if index + 1 < len(scale) else scale[0][1] * 2
        lines.append(f" {value:.6f}  ! {source:g} Hz folded")
    return "\n".join(lines) + "\n"


def render_kbm(presets: dict | None = None) -> str:
    base = build_scale(presets)[0][0]
    lines = [
        "! hazama-solfeggio-9.kbm",
        "! Size of map",
        f"{NOTES_PER_OCTAVE}",
        "! First / last MIDI note to retune",
        "0",
        "127",
        "! Middle note (scale degree 0 lands here)",
        f"{REFERENCE_KEY}",
        "! Reference note and its frequency",
        f"{REFERENCE_KEY}",
        f"{base:.6f}",
        "! Scale degree that formally equals an octave",
        f"{NOTES_PER_OCTAVE}",
        "! Mapping",
    ]
    lines += [str(degree) for degree in range(NOTES_PER_OCTAVE)]
    return "\n".join(lines) + "\n"


def render_tun(presets: dict | None = None) -> str:
    """AnaMark TUN v2 — 128 explicit keys. Kontakt and Sonar read this."""
    lines = [
        "; hazama-solfeggio-9.tun",
        "; nine solfeggio frequencies as absolute Hz, nine notes per octave.",
        f"; key {REFERENCE_KEY} = {build_scale(presets)[0][0]:.6f} Hz",
        "",
        "[Tuning]",
    ]
    for key in range(128):
        frequency = midi_frequency(key, presets)
        cents = 1200.0 * math.log2(frequency / MIDI_0_HZ)
        # 8 dp, not the usual 6: a .tun stores cents, so absolute error grows
        # with pitch, and the whole premise here is exact absolute Hz.
        lines.append(f"note {key}={cents:.8f}")
    return "\n".join(lines) + "\n"


def render_report(presets: dict | None = None) -> str:
    """Markdown: which key plays which solfeggio, and the 12-TET damage."""
    rows = true_pitch_keys(presets)
    out = [
        "# ソルフェジオ・チューニング表",
        "",
        "`namima.tuning` が生成。数値の正本は `presets.yaml`。",
        "",
        "## 真値が鳴るキー",
        "",
        "| MIDI | 鳴る Hz | ソルフェジオ | A440/12平均律の最寄り | ずれ |",
        "|---:|---:|---:|:--|---:|",
    ]
    for key, sounded, source in rows:
        name, cents = nearest_12tet(source)
        out.append(
            f"| {key} | {sounded:.3f} | {source:g} Hz | {name} | {cents:+.1f} cent |"
        )
    out += [
        "",
        "## なぜ 12平均律で代用できないか",
        "",
        "上の「ずれ」列がそのまま代用したときの誤差。**最大でおよそ半音の 4 割**"
        "ずれる。528 だけは A4=444 にすれば C5 に一致する(+15.6 cent は A440 比)"
        "が、9 つを 1 つの調律で揃えることはできない。だからスケールごと差し替える。",
        "",
        "## 使い方",
        "",
        "| 音源 | 読ませるファイル | 場所 |",
        "|:--|:--|:--|",
        "| Kontakt 6/7 | `.tun` | インストゥルメント → Tuning → Load |",
        "| Reaktor 6 | `.tun` | Master tuning table |",
        "| VCV Rack / Surge | `.scl` + `.kbm` | Scala tuning を読み込み |",
        "| Sonar / 一般 VSTi | `.tun` | 対応プラグインの microtuning スロット |",
        "",
        "`.kbm` は `.scl` と**必ず対で**読ませること。`.scl` 単体だと 1 オクターブ"
        "12 鍵に詰められ、基準 Hz も A440 のままになる。",
        "",
        "## 444 / 888 / 8888 Hz",
        "",
        "これらは**ソルフェジオではない**(ベル・スパークルの装飾)。スケールには"
        "入れていない。DAW でも固定ピッチの別レイヤーとして鳴らすこと — "
        "スケールを曲げて合わせない。",
    ]
    return "\n".join(out) + "\n"


def write_all(out_dir: Path, presets: dict | None = None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in (
        ("hazama-solfeggio-9.scl", render_scl(presets)),
        ("hazama-solfeggio-9.kbm", render_kbm(presets)),
        ("hazama-solfeggio-9.tun", render_tun(presets)),
        ("TUNING-TABLE.md", render_report(presets)),
    ):
        path = out_dir / name
        path.write_text(text, encoding="utf-8", newline="\n")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="exports/tuning", help="output directory")
    args = parser.parse_args(argv)
    for path in write_all(Path(args.out)):
        print(f"wrote {path}")
    for key, sounded, source in true_pitch_keys():
        print(f"  MIDI {key:3d} -> {sounded:9.3f} Hz  (solfeggio {source:g})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
