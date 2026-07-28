"""Headphone depth for texture layers, without breaking the phone speaker.

The problem this solves
-----------------------
The solfeggio pieces are auditioned on an iPhone built-in speaker, which is
effectively a mono sum, so ``solfeggio_composer`` deliberately keeps everything
mono-compatible. But the audience for sleep/focus material listens on
headphones, where a flat centred image is the one thing that reads as cheap.

Both cannot be served by widening the core: any delayed copy of a centred sound
combs against its twin in the mono sum and the body of the tone disappears on
the speaker. So the core stays centred and mono, and only the TEXTURE layer is
spatialised.

Why decorrelation and not delays
--------------------------------
Delaying one ear (a real ITD) is the textbook way to place a sound, and it is
exactly what destroys the mono sum: L(t) + L(t-d) is a comb filter with nulls
every 1/d Hz. Two *independent* signals do not comb - their powers add. So each
ear is built by convolving the source with its OWN exponentially decaying noise
impulse, seeded differently. The ears end up uncorrelated (headphones hear a
room), while the mono sum is the source convolved with the SUM of two noise
impulses, which is still noise: no nulls, roughly +3 dB incoherent gain.

``mono_safety`` measures that claim rather than asserting it, and the tests hold
it to a band-by-band budget.

numpy + scipy only; deterministic for a fixed ``seed`` (namima rules 5 and 6 -
no samples, no new dependencies).

    python -m namima.spatial in.wav --out wide.wav --width 0.8
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

__version__ = "0.1.0"

# Head-shadow corner. Above this the far ear is darkened; below it, the
# wavelength is longer than a head and no shadow exists in the real world.
SHADOW_HZ = 1200.0
ANALYSIS_BANDS = ((60, 250), (250, 800), (800, 3000), (3000, 12000))


def decay_noise_ir(length, sr, seed, decay_s, predelay_ms=0.0):
    """One ear's impulse: exponentially decaying noise after a short predelay."""
    rng = np.random.default_rng(seed)
    ir = rng.standard_normal(length)
    t = np.arange(length) / sr
    ir *= np.exp(-t / max(decay_s, 1e-6))
    pre = int(sr * predelay_ms / 1000.0)
    if pre > 0:
        ir = np.concatenate([np.zeros(pre), ir])[:length]
    # No dry spike here on purpose. An identical impulse in both ears is
    # perfectly correlated and swamps the decorrelated tail, which pins the
    # image back to the centre no matter what ``width`` is set to. The dry
    # path belongs to the crossfade in ``spatialise``, where it is controllable.
    peak = np.abs(ir).max()
    return ir / peak if peak > 0 else ir


def spatialise(x, sr, seed=174, width=0.8, decay_s=1.1, predelay_ms=11.0):
    """Mono (or mono-summed) input -> uncorrelated stereo pair.

    ``width`` 0..1 crossfades between the untouched centre and the fully
    decorrelated pair, so the effect can be dialled back without re-rendering.
    """
    if x.ndim > 1:
        x = x.mean(axis=1)
    width = float(np.clip(width, 0.0, 1.0))
    length = int(sr * max(decay_s, 0.05) * 2)

    # Ears differ only by seed; the asymmetric predelay is a few samples of
    # room, not an ITD, so it cannot comb the sum.
    left_ir = decay_noise_ir(length, sr, seed, decay_s, predelay_ms)
    right_ir = decay_noise_ir(length, sr, seed + 977, decay_s, predelay_ms * 1.27)

    left = fftconvolve(x, left_ir)[: len(x)]
    right = fftconvolve(x, right_ir)[: len(x)]

    # Gentle head shadow: each ear loses a little top, on opposite sides, which
    # reads as off-axis without touching phase relationships in the sum.
    sos = butter(1, SHADOW_HZ / (sr / 2), btype="low", output="sos")
    left = left - 0.18 * (left - sosfilt(sos, left))
    right = right - 0.12 * (right - sosfilt(sos, right))

    # Match the wet to the dry by RMS, not by peak. A reverb tail has a much
    # lower peak-to-RMS than its source, so peak-matching makes the wet several
    # times louder in energy and ``width`` stops behaving like a dry/wet
    # control - every setting above 0 lands fully wet.
    wet = np.stack([left, right], axis=1)
    dry_rms = np.sqrt((x ** 2).mean())
    wet_rms = np.sqrt((wet.mean(axis=1) ** 2).mean())
    if wet_rms > 0:
        wet *= dry_rms / wet_rms

    dry = np.stack([x, x], axis=1)
    return dry * (1.0 - width) + wet * width


