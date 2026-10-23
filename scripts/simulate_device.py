"""Live ESP32 simulator for demos — no hardware needed.

POSTs ECG-like batches over real HTTP to a RUNNING backend, exactly like the
firmware (same JSON shape, same cadence: 750 samples @ 250 Hz every 3 s), so the
app's "Live device mode" panel updates as if a real device were attached.

Start the backend first (python backend\\app.py), then:

    .venv\\Scripts\\python.exe scripts\\simulate_device.py
    .venv\\Scripts\\python.exe scripts\\simulate_device.py --lead-off   # demo poor signal

Ctrl+C to stop (the app will show "Device offline" ~15 s later).
Only the stdlib is used — no extra dependencies.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
import urllib.error
import urllib.request

SAMPLE_RATE_HZ = 250
BATCH_SAMPLE_COUNT = 750          # 3 seconds of signal, like the firmware
DEVICE_ID = "esp32-sim"


def synth_adc_batch(t0: int, lead_off: bool) -> list[int]:
    """ECG-like waveform in raw 12-bit ADC counts (0..4095), continuing from
    sample index t0 so consecutive batches form one continuous signal."""
    samples = []
    rr = int(SAMPLE_RATE_HZ * 0.8)  # ~75 bpm
    for k in range(BATCH_SAMPLE_COUNT):
        i = t0 + k
        if lead_off:
            # Electrode detached: near-flat noise floor.
            samples.append(1850 + random.randint(-8, 8))
            continue
        phase = i % rr
        v = 1850.0
        if phase < 5:
            v += 900.0 * math.sin(math.pi * phase / 5.0)   # R spike
        elif phase < 10:
            v -= 250.0                                      # S dip
        v += 20.0 * math.sin(2 * math.pi * i / SAMPLE_RATE_HZ)  # baseline wander
        v += random.gauss(0, 6)                             # sensor noise
        samples.append(max(0, min(4095, int(v))))
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:49232/device-ecg")
    parser.add_argument("--lead-off", action="store_true",
                        help="simulate a detached electrode (poor signal)")
    parser.add_argument("--interval", type=float, default=3.0)
    args = parser.parse_args()

    headers = {"Content-Type": "application/json"}
    token = os.getenv("DEVICE_API_TOKEN")
    if token:
        headers["X-Device-Token"] = token

    print(f"Posting batches to {args.url} every {args.interval:g}s (Ctrl+C to stop)")
    t0, sent = 0, 0
    while True:
        payload = {
            "deviceId": DEVICE_ID,
            "sampleRateHz": SAMPLE_RATE_HZ,
            "leadOff": bool(args.lead_off),
            "samples": synth_adc_batch(t0, args.lead_off),
        }
        request = urllib.request.Request(
            args.url, data=json.dumps(payload).encode(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=10) as resp:
                body = json.loads(resp.read().decode())
                sent += 1
                print(f"  #{sent}  {resp.status}  prediction={body.get('prediction')!r}  "
                      f"confidence={body.get('confidence')}  HR={body.get('heartRateBpm')}")
        except urllib.error.URLError as exc:
            print(f"  cannot reach the backend ({exc}). Is it running on port 49232?")
        t0 += BATCH_SAMPLE_COUNT
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nstopped.")
        sys.exit(0)
