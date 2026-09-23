"""namima.deliver — the same delivery lane on any PC (Surface / worker / studio).

CPU-only (numpy/scipy), deterministic, GPU never touched.  One command produces
the worker-convention hand-off packet and drops it in the shared Google Drive
folder that every machine syncs:

    <base>-master.wav   48 kHz / 24-bit PCM
    <base>-iphone.m4a   AAC-LC 192 kbps, fast-start   (phone listening via the Drive app)
    <base>-handoff.md   SHA-256 of both, recipe, structure timeline, knobs

Usage (from the namima repo root, any OS / CPU):

    python scripts/deliver.py doctor                       # what this machine can do
    python scripts/deliver.py judge --name idm-ambient     # 3 x 90 s clips (beatless/soft/idm)
    python scripts/deliver.py long  --name idm-ambient --mode idm --bars 144

Resolution order (override with flags / env):
  ffmpeg      : $NAMIMA_FFMPEG -> `ffmpeg` on PATH -> imageio_ffmpeg bundled binary -> none (wav only)
  hand-off dir: --handoff-dir -> $NAMIMA_HANDOFF_DIR -> <home>/マイドライブ/AI連携/Music
                -> G:/マイドライブ/AI連携/Music -> <home>/My Drive/AI連携/Music -> ./deliveries (warn)
Subprocesses are launched from Python with Path objects, so non-ASCII user
folders (平成造園 ...) never pass through a Git-Bash shell line.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

import numpy as np

from .generator import write_wav24
from .idm_ambient import AmbientConfig, MODES, render, add_variation_args, variation_kwargs

__version__ = "0.2.0"
HANDOFF_SUBPATH = Path("AI連携") / "Music"


# =============================================================================
# environment resolution
# =============================================================================
def find_ffmpeg() -> tuple[str | None, str]:
    env = os.environ.get("NAMIMA_FFMPEG")
    if env and Path(env).exists():
        return env, "env:NAMIMA_FFMPEG"
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path, "PATH"
    try:
        import imageio_ffmpeg  # optional fallback (bundled x64 binary; runs under ARM emulation)
        return imageio_ffmpeg.get_ffmpeg_exe(), "imageio_ffmpeg"
    except Exception:
        return None, "none"


def handoff_candidates() -> list[Path]:
    home = Path.home()
    return [
        home / "マイドライブ" / HANDOFF_SUBPATH,
        Path("G:/") / "マイドライブ" / HANDOFF_SUBPATH,
        home / "My Drive" / HANDOFF_SUBPATH,
        home / "Google Drive" / "マイドライブ" / HANDOFF_SUBPATH,
    ]


def resolve_handoff_dir(explicit: str | None = None, fallback: Path | None = None) -> tuple[Path, str]:
    if explicit:
        return Path(explicit), "flag"
    env = os.environ.get("NAMIMA_HANDOFF_DIR")
    if env:
        return Path(env), "env:NAMIMA_HANDOFF_DIR"
    for c in handoff_candidates():
        if c.is_dir():
            return c, "google-drive"
    return (fallback or Path("deliveries")), "fallback:./deliveries (Drive folder not found)"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def encode(ff: str, wav: Path, fmt: str, bitrate: str = "192k") -> Path:
    stem = wav.name[:-len("-master.wav")] if wav.name.endswith("-master.wav") else wav.stem
    out = wav.with_name(stem + ("-iphone.m4a" if fmt == "m4a" else ".mp3"))
    codec = (["-codec:a", "aac", "-b:a", bitrate, "-movflags", "+faststart"] if fmt == "m4a"
             else ["-codec:a", "libmp3lame", "-b:a", bitrate])
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(wav), *codec, str(out)], check=True)
    return out


# =============================================================================
# packet
# =============================================================================
def _sec(bars: float, bar_s: float) -> str:
    s = int(round(bars * bar_s))
    return f"{s // 60}:{s % 60:02d}"


def handoff_md(base: str, meta: dict, files: dict[str, Path], recipe_cmd: str, notes: str = "") -> str:
    bar_s = 240.0 / float(meta["bpm"])
    st = meta.get("structure") or {}
    lines = [f"# {base} — hand-off", "",
             "- Status: listening candidate; not published",
             f"- Producer: {platform.node()} / namima.deliver v{__version__} (CPU-only, numpy/scipy, deterministic)",
             "- Rights: self-synthesised (no samples, no learned models) — re-renderable from the seed",
             "", "## Delivery assets", ""]
    desc = {"master": "48 kHz / 24-bit PCM", "iphone": "AAC-LC 192 kbps, fast-start", "mp3": "MP3 192 kbps"}
    for label, p in files.items():
        if p is None or not Path(p).exists():
            continue
        lines += [f"- `{Path(p).name}`", f"  - {desc.get(label, '')}", f"  - SHA-256: `{sha256(Path(p))}`"]
    lines += ["", "## Generation recipe", "",
              f"- Engine: `namima.idm_ambient` v{meta.get('version')} · mode `{meta.get('mode')}` · "
              f"bars {meta.get('bars')} · BPM {meta.get('bpm')} · seed {meta.get('seed')} · "
              f"root_degree {meta.get('root_degree')}",
              f"- Pitch system: {meta.get('pitch_system')}",
              *([f"- Variation: mix_db {meta.get('mix_db', {})} · break_plan {meta.get('break_plan', 'xtal')} · "
                 f"chop_max {meta.get('chop_max', 0.75)}"] if any(k in meta for k in ("mix_db", "break_plan", "chop_max")) else []),
              f"- Re-render (any PC, CPU): `{recipe_cmd}`", ""]
    if st:
        lines += ["## Structure", "", f"- 1 bar = {bar_s:.2f} s",
                  f"- 0:00–{_sec(st['lead'], bar_s)}: pad + sub + texture",
                  f"- {_sec(st['lead'], bar_s)}: lead motif in (stable pitch, delayed vibrato, dotted-8th echo)",
                  f"- {_sec(st['drums'], bar_s)}: beat in ({meta.get('mode')})"]
        for b0, b1 in st.get("breakdowns", []):
            lines.append(f"- {_sec(b0, bar_s)}–{_sec(b1, bar_s)}: breakdown (beat out, lead anchors only)")
        if st.get("outro") is not None:
            lines.append(f"- {_sec(st['outro'], bar_s)}–{_sec(meta['bars'], bar_s)}: outro → 5 s fade")
        lines.append("")
    if notes:
        lines += ["## Notes", "", notes, ""]
    lines += ["## Knobs (if feedback)", "",
              "- balance: `render()` mix gains sub 0.85 / lead 0.55 / pad 0.30 / drums 0.90",
              "- chop: `chop_break` intensity (0.35 / 0.6 / 0.75) · `BREAK_PATTERNS` (xtal / on / roll)",
              "- form: `_structure()` (breakdown every 32 bars, 8-bar outro)", ""]
    return "\n".join(lines)


def write_packet(stereo: np.ndarray, meta: dict, base: str, out_dir: Path, handoff_dir: Path | None,
                 ff: str | None, recipe_cmd: str, deliver_master: bool = True, notes: str = "") -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / f"{base}-master.wav"
    write_wav24(wav, stereo, int(meta["sample_rate"]))
    (out_dir / f"{base}-master.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    files: dict[str, Path | None] = {"master": wav, "iphone": None, "mp3": None}
    if ff:
        files["iphone"] = encode(ff, wav, "m4a")
        files["mp3"] = encode(ff, wav, "mp3")
    md = out_dir / f"{base}-handoff.md"
    md.write_text(handoff_md(base, meta, {k: v for k, v in files.items() if v}, recipe_cmd, notes),
                  encoding="utf-8")
    delivered: list[Path] = []
    if handoff_dir is not None:
        handoff_dir = Path(handoff_dir)
        handoff_dir.mkdir(parents=True, exist_ok=True)
        for p in ([wav] if deliver_master else []) + [files["iphone"], md]:
            if p and Path(p).exists():
                shutil.copy2(p, handoff_dir / Path(p).name)
                delivered.append(handoff_dir / Path(p).name)
    return {"wav": wav, "m4a": files["iphone"], "mp3": files["mp3"], "handoff": md, "delivered": delivered}


# =============================================================================
# commands
# =============================================================================
def _render_job(cfg_dict: dict):
    cfg = AmbientConfig(**cfg_dict)
    t0 = time.perf_counter()
    stereo, meta = render(cfg)
    return cfg.mode, stereo, meta, time.perf_counter() - t0


def cmd_doctor(a) -> int:
    ff, ff_src = find_ffmpeg()
    hd, hd_src = resolve_handoff_dir(a.handoff_dir)
    try:
        import scipy
        scipy_v = scipy.__version__
    except Exception:
        scipy_v = "MISSING"
    t0 = time.perf_counter()
    render(AmbientConfig(bars=4, mode="idm"))
    dt = time.perf_counter() - t0
    per_bar = dt / 4.0
    rep = {
        "host": platform.node(), "os": platform.platform(), "machine": platform.machine(),
        "python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy_v,
        "cpus": os.cpu_count(), "ffmpeg": ff or "MISSING (wav only)", "ffmpeg_source": ff_src,
        "handoff_dir": str(hd), "handoff_source": hd_src, "handoff_exists": hd.is_dir(),
        "bench_4bars_s": round(dt, 2),
        "estimate_90s_clip_s": round(per_bar * 36 + 2, 1), "estimate_6min_s": round(per_bar * 144 + 5, 1),
    }
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    problems = []
    if scipy_v == "MISSING":
        problems.append("scipy missing (pip install -r requirements.txt)")
    if not rep["handoff_exists"]:
        problems.append("hand-off dir not found (set NAMIMA_HANDOFF_DIR)")
    if not ff:
        problems.append("no ffmpeg (m4a/mp3 skipped; install ffmpeg or pip install imageio-ffmpeg)")
    print("DOCTOR:", "OK" if not problems else "ATTENTION — " + "; ".join(problems))
    return 0 if not problems else 1


def cmd_judge(a) -> int:
    ff, _ = find_ffmpeg()
    hd, hd_src = resolve_handoff_dir(a.handoff_dir)
    out_dir = Path(a.out_dir)
    cfgs = [asdict(AmbientConfig(bars=a.bars, bpm=a.bpm, seed=a.seed, mode=m, root_degree=a.root_degree,
                                 **variation_kwargs(a)))
            for m in MODES]
    jobs = max(1, min(a.jobs, len(cfgs)))
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            results = list(ex.map(_render_job, cfgs))
    else:
        results = [_render_job(c) for c in cfgs]
    for mode, stereo, meta, dt in results:
        secs = int(round(meta["frames"] / meta["sample_rate"]))
        base = f"{a.name}-judge-{mode}-s{a.seed}{'-' + a.tag if a.tag else ''}-{secs}s"
        cmd = f"python scripts/deliver.py long --name {a.name} --mode {mode} --bars {a.bars} --seed {a.seed}{variation_cli(a)}"
        pk = write_packet(stereo, meta, base, out_dir, hd, ff, cmd, deliver_master=a.deliver_master,
                          notes="Judgement clip — same seed / motif / pad as its siblings; only the beat differs.")
        print(f"[{mode}] rendered {secs}s in {dt:.1f}s -> {pk['wav'].name}; "
              f"delivered {len(pk['delivered'])} file(s) to {hd} ({hd_src})")
    return 0


def cmd_long(a) -> int:
    ff, _ = find_ffmpeg()
    hd, _ = resolve_handoff_dir(a.handoff_dir)
    cfg = AmbientConfig(bars=a.bars, bpm=a.bpm, seed=a.seed, mode=a.mode, root_degree=a.root_degree,
                        **variation_kwargs(a))
    mode, stereo, meta, dt = _render_job(asdict(cfg))
    secs = int(round(meta["frames"] / meta["sample_rate"]))
    base = a.base or f"{a.name}-{mode}-s{a.seed}{'-' + a.tag if a.tag else ''}-{a.bars}bars-{secs // 60}m{secs % 60:02d}s"
    cmd = f"python scripts/deliver.py long --name {a.name} --mode {mode} --bars {a.bars} --seed {a.seed}{variation_cli(a)}"
    pk = write_packet(stereo, meta, base, Path(a.out_dir), hd, ff, cmd, deliver_master=True, notes=a.notes or "")
    print(f"rendered {secs}s in {dt:.1f}s -> {pk['wav']}")
    for p in pk["delivered"]:
        print(f"delivered -> {p}")
    if not ff:
        print("NOTE: no ffmpeg found — m4a/mp3 skipped (install ffmpeg or `pip install imageio-ffmpeg`)")
    return 0


def variation_cli(a) -> str:
    """Exact CLI suffix that reproduces the non-default variation (repr keeps floats lossless)."""
    parts = []
    for part in AmbientConfig.MIX_PARTS:
        v = getattr(a, f"{part}_db")
        if v != 0.0:
            parts.append(f"--{part}-db {v!r}")
    if a.break_plan != "xtal":
        parts.append(f"--break-plan {a.break_plan}")
    if a.chop_max != 0.75:
        parts.append(f"--chop-max {a.chop_max!r}")
    if a.tag:
        parts.append(f"--tag {a.tag}")
    return (" " + " ".join(parts)) if parts else ""


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--name", default="idm-ambient")
    p.add_argument("--seed", type=int, default=174852)
    p.add_argument("--bpm", type=float, default=96.0)
    p.add_argument("--root-degree", type=int, default=0)
    p.add_argument("--out-dir", default=str(Path("renders") / "deliver"))
    p.add_argument("--handoff-dir", default=None)
    p.add_argument("--tag", default="", help="short ASCII tag added to the packet base name for a variation")
    add_variation_args(p)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="namima.deliver",
                                 description="namima delivery lane — same packet on any PC (CPU-only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("doctor", help="report what this machine can do")
    d.add_argument("--handoff-dir", default=None)
    d.set_defaults(fn=cmd_doctor)
    j = sub.add_parser("judge", help="render the three 90 s judgement clips")
    _common(j)
    j.add_argument("--bars", type=int, default=36)
    j.add_argument("--jobs", type=int, default=min(3, os.cpu_count() or 1))
    j.add_argument("--deliver-master", action="store_true",
                   help="also copy the wav masters to the hand-off dir (default: m4a + handoff only)")
    j.set_defaults(fn=cmd_judge)
    lg = sub.add_parser("long", help="render one long form and deliver the full packet")
    _common(lg)
    lg.add_argument("--mode", choices=MODES, default="idm")
    lg.add_argument("--bars", type=int, default=144)
    lg.add_argument("--base", default=None, help="override the packet base name")
    lg.add_argument("--notes", default=None)
    lg.set_defaults(fn=cmd_long)
    a = ap.parse_args(argv)
    return int(a.fn(a))


if __name__ == "__main__":
    raise SystemExit(main())
