"""Verify the ESP32 -> /device-ecg telemetry path WITHOUT real hardware.

Replays the exact HTTP request the firmware sends (same JSON shape, same headers,
raw 12-bit ADC integers) against the Flask app's in-process test client, then
confirms GET /device-ecg/latest returns that batch.

Run with the project's .venv:
    .venv\\Scripts\\python.exe scripts\\verify_device_telemetry.py
"""
from __future__ import annotations

import math
import os
import pathlib
import sys

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

SAMPLE_RATE_HZ = 250
BATCH_SAMPLE_COUNT = 750
DEVICE_ID = "esp32-ad8232-demo"


def synth_adc_batch(n: int = BATCH_SAMPLE_COUNT, fs: int = SAMPLE_RATE_HZ) -> list[int]:
    """ECG-like waveform in raw 12-bit ADC counts (0..4095), as the AD8232 +
    ESP32 analogRead() would produce: ~1850 baseline with periodic QRS spikes."""
    samples = []
    rr = int(fs * 0.8)  # ~75 bpm
    for i in range(n):
        phase = i % rr
        v = 1850.0
        if phase < 5:
            v += 900.0 * math.sin(math.pi * phase / 5.0)      # R spike
        elif phase < 10:
            v -= 250.0                                         # S dip
        v += 20.0 * math.sin(2 * math.pi * i / fs)            # slow baseline wander
        samples.append(max(0, min(4095, int(v))))
    return samples


def main() -> int:
    try:
        import app  # backend/app.py
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot import backend app (need the .venv + model files): {exc}")
        return 2

    app.app.config.update(TESTING=True)
    client = app.app.test_client()

    samples = synth_adc_batch()
    # Exactly what the firmware's postBatch() serializes.
    payload = {
        "deviceId": DEVICE_ID,
        "sampleRateHz": SAMPLE_RATE_HZ,
        "leadOff": False,
        "samples": samples,
    }
    headers = {"Content-Type": "application/json"}
    # In a DEVICE_AUTH_ENABLED run, the firmware also sends X-Device-Token.
    token = os.getenv("DEVICE_API_TOKEN")
    if token:
        headers["X-Device-Token"] = token

    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{f' — {detail}' if detail else ''}")

    print(f"POST /device-ecg  (deviceId={DEVICE_ID}, {len(samples)} samples @ {SAMPLE_RATE_HZ} Hz)")
    post = client.post("/device-ecg", json=payload, headers=headers)
    check("backend accepts the batch (HTTP 200)", post.status_code == 200, f"status={post.status_code}")
    if post.status_code != 200:
        print("   body:", post.get_data(as_text=True)[:300])
        return 1

    body = post.get_json()
    check("response has a prediction", bool(body.get("prediction")), repr(body.get("prediction")))
    check("confidence is a 0-100 percentage", isinstance(body.get("confidence"), (int, float)) and 0 <= body["confidence"] <= 100, f"confidence={body.get('confidence')}")
    check("heart rate estimated", body.get("heartRateBpm") is not None, f"HR={body.get('heartRateBpm')}")
    check("multi-beat analysis present", isinstance(body.get("analysis"), dict), "")

    print("GET /device-ecg/latest")
    latest = client.get("/device-ecg/latest")
    check("latest returns 200", latest.status_code == 200, f"status={latest.status_code}")
    ldata = latest.get_json() if latest.status_code == 200 else {}
    check("latest.connected is true", ldata.get("connected") is True)
    check("latest.deviceId matches", ldata.get("deviceId") == DEVICE_ID, ldata.get("deviceId"))
    check("latest.sampleRateHz matches", ldata.get("sampleRateHz") == SAMPLE_RATE_HZ, ldata.get("sampleRateHz"))
    check("latest echoes the full batch", len(ldata.get("ecgData", [])) == BATCH_SAMPLE_COUNT, f"len={len(ldata.get('ecgData', []))}")
    check("latest has a receivedAt timestamp", bool(ldata.get("receivedAt")), ldata.get("receivedAt"))

    print(f"\nDEVICE TELEMETRY VERIFY: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