def band_energy(signal, sr, lo, hi):
    spectrum = np.abs(np.fft.rfft(signal * np.hanning(len(signal))))
    freq = np.fft.rfftfreq(len(signal), 1.0 / sr)
    mask = (freq >= lo) & (freq < hi)
    return float(np.sqrt((spectrum[mask] ** 2).sum()))


def mono_safety(stereo, reference, sr, bands=ANALYSIS_BANDS):
    """Per-band dB the mono sum's BALANCE moves against the reference.

    Both signals are normalised to unit RMS first, because the question is not
    "is it louder" (a reverb changes level, and level is a fader) but "did a
    band get eaten". Comb filtering shows up as one or two bands several dB
    down while the others sit near zero.

    Bands holding less than 1% of the reference's power are skipped: a ratio
    against silence is arbitrarily large and says nothing.
    """
    mono = stereo.mean(axis=1)
    if reference.ndim > 1:
        reference = reference.mean(axis=1)

    def unit(signal):
        rms = np.sqrt((signal ** 2).mean())
        return signal / rms if rms > 0 else signal

    mono, reference = unit(mono), unit(reference)
    total = band_energy(reference, sr, 20, sr / 2)
    out = {}
    for lo, hi in bands:
        source = band_energy(reference, sr, lo, hi)
        if total <= 0 or (source / total) ** 2 < 0.01:
            continue                       # not present in the source anyway
        summed = band_energy(mono, sr, lo, hi)
        out[(lo, hi)] = 20.0 * np.log10(max(summed, 1e-12) / max(source, 1e-12))
    return out


def channel_correlation(stereo):
    """Zero-lag correlation. 1.0 = identical channels, 0.0 = uncorrelated.

    Read this together with ``side_to_mid``: on narrowband material two
    genuinely independent reverb tails still land at the same frequency with
    some fixed phase offset, so this number reports cos(delta phi) and can sit
    near 0.5 on a bed that is audibly wide. It catches "the channels are the
    same signal"; it does not measure perceived width.
    """
    left, right = stereo[:, 0], stereo[:, 1]
    denominator = np.sqrt((left ** 2).sum() * (right ** 2).sum())
    return float(abs((left * right).sum() / denominator)) if denominator > 0 else 1.0


def side_to_mid(stereo):
    """Side/Mid energy ratio - what a headphone listener hears as width.

    0.0 = dead centre. Around 0.5 the bed sits outside the head; above ~1.0 the
    sides dominate, which is the point where a mono speaker starts to lose the
    material entirely.
    """
    mid = (stereo[:, 0] + stereo[:, 1]) * 0.5
    side = (stereo[:, 0] - stereo[:, 1]) * 0.5
    mid_rms = np.sqrt((mid ** 2).mean())
    side_rms = np.sqrt((side ** 2).mean())
    return float(side_rms / mid_rms) if mid_rms > 0 else float("inf")


def main(argv=None):
    from scipy.io import wavfile

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source")
    parser.add_argument("--out", default=None)
    parser.add_argument("--width", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=174)
    parser.add_argument("--decay", type=float, default=1.1)
    args = parser.parse_args(argv)

    sr, data = wavfile.read(args.source)
    x = data.astype(np.float64)
    if np.issubdtype(data.dtype, np.integer):
        x /= float(np.iinfo(data.dtype).max)
    mono = x.mean(axis=1) if x.ndim > 1 else x

    wide = spatialise(mono, sr, seed=args.seed, width=args.width, decay_s=args.decay)
    print(f"side/mid: {side_to_mid(wide):.3f} (0 = centred, ~0.5 = outside the head)"
          f"   correlation: {channel_correlation(wide):.3f}")
    print("mono-sum change vs source:")
    for (lo, hi), delta in mono_safety(wide, mono, sr).items():
        print(f"  {lo:5d}-{hi:5d} Hz  {delta:+6.2f} dB")

    peak = np.abs(wide).max()
    if peak > 0.99:
        wide *= 0.99 / peak
    out = Path(args.out or Path(args.source).with_name(
        Path(args.source).stem + "-binaural.wav"))
    wavfile.write(out, sr, wide.astype(np.float32))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
