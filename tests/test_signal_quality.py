"""Tests for backend/signal_quality.py and the inference quality gate.

The pure quality-assessment tests need only numpy/scipy. The gate test needs the
full app (TensorFlow + model) and SKIPs cleanly if unavailable.

    .venv\\Scripts\\python.exe -m pytest tests/test_signal_quality.py -q
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

try:
    from signal_quality import assess_quality
    _DEPS = True
except ImportError:
    _DEPS = False

FS = 250


def _good_ecg(seconds: float = 3.0, fs: int = FS):
    t = np.arange(0, seconds, 1 / fs)
    # baseline + periodic narrow QRS-like spikes, light noise
    spikes = np.maximum(0, np.sin(2 * np.pi * 1.25 * t)) ** 8
    return 1850 + 800 * spikes + 8 * np.random.RandomState(0).randn(t.size)


def test_good_signal_is_usable():
    if not _DEPS:
        print("SKIP"); return
    q = assess_quality(_good_ecg(), FS)
    assert q["quality"] == "good"
    assert q["usableForClassification"] is True
    assert q["leadOff"] is False and q["flatline"] is False


def test_lead_off_is_poor():
    if not _DEPS:
        print("SKIP"); return
    q = assess_quality(_good_ecg(), FS, lead_off=True)
    assert q["leadOff"] is True
    assert q["quality"] == "poor"
    assert q["usableForClassification"] is False


def test_flatline_is_poor():
    if not _DEPS:
        print("SKIP"); return
    q = assess_quality(np.full(FS * 3, 2048.0), FS)
    assert q["flatline"] is True
    assert q["usableForClassification"] is False


def test_severe_clipping_is_poor():
    if not _DEPS:
        print("SKIP"); return
    clipped = np.clip(_good_ecg() * 4 - 3000, 0, 4095)  # rails hard
    q = assess_quality(clipped, FS)
    assert q["clipping"] is True
    assert q["usableForClassification"] is False


def test_heavy_noise_is_poor():
    if not _DEPS:
        print("SKIP"); return
    t = np.arange(0, 3, 1 / FS)
    noisy = 1850 + 600 * (np.maximum(0, np.sin(2 * np.pi * 1.25 * t)) ** 8) \
        + 1500 * np.random.RandomState(2).randn(t.size)
    q = assess_quality(noisy, FS)
    assert q["noisy"] is True
    assert q["usableForClassification"] is False


def test_too_short_is_poor():
    if not _DEPS:
        print("SKIP"); return
    q = assess_quality([1, 2, 3, 4], FS)
    assert q["tooShort"] is True
    assert q["usableForClassification"] is False


def test_metrics_present():
    if not _DEPS:
        print("SKIP"); return
    q = assess_quality(_good_ecg(), FS)
    for key in ("clipFraction", "noiseRatio", "inbandRatio", "robustPeakToPeak"):
        assert key in q["metrics"]


def test_build_prediction_gate_flags_poor_signal():
    """A flat trace must NOT yield a confident class through the real endpoint path."""
    try:
        import ecg_service
    except Exception:  # noqa: BLE001 - no TF/model here
        print("SKIP (ecg_service unavailable)"); return
    if ecg_service.model is None:
        print("SKIP (model not loaded)"); return

    flat = [2048.0] * (FS * 3)
    resp = ecg_service.build_prediction_response(flat, FS, device_id="t")
    assert resp["qualityOk"] is False
    assert resp["confidence"] is None
    assert "Inconclusive" in resp["prediction"]
    assert resp["signalQuality"]["flatline"] is True

    good = _good_ecg().tolist()
    resp2 = ecg_service.build_prediction_response(good, FS, device_id="t")
    assert resp2["qualityOk"] is True
    assert isinstance(resp2["confidence"], (int, float))


def _main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fails = 0
    for t in tests:
        try:
            t(); print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            fails += 1; print(f"FAIL {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - fails}/{len(tests)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(_main())
