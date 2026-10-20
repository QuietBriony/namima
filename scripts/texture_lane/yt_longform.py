"""Build an N-hour YouTube MP4 from one 44.1 kHz/16-bit WAV using hazama-release's yt_build helpers.

    python scripts/texture_lane/yt_longform.py <src.wav> <hz> <tag> <hours> --youtube-dir <hazama-release>/youtube
        [--image art.png] [--out <dir>] [--from-master [--dither-seed N]]

--youtube-dir : the external folder holding yt_build.py (hazama-release/youtube; not a git repo and
                not part of namima). Its read_wav16 / loop_audio (10 s equal-power crossfades) /
                write_wav16 / frames_from_image / frames are used as-is.
--out         : where the MP4 + still + thumbnail go (default: --youtube-dir, i.e. yt_build's layout).
--from-master : <src.wav> is a 48 kHz/24-bit master; first write <out>/<hz>hz-<tag>-src-441k16.wav with
                namima.hazama_release.write_wav16_441 (147/160 polyphase + seeded TPDF dither,
                seed = --dither-seed, default 400000 + hz = the hazama release convention).
Output: <out>/<hz>hz-<tag>-<hours>h.mp4 (still image @1 fps + AAC 192k), same naming as yt_build.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))   # repo/src (namima)

from namima.texture_layer import read_wav           # noqa: E402
from namima.hazama_release import MASTER_SR, write_wav16_441  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="N-hour YouTube MP4 from one release WAV (via hazama-release yt_build)")
    ap.add_argument("src", help="44.1 kHz / 16-bit WAV (or a 48 kHz master with --from-master)")
    ap.add_argument("hz", type=int)
    ap.add_argument("tag", help="output tag, e.g. drift2 -> <hz>hz-drift2-<hours>h.mp4")
    ap.add_argument("hours", type=int)
    ap.add_argument("--youtube-dir", required=True, help="folder containing yt_build.py (hazama-release/youtube)")
    ap.add_argument("--image", default=None, help="key visual (still = art, thumb = art + Hz text); default: yt_build cover frames")
    ap.add_argument("--out", default=None, help="output folder (default: --youtube-dir)")
    ap.add_argument("--from-master", action="store_true", help="convert a 48 kHz master to 44.1 kHz/16-bit first")
    ap.add_argument("--dither-seed", type=int, default=None, help="TPDF dither seed for --from-master (default 400000 + hz)")
    a = ap.parse_args(argv)

    ydir = Path(a.youtube_dir).resolve()
    if not (ydir / "yt_build.py").is_file():
        ap.error(f"yt_build.py not found in --youtube-dir {ydir}")
    sys.path.insert(0, str(ydir))
    import yt_build as yb  # noqa: E402  (external helper, resolved from --youtube-dir)
    import imageio_ffmpeg  # noqa: E402

    out = Path(a.out).resolve() if a.out else ydir
    out.mkdir(parents=True, exist_ok=True)
    yb.OUT = out          # yt_build writes stills / thumbs to its module-level OUT
    hz, tag, hours = a.hz, a.tag, a.hours
    src = Path(a.src)
    if a.from_master:
        sr48, x48 = read_wav(src)
        if sr48 != MASTER_SR:
            raise SystemExit(f"--from-master expects a {MASTER_SR} Hz master (got {sr48} Hz): {src}")
        seed = a.dither_seed if a.dither_seed is not None else 400000 + hz
        src = out / f"{hz}hz-{tag}-src-441k16.wav"
        write_wav16_441(src, x48, seed=seed)
        print(f"wrote {src} (44.1 kHz/16-bit, TPDF dither seed {seed})", flush=True)

    x, sr = yb.read_wav16(src)
    long = yb.loop_audio(x, sr, hours)
    tmp = yb.OUT / f"_tmp-{hz}-{tag}.wav"
    yb.write_wav16(tmp, long, sr)
    still, thumb = (yb.frames_from_image(Path(a.image), hz, tag) if a.image else yb.frames(hz, "drift", hours))
    mp4 = yb.OUT / f"{hz}hz-{tag}-{hours}h.mp4"
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-y", "-loop", "1", "-framerate", "1", "-i", str(still), "-i", str(tmp),
           "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(mp4)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    tmp.unlink(missing_ok=True)
    if r.returncode != 0:
        print(r.stderr[-1200:])
        return 1
    print(f"wrote {mp4} ({mp4.stat().st_size/1e6:.0f}MB) audio {len(long)/sr/3600:.2f}h thumb {thumb.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
