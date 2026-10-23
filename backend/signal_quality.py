"""ECG signal-quality assessment — a gate that runs BEFORE model inference.

A single-lead AD8232 trace is frequently unusable: the electrode falls off, the
input rails (clips), or motion/EMG noise drowns the QRS. Feeding such a trace to
the classifier produces a *confident-looking but meaningless* label. This module
computes scale-invariant quality indicators so the API can flag or reject a poor
trace instead of pretending to classify it.

Indicators (all best-effort, single-lead):
  * leadOff      - electrode not in contact (reported by the device, or inferred)
  * flatline     - no ECG content (disconnected / DC)
  * clipping     - samples saturated at the ADC rails
  * noisy        - out-of-band (EMG/mains/motion) energy dominates the ECG band
  * weakSignal   - little in-band ECG content relative to noise/baseline

The verdict is "good" / "acceptable" / "poor"; only non-"poor" traces are
considered usable for classification.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt

GOOD = "good"
ACCEPTABLE = "acceptable"
POOR = "poor"


def _robust_ptp(x: np.ndarray) -> float:
    """Peak-to-peak using the 2nd/98th percentiles, so a single spike or a
    clipped sample doesn't dominate the amplitude estimate."""
    if x.size == 0:
        return 0.0
    return float(np.percentile(x, 98) - np.percentile(x, 2))


def _filter(sig: np.ndarray, fs: float, band, btype: str, order: int = 2) -> np.ndarray:
    nyq = 0.5 * fs
    if sig.size < 12:
        return sig - float(np.mean(sig))
    try:
        if btype == "highpass":
            wc = float(np.clip(band / nyq, 1e-4, 0.999))
            b, a = butter(order, wc, btype="highpass")
        else:
            lo = float(np.clip(band[0] / nyq, 1e-4, 0.999))
            hi = float(np.clip(band[1] / nyq, 1e-4, 0.999))
            if lo >= hi:
                return sig - float(np.mean(sig))
            b, a = butter(order, [lo, hi], btype="band")
        # filtfilt needs the signal longer than its padding window.
        if sig.size <= 3 * max(len(a), len(b)):
            return sig - float(np.mean(sig))
        return filtfilt(b, a, sig)
    except Exception:
        return sig - float(np.mean(sig))


def assess_quality(raw, fs: float, lead_off: bool = False) -> dict:
    """Return a signal-quality report dict (see module docstring)."""
    sig = np.asarray(raw, dtype=float).flatten()
    n = sig.size
    reasons: list[str] = []
    result: dict = {
        "leadOff": bool(lead_off),
        "flatline": False,
        "clipping": False,
        "noisy": False,
        "weakSignal": False,
        "tooShort": False,
    }

    min_samples = max(int(0.5 * fs), 10)
    if n < min_samples:
        result.update(
            tooShort=True, quality=POOR, qualityScore=0,
            usableForClassification=False,
            reasons=["Too few samples for a reliable quality assessment."],
            metrics={"samples": int(n)},
        )
        return result

    scale = max(float(np.max(np.abs(sig))), 1e-9)
    robust_ptp = _robust_ptp(sig)

    # --- flatline: signal barely varies relative to its own magnitude (DC / no contact) ---
    flatline = robust_ptp <= max(1e-9, 1e-3 * scale)

    # --- clipping/saturation: many samples stuck at the global min/max (ADC rails) ---
    s_min, s_max = float(np.min(sig)), float(np.max(sig))
    span = max(s_max - s_min, 1e-9)
    tol = 1e-3 * span
    clip_fraction = float(
        (np.sum(np.abs(sig - s_max) <= tol) + np.sum(np.abs(sig - s_min) <= tol)) / n
    )
    clipping = clip_fraction > 0.15

    # --- in-band (ECG) vs out-of-band (noise) energy ---
    bp = _filter(sig, fs, [0.5, min(40.0, 0.49 * fs)], "band")
    hf_cut = min(40.0, 0.45 * fs)
    hf = _filter(sig, fs, hf_cut, "highpass")
    bp_rms = float(np.sqrt(np.mean(bp ** 2)))
    hf_rms = float(np.sqrt(np.mean(hf ** 2)))
    noise_ratio = hf_rms / (bp_rms + 1e-9)
    inband_ratio = _robust_ptp(bp) / (robust_ptp + 1e-9)
    noisy = noise_ratio > 0.5
    weak_signal = (not flatline) and inband_ratio < 0.15

    # --- score + verdict ---
    score = 100
    if lead_off:
        score = 0
        reasons.append("Lead-off detected: an electrode is not in proper contact.")
    if flatline:
        score = min(score, 5)
        reasons.append("Flatline / no ECG signal (sensor disconnected or no skin contact).")
    if clipping:
        score -= 40
        if clip_fraction > 0.30:  # severe saturation
            score -= 25
        reasons.append(f"Signal clipping/saturation ({clip_fraction:.0%} of samples at the rails).")
    if noisy:
        score -= 35
        if noise_ratio > 1.0:  # noise dominates the ECG band
            score -= 30
        reasons.append(f"High noise: out-of-band energy is {noise_ratio:.2f}x the ECG band.")
    if weak_signal:
        score -= 30
        reasons.append("Weak ECG content relative to noise/baseline (check electrode contact).")
    score = int(max(0, min(100, score)))

    if lead_off or flatline or score < 40:
        quality = POOR
    elif score < 70:
        quality = ACCEPTABLE
    else:
        quality = GOOD
    if quality == GOOD and not reasons:
        reasons.append("Signal quality looks adequate for single-lead screening.")

    result.update(
        flatline=flatline,
        clipping=clipping,
        noisy=noisy,
        weakSignal=weak_signal,
        quality=quality,
        qualityScore=score,
        usableForClassification=(quality != POOR),
        reasons=reasons,
        metrics={
            "samples": int(n),
            "clipFraction": round(clip_fraction, 4),
            "noiseRatio": round(noise_ratio, 4),
            "inbandRatio": round(inband_ratio, 4),
            "robustPeakToPeak": round(robust_ptp, 4),
        },
    )
    return result
