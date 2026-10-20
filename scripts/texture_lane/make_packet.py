"""Wave-2 packet writer: lane-convention packet (master 48k/24 + iphone m4a + handoff.md) for a bedded track.

    python scripts/texture_lane/make_packet.py <bedded-48k24.wav> <packet-dir-name> <base> <handoff-notes.md>
        [--out <dir>] [--deliver] [--handoff-dir <dir>]

- master: copies the 48 kHz/24-bit wav as <base>-master.wav
- iphone: AAC-LC 192k fast-start via namima.deliver.encode (ffmpeg via namima.deliver.find_ffmpeg)
- handoff: SHA-256 of both + the notes file (recipe/measurements/verdict written by the caller)
- the packet is assembled in <out>/<packet-dir-name>/ (default <out> = <wav folder>/packet)
- --deliver copies the three files to the Drive lane deliveries/<packet-dir-name>/ (new folder only).
  Hand-off dir: --handoff-dir -> NAMIMA_HANDOFF_DIR -> Google Drive (AI連携/Music); refuses to fall
  back to ./deliveries so nothing lands in the repo.
"""
from __future__ import annotations

import argparse
import platform
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))   # repo/src (namima)

from namima.deliver import find_ffmpeg, resolve_handoff_dir, sha256, encode  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="lane-convention hand-off packet for a bedded track")
    ap.add_argument("src", help="bedded 48 kHz / 24-bit wav")
    ap.add_argument("packet_dir", metavar="packet-dir-name", help="e.g. 2026-10-20_285hz-drift-wave2-rain")
    ap.add_argument("base", help="file base name, e.g. 285hz-drift-wave2-rain-s200285-9m44s")
    ap.add_argument("notes", metavar="handoff-notes.md", help="recipe / measurements / verdict appended to the handoff")
    ap.add_argument("--out", default=None, help="packet work root (default: <wav folder>/packet)")
    ap.add_argument("--deliver", action="store_true", help="copy the packet to <hand-off dir>/deliveries/<packet-dir-name>/")
    ap.add_argument("--handoff-dir", default=None, help="override the hand-off dir (else NAMIMA_HANDOFF_DIR / Google Drive)")
    a = ap.parse_args(argv)

    src = Path(a.src)
    pdir, base = a.packet_dir, a.base
    notes = Path(a.notes).read_text(encoding="utf-8")
    work = (Path(a.out) if a.out else src.parent / "packet") / pdir
    work.mkdir(parents=True, exist_ok=True)
    master = work / f"{base}-master.wav"
    shutil.copy2(src, master)
    ff, ffsrc = find_ffmpeg()
    m4a = encode(ff, master, "m4a") if ff else None
    lines = [f"# {base} — hand-off", "",
             "- Status: listening candidate; not published",
             f"- Packaged: {platform.node()} / wave-2 texture lane (namima.texture_layer + ACE-Step bed) — CPU layering, deterministic given core seed + bed file",
             "", "## Delivery assets", "",
             f"- `{master.name}`", "  - 48 kHz / 24-bit PCM", f"  - SHA-256: `{sha256(master)}`"]
    if m4a:
        lines += [f"- `{m4a.name}`", "  - AAC-LC 192 kbps, fast-start", f"  - SHA-256: `{sha256(m4a)}`"]
    lines += ["", notes.rstrip(), ""]
    md = work / f"{base}-handoff.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    print("packet:", work)
    for p in (master, m4a, md):
        if p:
            print("  ", p.name, p.stat().st_size)
    if not m4a:
        print("NOTE: no ffmpeg found (NAMIMA_FFMPEG / PATH / imageio-ffmpeg) - m4a skipped")
    if a.deliver:
        hd, hsrc = resolve_handoff_dir(a.handoff_dir)
        if hsrc.startswith("fallback"):
            raise SystemExit("hand-off dir not found (Google Drive AI連携/Music); pass --handoff-dir or set NAMIMA_HANDOFF_DIR")
        dest = hd / "deliveries" / pdir
        if dest.exists():
            raise SystemExit(f"refusing to write into existing packet folder: {dest}")
        dest.mkdir(parents=True)
        for p in (master, m4a, md):
            if p:
                shutil.copy2(p, dest / p.name)
        print("delivered ->", dest, f"({hsrc})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
