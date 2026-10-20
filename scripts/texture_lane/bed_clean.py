"""Bed cleaning for the Hz-true lane: HPF 800 -> notch out pitched residue (12-TET leakage from the
generator) -> gentle tanh conditioning -> report. Deterministic.

    python scripts/texture_lane/bed_clean.py <bed.wav> <out.wav> [--prom-db 10] [--max-notches 16] [--knee-db 9]
    python scripts/texture_lane/bed_clean.py <cleaned.wav> <out.wav> --notch-only 1403.2 2322.0

Notch: iirnotch with bandwidth 2 * f0 * (2**(40/1200) - 1), i.e. -3 dB at +-40 cents (Q ~ 21.4);
two detection passes so masked peaks are caught.
--notch-only applies just the listed notches (same filter, in the given order) to an already
cleaned bed: no HPF, no detection, no tanh. The adopted 285 Drift II bed is the --prom-db 8
clean followed by two such calls (1403.2 + 2322.0, then 1760.0), each written to 24-bit in between.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks, iirnotch, medfilt, sosfiltfilt, tf2sos

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))   # repo/src (namima)
sys.path.insert(0, str(Path(__file__).resolve().parent))               # lane siblings (bed_stats, common)

from namima.generator import write_wav24  # noqa: E402
from bed_stats import condition, hpf, stats  # noqa: E402
from common import SR, load_48k, spectrum_db  # noqa: E402


def find_tonal_peaks(x, prom_db=10.0, lo=700.0, hi=7000.0, maxn=16):
    freqs, db = spectrum_db(x.mean(axis=1))
    prom = db - medfilt(db, 301)
    band = np.flatnonzero((freqs >= lo) & (freqs <= hi))
    pk, props = find_peaks(prom[band], prominence=prom_db, distance=20)
    order = np.argsort(props["prominences"])[::-1][:maxn]
    return [(float(freqs[band][pk[j]]), float(props["prominences"][j])) for j in order]


def notch(x, f0, cents=40.0):
    bw = f0 * (2 ** (cents / 1200.0) - 1.0) * 2.0
    b, a = iirnotch(f0, f0 / bw, fs=SR)
    sos = tf2sos(b, a)
    return np.stack([sosfiltfilt(sos, x[:, c]) for c in range(x.shape[1])], axis=1)


def clean(x, prom_db=10.0, knee_db=9.0, passes=2, maxn=16):
    y = hpf(x)
    removed = []
    for _ in range(passes):
        peaks = find_tonal_peaks(y, prom_db, maxn=maxn)
        if not peaks:
            break
        for f0, pr in peaks:
            y = notch(y, f0)
            removed.append((round(f0, 1), round(pr, 1)))
    y = condition(y, knee_db=knee_db)
    left = find_tonal_peaks(y, prom_db=8.0, maxn=5)
    return y, removed, left


def notch_only(x, freqs):
    for f0 in freqs:
        x = notch(x, f0)
    return x


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="clean a texture bed: HPF 800 -> notch 12-TET residue -> tanh")
    ap.add_argument("src", help="bed wav (any rate; processed at 48 kHz)")
    ap.add_argument("out", help="cleaned bed (48 kHz / 24-bit)")
    ap.add_argument("--prom-db", type=float, default=10.0, help="peak prominence over the local median to notch (dB)")
    ap.add_argument("--max-notches", type=int, default=16, help="max notches per detection pass (2 passes)")
    ap.add_argument("--knee-db", type=float, default=9.0, help="tanh knee over the bed RMS (dB)")
    ap.add_argument("--notch-only", type=float, nargs="+", metavar="HZ", default=None,
                    help="targeted mode: apply only these notches, in order (no HPF / detection / tanh)")
    a = ap.parse_args(argv)
    x = load_48k(a.src)
    if a.notch_only:
        y = notch_only(x, a.notch_only)
        write_wav24(a.out, y.astype(np.float64), SR)
        left = find_tonal_peaks(y, prom_db=8.0, maxn=5)
        print(f"{a.src.split('/')[-1]}: notch-only {a.notch_only} -> remaining peaks(>8dB) "
              f"{[(round(f), round(p, 1)) for f, p in left]}")
        print("   wrote  :", a.out)
        return 0
    y, removed, left = clean(x, prom_db=a.prom_db, knee_db=a.knee_db, maxn=a.max_notches)
    write_wav24(a.out, y.astype(np.float64), SR)
    s = {k: (round(float(v), 3) if not isinstance(v, int) else v) for k, v in stats(y).items()}
    print(f"{a.src.split('/')[-1]}: notched {len(removed)} -> remaining peaks(>8dB) {[(round(f), round(p,1)) for f, p in left]}")
    print("   removed:", removed[:12], ("..." if len(removed) > 12 else ""))
    print("   stats  :", s)
    print("   wrote  :", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
