"""Live-ECG analysis pipeline: raw sensor signal -> screening FINDINGS.

Bridges the gap between a continuous sensor stream (ESP32 / AD8232) and the
single-beat CNN-LSTM classifier:

  1. band-pass filter  -remove baseline wander + high-frequency noise
  2. R-peak detection  -locate individual heartbeats
  3. segmentation      -cut each beat and resample to the model's 180 samples
  4. classification    -per-beat AAMI type (Normal / PVC / atrial premature / ...)
  5. rhythm analysis   -heart rate + RR-interval regularity
  6. aggregation       -findings + flags (NOT a diagnosis)

IMPORTANT (clinical scope): a single low-cost lead supports screening for rate,
rhythm and ectopic beats. It CANNOT diagnose ischemia/MI or localize conduction
disease -that needs a calibrated 12-lead ECG. Output is screening-level only and
always carries a disclaimer.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt, find_peaks

CATEGORIES = [
    "Normal", "Atrial Premature", "Premature Ventricular Contraction",
    "Fusion of Ventricular and Normal", "Fusion of Paced and Normal",
]
MODEL_TIMESTEPS = 180


def bandpass_filter(raw, fs: float, low: float = 0.5, high: float = 40.0, order: int = 2):
    sig = np.asarray(raw, dtype=float).flatten()
    nyq = 0.5 * fs
    high = min(high, nyq * 0.99)
    if low >= high or sig.size < 12:
        return sig - np.mean(sig)
    b, a = butter(order, [low / nyq, high / nyq], btype="band")
    try:
        return filtfilt(b, a, sig)
    except Exception:
        return sig - np.mean(sig)


def detect_r_peaks(sig, fs: float):
    """Pan-Tompkins-style QRS detection.

    QRS band-pass (5-15 Hz) -> derivative -> squaring -> moving-window
    integration -> adaptive-threshold peak picking with a ~200 ms refractory
    period, then each peak is refined to the local maximum of the raw signal.
    Far more robust to noise / secondary bumps than a plain threshold.
    """
    base = np.asarray(sig, float)
    x = base - np.mean(base)
    nyq = 0.5 * fs

    # 1) QRS-emphasizing band-pass (5-15 Hz)
    lo, hi = 5.0 / nyq, min(15.0, nyq * 0.99) / nyq
    if x.size > 12 and 0 < lo < hi < 1:
        try:
            b, a = butter(1, [lo, hi], btype="band")
            x = filtfilt(b, a, x)
        except Exception:
            pass

    # 2) derivative -> 3) square -> 4) moving-window integration (~150 ms)
    deriv = np.ediff1d(x, to_begin=0.0)
    squared = deriv ** 2
    win = max(int(0.15 * fs), 1)
    integrated = np.convolve(squared, np.ones(win) / win, mode="same")

    # 5) adaptive threshold + refractory distance (~200 ms -> max ~300 bpm)
    distance = max(int(0.2 * fs), 1)
    threshold = np.mean(integrated) + 0.5 * np.std(integrated)
    peaks, _ = find_peaks(integrated, distance=distance, height=threshold)

    # 6) refine each detection to the true R-peak on the raw signal (+-50 ms)
    search = max(int(0.05 * fs), 1)
    refined = []
    for p in peaks:
        s, e = max(0, p - search), min(base.size, p + search + 1)
        if e > s:
            refined.append(s + int(np.argmax(base[s:e])))
    return np.array(sorted(set(refined)), dtype=int)


def segment_beats(sig, rpeaks, fs: float, target_len: int = MODEL_TIMESTEPS):
    """Cut a window around each R-peak and resample to the model length."""
    half = max(int(0.33 * fs), 1)
    beats = []
    for r in rpeaks:
        start, end = r - half, r + half
        if start < 0 or end > len(sig):
            continue
        seg = np.asarray(sig[start:end], dtype=float)
        if seg.size < 2:
            continue
        seg = np.interp(np.linspace(0, seg.size - 1, target_len), np.arange(seg.size), seg)
        beats.append(seg.astype(np.float32))
    return np.array(beats, dtype=np.float32)


_model = None


def _get_model():
    global _model
    if _model is None:
        import os
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
        import tensorflow as tf
        path = Path(__file__).parent / "ECG model" / "ECG_Heart Failure Project_best_model_cnn_lstm.keras"
        _model = tf.keras.models.load_model(str(path), compile=False)
    return _model


def classify_beats(beats):
    """Return [(label, confidence), ...] for an array of segmented beats."""
    if len(beats) == 0:
        return []
    x = beats.reshape(len(beats), MODEL_TIMESTEPS, 1).astype(np.float32)
    # Per-beat min-max scaling to [0, 1] -- MUST match the training-time
    # preprocessing (the MIT-BIH beats the model was trained on are stored in
    # 0..1). Using z-normalization here drops accuracy from ~98% to ~70%
    # (confirmed by analysis/evaluate_ecg_model.py).
    lo = x.min(axis=1, keepdims=True)
    hi = x.max(axis=1, keepdims=True)
    rng = hi - lo
    rng[rng == 0] = 1.0
    x = (x - lo) / rng
    preds = _get_model().predict(x, verbose=0)
    return [(CATEGORIES[int(np.argmax(p))], float(p[int(np.argmax(p))])) for p in preds]


def analyze(raw, fs: float, classify: bool = True, lead_off: bool = False) -> dict:
    """Full pipeline. Returns a screening report (findings + flags + disclaimer)."""
    from signal_quality import assess_quality

    disclaimer = (
        "Screening only (single-lead) - not a diagnosis. Cannot rule out ischemia or "
        "structural heart disease. Confirm with a physician and a clinical 12-lead ECG.")

    # Quality gate before any rhythm/beat analysis: a lead-off, flat, clipped, or
    # noise-dominated trace cannot be screened reliably.
    quality = assess_quality(raw, fs, lead_off=lead_off)
    if not quality["usableForClassification"]:
        return {
            "sampleRateHz": fs,
            "numBeats": 0,
            "signalQuality": quality,
            "qualityOk": False,
            "findings": [
                "Signal quality is too poor for reliable screening ("
                + "; ".join(quality["reasons"]) + "). Re-check electrode contact and retry."
            ],
            "disclaimer": disclaimer,
        }

    sig = bandpass_filter(raw, fs)
    rpeaks = detect_r_peaks(sig, fs)
    report: dict = {
        "sampleRateHz": fs,
        "numBeats": int(len(rpeaks)),
        "signalQuality": quality,
        "qualityOk": True,
    }
    findings: list[str] = []

    if len(rpeaks) >= 2:
        rr = np.diff(rpeaks) / fs
        hr = 60.0 / np.mean(rr) if np.mean(rr) > 0 else 0.0
        cv = float(np.std(rr) / np.mean(rr)) if np.mean(rr) > 0 else 0.0
        report["heartRateBpm"] = round(float(hr), 1)
        report["rrVariability"] = round(cv, 3)
        report["rhythm"] = "irregular" if cv > 0.15 else "regular"

    if classify:
        beats = segment_beats(sig, rpeaks, fs)
        counts: dict[str, int] = {}
        for label, _conf in classify_beats(beats):
            counts[label] = counts.get(label, 0) + 1
        report["beatCounts"] = counts
        report["abnormalBeats"] = sum(v for k, v in counts.items() if k != "Normal")
        if counts.get("Premature Ventricular Contraction", 0):
            findings.append(
                f"{counts['Premature Ventricular Contraction']} ventricular ectopic beat(s) (PVC) detected.")
        if counts.get("Atrial Premature", 0):
            findings.append(f"{counts['Atrial Premature']} atrial premature beat(s) detected.")

    hr = report.get("heartRateBpm")
    if report.get("rhythm") == "irregular":
        findings.append("Irregular rhythm (high RR variability) - possible arrhythmia, review advised.")
    if hr is not None and hr > 100:
        findings.append("Tachycardia (fast heart rate).")
    elif hr is not None and hr < 60:
        findings.append("Bradycardia (slow heart rate).")
    if not findings:
        findings.append("No obvious rate/rhythm/ectopy abnormality in this screening window.")

    report["findings"] = findings
    report["disclaimer"] = disclaimer
    return report
