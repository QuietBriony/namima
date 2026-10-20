"""Bed hygiene for the sleep lane: measure a texture bed's spikiness / tonality / pulse, and
optionally write a conditioned copy (gentle peak limiting at the bed's own level).

    python scripts/texture_lane/bed_stats.py <bed.wav> [--condition <out.wav>] [--knee-db 9]

Metrics (after the same 800 Hz HPF the layer applies):
  crest_db        peak / rms of the HPF'd bed (noise-like beds ~12-15 dB; crackly > 20)
  click_per_min   samples > +12 dB over a 50 ms RMS envelope, grouped (<=10 ms apart), per minute
  p999_over_rms   99.9th percentile |x| over rms (dB)
  flatness_800_6k spectral flatness in 800-6000 Hz (1.0 = white-ish noise, <0.3 = tonal/pitched)
  pulse           max normalised autocorrelation of the 20 ms energy envelope, lags 0.25-2.0 s
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))   # repo/src (namima)
sys.path.insert(0, str(Path(__file__).resolve().parent))               # lane siblings (common)

from namima.generator import write_wav24  # noqa: E402
from common import SR, PULSE_LAGS, envelope_autocorr, energy_envelope_20ms, load_48k  # noqa: E402


def hpf(x, hz=800.0):
    sos = butter(8, hz / (SR / 2), btype="high", output="sos")
    return np.stack([sosfiltfilt(sos, x[:, c]) for c in range(x.shape[1])], axis=1)


def envelope_rms(m, win_s=0.05):
    w = int(SR * win_s)
    k = np.ones(w) / w
    return np.sqrt(np.convolve(m ** 2, k, mode="same")) + 1e-9


def stats(x):
    m = x.mean(axis=1)
    rms = np.sqrt(np.mean(m ** 2)) + 1e-12
    peak = np.abs(m).max()
    env = envelope_rms(m)
    over = np.abs(m) > env * 10 ** (12 / 20)
    idx = np.flatnonzero(over)
    clicks = 0
    if len(idx):
        gaps = np.diff(idx)
        clicks = 1 + int((gaps > SR * 0.010).sum())
    minutes = len(m) / SR / 60.0
    # spectral flatness 800-6000 Hz (Welch-ish: average of 4096-pt windows)
    w = 4096
    n = len(m) // w
    freqs = np.fft.rfftfreq(w, 1 / SR)
    band = (freqs >= 800) & (freqs <= 6000)
    ps = np.zeros(band.sum())
    for i in range(n):
        seg = m[i * w:(i + 1) * w] * np.hanning(w)
        ps += np.abs(np.fft.rfft(seg))[band] ** 2
    ps = ps / max(n, 1) + 1e-18
    flat = float(np.exp(np.mean(np.log(ps))) / np.mean(ps))
    # pulse: autocorrelation of 20 ms energy envelope
    ac = envelope_autocorr(energy_envelope_20ms(m))
    lo, hi = PULSE_LAGS
    pulse = float(ac[lo:hi].max()) if len(ac) > hi else 0.0
    return {
        "seconds": round(len(m) / SR, 1),
        "rms_dbfs": round(20 * np.log10(rms), 2),
        "crest_db": round(20 * np.log10(peak / rms), 2),
        "p999_over_rms_db": round(20 * np.log10(np.percentile(np.abs(m), 99.9) / rms), 2),
        "click_per_min": round(clicks / max(minutes, 1e-6), 1),
        "flatness_800_6k": round(flat, 3),
        "pulse": round(pulse, 3),
    }


def condition(x, knee_db=9.0):
    """Instantaneous soft clip at the bed's own level (rms * knee): peaks fold into a
    tanh curve, so the crest can never exceed ~knee+2 dB. Deterministic, stereo-linked
    scale, no makeup gain. At -20 dB under the core the curvature is inaudible; what it
    removes is exactly the spikes a sleep bed must not have."""
    m = x.mean(axis=1)
    rms = np.sqrt(np.mean(m ** 2)) + 1e-12
    thr = rms * 10 ** (knee_db / 20)
    return thr * np.tanh(x / thr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="texture bed hygiene stats (+ optional tanh-conditioned copy)")
    ap.add_argument("bed", help="texture bed wav (any rate; analysed at 48 kHz)")
    ap.add_argument("--condition", metavar="OUT_WAV", default=None,
                    help="also write the HPF 800 + tanh-conditioned bed (48 kHz / 24-bit) here")
    ap.add_argument("--knee-db", type=float, default=9.0, help="tanh knee over the bed RMS (default 9)")
    a = ap.parse_args(argv)
    x = load_48k(a.bed)
    h = hpf(x)
    print("raw   :", stats(x))
    print("hpf800:", stats(h))
    if a.condition:
        c = condition(h, knee_db=a.knee_db)
        print(f"cond{a.knee_db:+.0f}:", stats(c))
        write_wav24(a.condition, c.astype(np.float64), SR)
        print("wrote", a.condition)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
