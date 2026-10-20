"""Audition reel: 25 s excerpts (from 30 s into each 90 s clip) with 1 s gaps, AAC m4a + cue sheet.

    python scripts/texture_lane/make_reel.py <out.m4a> "<label>=<clip.wav>" ["<label>=<clip.wav>" ...]

ffmpeg is resolved like namima.deliver (NAMIMA_FFMPEG -> PATH -> imageio-ffmpeg).
The cue sheet is written next to the reel as <out>.cue.txt (m:ss  label).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))   # repo/src (namima)

from namima.deliver import find_ffmpeg  # noqa: E402

EXC, GAP, START = 25.0, 1.0, 30.0


def build(out: Path, items, ff: str) -> list[str]:
    inputs, chain, cue, t = [], [], [], 0.0
    for i, (label, path) in enumerate(items):
        inputs += ["-ss", str(START), "-t", str(EXC), "-i", path]
        chain.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,afade=t=in:d=0.3,afade=t=out:st={EXC-0.3}:d=0.3[a{i}]")
        # one silent source per gap: a filtergraph label can feed only one input. The first version
        # reused a single [g], and ffmpeg bound every later [g] to input 0 - a 25 s repeat of the first
        # excerpt instead of 1 s of silence - so the cue sheet drifted from the 3rd entry on.
        chain.append(f"anullsrc=r=48000:cl=stereo,atrim=end={GAP:g}[g{i}]")
        cue.append(f"{int(t//60)}:{int(t%60):02d}  {label}")
        t += EXC + GAP
    concat = "".join(f"[a{i}][g{i}]" for i in range(len(items))) + f"concat=n={2*len(items)}:v=0:a=1[out]"
    filt = ";".join(chain + [concat])
    cmd = [ff, "-y", "-loglevel", "error", *inputs, "-filter_complex", filt, "-map", "[out]",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    # ffmpeg writes UTF-8; the locale codec (cp932 on a Japanese Windows) would crash on a non-ASCII path
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        print(r.stderr[-800:])
        raise SystemExit(1)
    out.with_suffix(".cue.txt").write_text("\n".join(cue) + "\n", encoding="utf-8")
    return cue


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="audition reel of 25 s excerpts + cue sheet")
    ap.add_argument("out", help="reel path (.m4a)")
    ap.add_argument("items", nargs="+", metavar="LABEL=CLIP", help="label and 90 s clip wav, joined by '='")
    a = ap.parse_args(argv)
    items = [s.split("=", 1) for s in a.items]
    bad = [s for s, it in zip(a.items, items) if len(it) != 2]
    if bad:
        ap.error(f"expected LABEL=CLIP, got {bad}")
    ff, _ = find_ffmpeg()
    if not ff:
        print("ffmpeg not found (NAMIMA_FFMPEG / PATH / imageio-ffmpeg) - cannot build a reel")
        return 1
    out = Path(a.out)
    cue = build(out, items, ff)
    print("wrote", out, f"({out.stat().st_size//1024} KB)")
    print("\n".join(cue))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
