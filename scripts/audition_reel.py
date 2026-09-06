"""Build a phone-friendly audition reel from delivery packets (any PC, CPU-only).

    python scripts/audition_reel.py --plan deliveries/<plan>.json [--handoff-dir ...]

The plan lists excerpts (packet-relative file, start, duration, label, what to
listen for). Each excerpt gets 0.3 s fade-in / 0.4 s fade-out and a silent gap,
everything is concatenated with ffmpeg (resolved like namima.deliver) into one
AAC m4a, and a cue sheet (cumulative timestamps -> packet -> checkpoint) is
written next to it. Output lands in `<handoff dir>/deliveries/<plan.out_dir>/`
so it shows up in the catalogue like any other packet.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from namima.deliver import resolve_handoff_dir, find_ffmpeg, sha256  # noqa: E402


def mmss(sec: float) -> str:
    s = int(round(sec))
    return f"{s // 60}:{s % 60:02d}"


def build(plan: dict, deliveries: Path, ff: str) -> tuple[Path, Path]:
    gap = float(plan.get("gap_s", 1.5))
    out_dir = deliveries / plan["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    inputs, filters, labels, cues = [], [], [], []
    t = 0.0
    for i, ex in enumerate(plan["excerpts"]):
        src = deliveries / ex["file"]
        if not src.exists():
            raise FileNotFoundError(src)
        dur = float(ex["dur"])
        inputs += ["-i", str(src)]
        filters.append(
            f"[{i}:a]atrim=start={float(ex['start'])}:duration={dur},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d=0.3,afade=t=out:st={max(dur - 0.4, 0):.2f}:d=0.4,"
            f"aformat=sample_rates=48000:channel_layouts=stereo,apad=pad_dur={gap}[a{i}]")
        labels.append(f"[a{i}]")
        cues.append((t, ex))
        t += dur + gap
    total = t - gap
    fc = ";".join(filters) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=0:a=1[out]"
    base = f"{plan['name']}-{mmss(total).replace(':', 'm')}s"
    m4a = out_dir / f"{base}-iphone.m4a"
    subprocess.run([ff, "-y", "-loglevel", "error", *inputs, "-filter_complex", fc, "-map", "[out]",
                    "-codec:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(m4a)], check=True)
    lines = [f"# {plan.get('title', plan['name'])} — cue sheet", "",
             f"- 総尺 {mmss(total)}・{len(cues)} 抜粋・各抜粋の後に {gap:g} 秒の無音",
             f"- `{m4a.name}`  SHA-256: `{sha256(m4a)}`",
             "- 判定は packet 名で: `python scripts/catalog_deliveries.py --set-verdict <packet> \"…\"`", "",
             "| 開始 | packet | 抜粋 | 聴きどころ |", "|---|---|---|---|"]
    for t0, ex in cues:
        pk = ex["file"].split("/")[0]
        lines.append(f"| **{mmss(t0)}** | `{pk}` | {ex['label']}（元 {mmss(float(ex['start']))}〜 {int(float(ex['dur']))}s） | {ex.get('listen', '')} |")
    lines.append("")
    cue = out_dir / f"{base}-cuesheet.md"
    cue.write_text("\n".join(lines), encoding="utf-8")
    return m4a, cue


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="plan json (absolute, or relative to the hand-off dir)")
    ap.add_argument("--handoff-dir", default=None)
    a = ap.parse_args(argv)
    hd, src = resolve_handoff_dir(a.handoff_dir)
    ff, ff_src = find_ffmpeg()
    if not ff:
        print("ffmpeg not found (PATH / imageio-ffmpeg) — cannot build a reel")
        return 1
    plan_path = Path(a.plan)
    if not plan_path.is_absolute():
        plan_path = hd / plan_path
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    m4a, cue = build(plan, hd / "deliveries", ff)
    print(f"reel -> {m4a}\ncue  -> {cue}\n(ffmpeg via {ff_src}; hand-off dir via {src})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
