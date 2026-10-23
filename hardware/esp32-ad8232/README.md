# ESP32 AD8232 Live ECG Prototype

This folder contains the first live-device prototype for `Cardios`.

## What It Does

The ESP32:
- reads the `AD8232 OUTPUT` signal from `GPIO34`
- samples at `250 Hz`
- batches `750 samples` (~3 s per batch)
- detects lead-off (electrode detached) on `LO+ / LO-`
- connects to Wi-Fi with a bounded timeout and auto-reconnects if the link drops
  (it never blocks forever waiting for the network)
- sends each batch over Wi-Fi as JSON to:

```text
POST /device-ecg
Content-Type: application/json
X-Device-Token: <token>        # only when DEVICE_TOKEN is configured

{
  "deviceId": "cardios-aabbccddeeff",
  "sampleRateHz": 250,
  "leadOff": false,
  "samples": [ 1843, 1850, ... ]   // 750 raw 12-bit ADC values (0..4095)
}
```

> Note: the ESP32 radio is **2.4 GHz only** — connect it to a 2.4 GHz SSID, not 5 GHz.

The Cardios backend then:
- advertises `_cardios._tcp.local.` on the local network
- normalizes the batch to the ECG model input length
- runs the ECG classifier
- stores per-device readings in the SQLite-backed ECG store

The Cardios frontend ECG page then:
- polls `GET /device-ecg/latest`
- displays the latest waveform
- shows classification, confidence, lead status, and timing

## Wiring Used By The Sketch

```text
AD8232    -> ESP32
3.3V      -> 3V3
GND       -> GND
OUTPUT    -> GPIO34
LO+       -> GPIO26
LO-       -> GPIO27
SDN       -> 3V3
```

## Before Uploading

Open:

[esp32-ad8232.ino](./esp32-ad8232.ino)

Set `WIFI_SSID` and `WIFI_PASSWORD` to the shared 2.4 GHz Wi-Fi network. Keep
real credentials local and do not commit them.

Set `DEVICE_TOKEN` only if the server runs with `DEVICE_AUTH_ENABLED=true`; it
  must match the server's `DEVICE_API_TOKEN`. For an unauthenticated local demo,
leave `YOUR_DEVICE_TOKEN` as-is and the sketch won't send the header.

The API address is not stored in the sketch. After joining Wi-Fi, the ESP32
discovers the Cardios backend over mDNS.

## How To Run The Cardios Backend For ESP32 Access

Use:

```bash
./run_app.sh
```

The project now binds the backend to `0.0.0.0`, so devices on the same Wi-Fi network can reach it.

## Arduino IDE Notes

In Arduino IDE:
1. Install the `ESP32` board package if you have not already.
2. Select your ESP32 board.
3. Select the correct COM / serial port.
4. Paste or open the sketch.
5. Upload it.
6. Open `Serial Monitor` at `115200`.

## What You Should See

In Serial Monitor:
- Wi-Fi connection logs (with dots while connecting; a retry message if it times out)
- the ESP32 local IP once connected
- a unique `cardios-...` device ID
- `Cardios API discovered` followed by the current backend address
- a `POST status` line after each batch (200 = the backend accepted it), then the
  server's JSON response
- raw ECG numbers scrolling **only if** you set `STREAM_TO_SERIAL_PLOTTER 1` in the
  sketch (off by default so printing doesn't add timing jitter at 250 Hz)

In Cardios:
- open the ECG page
- switch to `Live device mode`
- select the device ID when more than one ESP32 is available
- after the first batch arrives, the waveform and prediction panel should update

If Serial Monitor prints `Cardios API not found`, confirm that the backend and
ESP32 are on the same Wi-Fi. Guest networks and access points with multicast or
client isolation enabled can block mDNS discovery.

## Clinical Scope & Single-Lead Limitations

Cardios is a **monitoring / risk-support tool, not a diagnostic device**, and the
AD8232 is a **single-lead** front end. Be explicit about what that can and cannot do:

**Can support (screening only):**
- heart-rate estimation
- rhythm regularity (RR-interval variability)
- detection of ectopic beats (e.g. PVCs / premature beats)

**Cannot do (needs a clinical 12-lead ECG + a physician):**
- diagnose ischemia, a heart attack (MI), or ST-segment changes
- localize conduction disease or chamber enlargement
- replace a clinician's interpretation

**Signal-quality reality:** a single dry-electrode lead is easily corrupted by
lead-off (electrode detached), motion/EMG noise, mains hum, and ADC clipping. The
backend runs a **signal-quality gate before inference** (`backend/signal_quality.py`):
lead-off, flatline, clipping, and noise are measured, and a poor-quality trace is
**flagged and left unclassified** instead of producing a confident but meaningless
label. Re-seat the electrodes and keep still if you see a poor-quality warning.

## Safety

This is a battery-powered prototype only.

- do not use it as a medical device
- avoid mains-powered connections while electrodes are attached
- use caution when attaching body electrodes
- never rely on it for diagnosis or emergency decisions — seek professional care for symptoms
