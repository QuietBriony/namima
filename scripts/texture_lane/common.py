"""Shared helpers for the texture lane (scripts/texture_lane/*.py).

Only what two or more lane scripts carried as private copies lives here: the 48 kHz
load, the 285 Hz lattice, the 1.46 Hz long-term spectrum, the 20 ms energy envelope
and its autocorrelation, and the --setting parser of the two layer probes.
The numerics are the original scratchpad code unchanged (same windows, epsilons and
operation order), so measurements and cleaned beds stay byte-reproducible.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))   # repo/src (namima): no install, no PYTHONPATH

from namima.texture_layer import read_wav, resample_to  # noqa: E402

SR = 48000
# 285 Hz lattice partials inside the bed band: harmonics of the 3-6-9 triad 285 / 528 / 852 Hz.
LATTICE = sorted({f * k for f in (285.0, 528.0, 852.0) for k in range(1, 24) if 700 <= f * k <= 7000})
# pulse search window of the 20 ms envelope autocorrelation: lags 0.25 - 2.0 s
PULSE_LAGS = (int(0.25 / 0.02), int(2.0 / 0.02))


def load_48k(path):
    """read_wav + rate-match to SR (ACE-Step writes 48 kHz already; older beds may not)."""
    sr, x = read_wav(path)
    if sr != SR:
        x = resample_to(x, sr, SR)
    return x


def spectrum_db(m, w=1 << 15):
    """Long-term power spectrum of a mono signal: Hann windows of 32768 (1.46 Hz bins), averaged, dB."""
    n = len(m) // w
    freqs = np.fft.rfftfreq(w, 1 / SR)
    ps = np.zeros(len(freqs))
    for i in range(n):
        ps += np.abs(np.fft.rfft(m[i * w:(i + 1) * w] * np.hanning(w))) ** 2
    return freqs, 10 * np.log10(ps / max(n, 1) + 1e-20)


def energy_envelope_20ms(m):
    """Mean power per 20 ms hop (no overlap)."""
    hop = int(SR * 0.02)
    return (m[: (len(m) // hop) * hop].reshape(-1, hop) ** 2).mean(axis=1)


def envelope_autocorr(e):
    """Autocorrelation of the mean-removed envelope, normalised so lag 0 = 1."""
    ec = e - e.mean()
    ac = np.correlate(ec, ec, mode="full")[len(ec) - 1:]
    return ac / (ac[0] + 1e-18)


def parse_setting(text):
    """'C=-24:0.5' -> ('C', {'level_db': -24.0, 'width': 0.5}) for layer(level_db=..., width=...)."""
    try:
        name, rest = text.split("=", 1)
        level, width = rest.split(":", 1)
        if not name.strip():
            raise ValueError
        return name.strip(), dict(level_db=float(level), width=float(width))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected NAME=LEVEL_DB:WIDTH (e.g. C=-24:0.5), got {text!r}") from None
