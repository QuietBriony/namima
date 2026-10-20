"""Wave-2 probe 1: render the 285 Hz Drift core (namima) and layer one texture bed under it.

    python scripts/texture_lane/probe1_layer.py --out <work> [--bed <bed.wav>] [--setting NAME=LEVEL_DB:WIDTH ...]

Default settings, side by side (--setting replaces them):
  A_approved : level -20 dB / width 0.50  (ear-approved on 174 on 2026-07-28)
  B_codex    : level -22 dB / width 0.22  (the 8/15 Mist Pulse v1 config)
HPF = highpass_for(285) = 800 Hz (same corner as the approved 174 case).
Outputs 48 kHz/24-bit into --out: core (<out>/285-drift-core-48k24.wav, reused by probe2_layer.py),
bedded full tracks, 90 s audition clips, measurements-probe1.json.
CPU only (numpy/scipy) - deterministic.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))   # repo/src (namima)
sys.path.insert(0, str(Path(__file__).resolve().parent))               # lane siblings (common)

from namima import hazama_release as hr                      # noqa: E402
from namima.generator import load_presets, write_wav24       # noqa: E402
from namima.texture_layer import read_wav, resample_to, layer, root_impact, highpass_for  # noqa: E402
from namima.spatial import band_energy, side_to_mid          # noqa: E402
from common import SR, parse_setting                         # noqa: E402

ROOT = 285
CLIP = (90.0, 180.0)   # audition window (after the intro)
DEFAULT_SETTINGS = {"A_approved": dict(level_db=-20.0, width=0.50),
                    "B_codex": dict(level_db=-22.0, width=0.22)}

BANDS = {"sub<150": (20, 150), "low150-800": (150, 800), "mid800-2k": (800, 2000),
         "pres2k-6k": (2000, 6000), "air6k-16k": (6000, 16000)}


def mono(x):
    return x.mean(axis=1)


def db(v):
    return 20.0 * np.log10(max(float(v), 1e-12))


def band_db(x, lo, hi):
    # band_energy returns an AMPLITUDE (sqrt of summed power) -> 20*log10, not 10*log10.
    # (Audit 2026-10-20: the 10*log10 version halved every band delta in measurements-probe1/2.)
    return 20.0 * np.log10(max(band_energy(x, SR, lo, hi), 1e-18))


def crest_db(x, lo=None, hi=None):
    m = mono(x)
    if lo is not None or hi is not None:
        if lo and hi:
            sos = butter(4, [lo / (SR / 2), hi / (SR / 2)], btype="band", output="sos")
        elif hi:
            sos = butter(4, hi / (SR / 2), btype="low", output="sos")
        else:
            sos = butter(4, lo / (SR / 2), btype="high", output="sos")
        m = sosfiltfilt(sos, m)
    rms = np.sqrt(np.mean(m ** 2)) + 1e-12
    return db(np.abs(m).max() / rms)


def envelope_cv(x, win_s=4.0):
    m = mono(x)
    w = int(SR * win_s)
    n = len(m) // w
    r = np.sqrt((m[: n * w].reshape(n, w) ** 2).mean(axis=1)) + 1e-12
    return float(r.std() / r.mean())


def centroid_track(x, win_s=4.0):
    m = mono(x)
    w = int(SR * win_s)
    n = len(m) // w
    freqs = np.fft.rfftfreq(w, 1.0 / SR)
    cs = []
    for i in range(n):
        seg = m[i * w:(i + 1) * w] * np.hanning(w)
        mag = np.abs(np.fft.rfft(seg)) + 1e-12
        cs.append(float((freqs * mag).sum() / mag.sum()))
    cs = np.array(cs)
    return {"centroid_mean_hz": float(cs.mean()), "centroid_std_hz": float(cs.std())}


def exposure(core_mono, bed_mono, win_s=0.05):
    """How far the bed pokes out: 50 ms RMS blocks of the prepared (layered) bed, dB re the core's
    overall RMS. p99 is the figure the 285 Drift II level was calibrated with (ear-approved 174 mix
    -8.0 dB; adopted -24 dB setting -18.2 dB). '-18 dB' mirrors rubric gate 4 (bed/core <= -18 dB)."""
    core_rms = np.sqrt(np.mean(core_mono ** 2))
    w = int(SR * win_s)
    n = len(bed_mono) // w
    e = np.sqrt((bed_mono[: n * w].reshape(n, w) ** 2).mean(axis=1)) + 1e-12
    e_db = 20.0 * np.log10(e / core_rms)
    return {"max_db": round(float(e_db.max()), 1),
            "p99_db": round(float(np.percentile(e_db, 99)), 1),
            "median_db": round(float(np.median(e_db)), 1),
            "time_over_-18dB_%": round(float((e_db > -18.0).mean() * 100), 2)}


def measure(name, core, mixed, bed=None):
    cm, mm = mono(core), mono(mixed)
    imp = root_impact(core, mixed, SR, ROOT)
    rep = {
        "name": name,
        "root_band_hz": [round(v, 1) for v in imp["root_band_hz"]],
        "root_delta_db": round(float(imp["root_delta_db"]), 3),
        "rms_dbfs": round(db(np.sqrt(np.mean(mixed ** 2))), 2),
        "peak": round(float(np.abs(mixed).max()), 3),
        "low_crest_db_<150": round(crest_db(mixed, hi=150), 2),
        "pres_crest_db_2k-6k": round(crest_db(mixed, 2000, 6000), 2),
        "side_to_mid": round(float(side_to_mid(mixed)), 3),
        "env_cv_4s": round(envelope_cv(mixed), 4),
        **centroid_track(mixed),
        "band_delta_db_vs_core": {k: round(band_db(mm, *v) - band_db(cm, *v), 2) for k, v in BANDS.items()},
    }
    if bed is not None:
        bm = mono(bed)
        rep["bed_minus_core_db"] = {k: round(band_db(bm, *v) - band_db(cm, *v), 2) for k, v in BANDS.items()}
        rep["bed_rms_rel_core_db"] = round(db(np.sqrt(np.mean(bm ** 2)) / (np.sqrt(np.mean(cm ** 2)) + 1e-12)), 2)
        rep["exposure"] = exposure(cm, bm)
    return rep


def clip(x):
    a, b = int(CLIP[0] * SR), int(CLIP[1] * SR)
    return x[a:b]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="probe 1: render the 285 Drift core and layer one bed under it")
    ap.add_argument("--out", required=True, help="work folder (outside the repo); core, mixes and json go here")
    ap.add_argument("--bed", default=None,
                    help="texture bed wav (default: <out>/bed-src/ace-air-altA-60s-48k24.wav, the 174-approved air bed)")
    ap.add_argument("--setting", type=parse_setting, action="append", metavar="NAME=LEVEL_DB:WIDTH",
                    help="layer setting, repeatable (replaces the default A_approved / B_codex pair)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    bed_path = Path(a.bed) if a.bed else out / "bed-src" / "ace-air-altA-60s-48k24.wav"
    settings = dict(a.setting) if a.setting else dict(DEFAULT_SETTINGS)

    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    presets = load_presets()
    core = hr.master(hr.render_drift(ROOT, presets), "drift")
    print(f"core rendered {core.shape[0]/SR:.1f}s in {time.perf_counter()-t0:.1f}s "
          f"rms {np.sqrt(np.mean(core**2)):.3f} peak {np.abs(core).max():.3f}", flush=True)
    write_wav24(out / f"{ROOT}-drift-core-48k24.wav", core, SR)
    write_wav24(out / f"{ROOT}-drift-core-clip90s.wav", clip(core), SR)

    bed_sr, bed = read_wav(bed_path)
    if bed_sr != SR:
        bed = resample_to(bed, bed_sr, SR)
    print(f"bed {bed_path.name}: {len(bed)/bed_sr:.1f}s @ {bed_sr}", flush=True)

    reports = [measure("core_only", core, core)]
    for name, st in settings.items():
        mixed, prepared = layer(core, bed, SR, ROOT, level_db=st["level_db"],
                                highpass_hz=None, width=st["width"], seed=ROOT)
        peak = float(np.abs(mixed).max())
        if peak > 0.99:
            mixed *= 0.99 / peak
        rep = measure(name, core, mixed, prepared)
        rep.update(st, highpass_hz=highpass_for(ROOT))
        reports.append(rep)
        write_wav24(out / f"{ROOT}-drift-bed-{name}-48k24.wav", mixed, SR)
        write_wav24(out / f"{ROOT}-drift-bed-{name}-clip90s.wav", clip(mixed), SR)
        print(f"[{name}] root {rep['root_delta_db']:+.3f} dB  low-crest {rep['low_crest_db_<150']} dB  "
              f"side/mid {rep['side_to_mid']}  env_cv {rep['env_cv_4s']}", flush=True)

    (out / "measurements-probe1.json").write_text(json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"done in {time.perf_counter()-t0:.1f}s -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
