"""Wave-2 probe 2: layer each candidate bed under the SAME 285 core (from probe 1) and measure.

    python scripts/texture_lane/probe2_layer.py --out <work> <bed.wav> [<bed.wav> ...] [--setting NAME=LEVEL_DB:WIDTH ...]

Reuses the core written by probe1 (<out>/285-drift-core-48k24.wav, or --core) so all candidates share one core.
Default settings A (-20 dB / width 0.50) and B (-22 dB / width 0.22); --setting replaces them
(285 Drift II adopted: --setting C=-24:0.5).
Writes <out>/<tag>-<setting>-48k24.wav full + clip90s, appends to <out>/measurements-probe2.json
(delete that file first for a fresh table).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))   # repo/src (namima)
sys.path.insert(0, str(Path(__file__).resolve().parent))               # lane siblings (probe1_layer, common)

from namima.generator import write_wav24                                 # noqa: E402
from namima.texture_layer import read_wav, resample_to, layer, highpass_for  # noqa: E402
from probe1_layer import measure, clip, SR, ROOT                           # noqa: E402
from common import parse_setting                                           # noqa: E402

DEFAULT_SETTINGS = {"A": dict(level_db=-20.0, width=0.50), "B": dict(level_db=-22.0, width=0.22)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="probe 2: layer candidate beds under the probe-1 core and measure")
    ap.add_argument("beds", nargs="+", metavar="BED", help="candidate bed wavs")
    ap.add_argument("--out", required=True, help="work folder (outside the repo) holding the probe-1 core")
    ap.add_argument("--core", default=None, help=f"core wav (default: <out>/{ROOT}-drift-core-48k24.wav)")
    ap.add_argument("--setting", type=parse_setting, action="append", metavar="NAME=LEVEL_DB:WIDTH",
                    help="layer setting, repeatable (replaces the default A / B pair)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    settings = dict(a.setting) if a.setting else dict(DEFAULT_SETTINGS)
    core_path = Path(a.core) if a.core else out / f"{ROOT}-drift-core-48k24.wav"

    sr, core = read_wav(core_path)
    if sr != SR:
        raise SystemExit(f"core must be {SR} Hz (got {sr} Hz): {core_path}")
    reports = []
    for bedp in (Path(p) for p in a.beds):
        bed_sr, bed = read_wav(bedp)
        if bed_sr != SR:
            bed = resample_to(bed, bed_sr, SR)
        tag = bedp.stem.replace("-90s-48kf32", "").replace("-60s-48k24", "")
        for name, st in settings.items():
            mixed, prepared = layer(core, bed, SR, ROOT, level_db=st["level_db"], highpass_hz=None,
                                    width=st["width"], seed=ROOT)
            peak = float(np.abs(mixed).max())
            if peak > 0.99:
                mixed *= 0.99 / peak
            rep = measure(f"{tag}-{name}", core, mixed, prepared)
            rep.update(st, highpass_hz=highpass_for(ROOT), bed=bedp.name, bed_seconds=round(len(bed) / SR, 1))
            reports.append(rep)
            write_wav24(out / f"{tag}-{name}-48k24.wav", mixed, SR)
            write_wav24(out / f"{tag}-{name}-clip90s.wav", clip(mixed), SR)
            print(f"[{tag}-{name}] root {rep['root_delta_db']:+.3f} dB  low-crest {rep['low_crest_db_<150']}  "
                  f"pres-crest {rep['pres_crest_db_2k-6k']}  side/mid {rep['side_to_mid']}  env_cv {rep['env_cv_4s']}  "
                  f"bands {rep['band_delta_db_vs_core']}", flush=True)
    p = out / "measurements-probe2.json"
    old = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    p.write_text(json.dumps(old + reports, indent=2, ensure_ascii=False), encoding="utf-8")
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
