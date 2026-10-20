"""Tonal-residue and pulse-depth check for conditioned beds.
For each wav: top spectral peaks in 800-6000 Hz (prominence over the local median, dB) with their
distance in cents to the nearest 285 Hz lattice partial (harmonics of 285/528/852), and the modulation
depth of the 20 ms energy envelope (CV) with the best-lag autocorrelation (0.25-2 s).

    python scripts/texture_lane/bed_tonal.py <bed.wav> [<bed.wav> ...]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks, medfilt

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))   # repo/src (namima)
sys.path.insert(0, str(Path(__file__).resolve().parent))               # lane siblings (common)

from common import LATTICE, PULSE_LAGS, envelope_autocorr, energy_envelope_20ms, load_48k, spectrum_db  # noqa: E402


def cents(a, b):
    return 1200.0 * np.log2(a / b)


def analyse(path):
    x = load_48k(path)
    m = x.mean(axis=1)
    freqs, db = spectrum_db(m)                             # 32768 -> 1.46 Hz bins
    band = (freqs >= 800) & (freqs <= 6000)
    local = medfilt(db, 301)                               # ~440 Hz median window
    prom = db - local
    idx = np.flatnonzero(band)
    pk, props = find_peaks(prom[idx], prominence=6, distance=20)
    order = np.argsort(prom[idx][pk])[::-1][:5]
    peaks = []
    for j in order:
        f = float(freqs[idx][pk[j]])
        nearest = min(LATTICE, key=lambda L: abs(cents(f, L)))
        peaks.append((round(f, 1), round(float(prom[idx][pk[j]]), 1), round(float(cents(f, nearest)), 0), nearest))
    e = energy_envelope_20ms(m)
    depth = float(e.std() / (e.mean() + 1e-18))
    ac = envelope_autocorr(e)
    lo, hi = PULSE_LAGS
    best = int(np.argmax(ac[lo:hi])) + lo
    return {"peaks(f,prom_dB,cents_to_lattice,lattice)": peaks,
            "env_depth_cv": round(depth, 3), "pulse_ac": round(float(ac[best]), 3),
            "pulse_lag_s": round(best * 0.02, 2)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="tonal residue vs the 285 lattice + envelope pulse depth")
    ap.add_argument("wavs", nargs="+", metavar="WAV")
    a = ap.parse_args(argv)
    for p in a.wavs:
        print(p.split("\\")[-1].split("/")[-1])
        for k, v in analyse(p).items():
            print("   ", k, "=", v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
