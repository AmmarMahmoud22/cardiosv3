"""Demo + sanity check for the live-ECG analysis pipeline.

Generates a CLEAN synthetic ECG at a known heart rate (so we have ground truth)
and verifies the Pan-Tompkins detector recovers the right beat count and rate.
This validates the detection/rhythm stage; classification accuracy still needs
real labelled ECG data.

Run (with the project .venv):
    .venv\\Scripts\\python.exe analysis\\run_ecg_analysis.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
import ecg_analysis as ea  # noqa: E402


def synth_ecg(fs: float, bpm: float, secs: float, seed: int = 0):
    """A simple synthetic ECG: noisy baseline + Gaussian QRS spikes at `bpm`."""
    rng = np.random.default_rng(seed)
    n = int(fs * secs)
    sig = 0.03 * rng.standard_normal(n)                       # measurement noise
    sig += 0.10 * np.sin(2 * np.pi * 0.3 * np.arange(n) / fs)  # baseline wander
    rr = 60.0 / bpm
    centers = (np.arange(rr / 2, secs, rr) * fs).astype(int)
    width = max(int(0.012 * fs), 1)
    for c in centers:
        idx = np.arange(max(0, c - 4 * width), min(n, c + 4 * width))
        sig[idx] += np.exp(-0.5 * ((idx - c) / width) ** 2)   # sharp QRS
    return sig, len(centers)


def main() -> int:
    fs, bpm, secs = 250.0, 75.0, 8.0
    sig, true_beats = synth_ecg(fs, bpm, secs)

    peaks = ea.detect_r_peaks(sig, fs)
    detected = len(peaks)
    hr = round(60.0 / (np.mean(np.diff(peaks)) / fs), 1) if detected >= 2 else 0.0

    print(f"Synthetic ECG: {secs:.0f}s @ {fs:.0f} Hz, set rate = {bpm:.0f} bpm")
    print(f"  ground-truth beats : {true_beats}")
    print(f"  detected beats     : {detected}")
    print(f"  estimated HR       : {hr} bpm  (target {bpm:.0f})")
    ok = abs(detected - true_beats) <= 1 and abs(hr - bpm) <= 5
    print(f"  detector check     : {'PASS' if ok else 'CHECK'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
