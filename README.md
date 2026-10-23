# Cardios

`Cardios` is one cardiac clinical software platform with three intelligence layers:

| Layer | What it does | Source |
|---|---|---|
| **Heart-Risk Intelligence** | Estimates cardiac risk from structured health information | Kaggle *Personal Key Indicators of Heart Disease* dataset |
| **ECG Intelligence** | Classifies ECG traces and analyses rhythm | MIT-BIH Arrhythmia Database (AAMI 5-class) |
| **Clinical Evidence Intelligence** | Answers clinical questions from official guidelines, with traceable citations and a refusal when evidence is insufficient | 2021 ESC Heart Failure Guidelines (*Eur Heart J* 2021;42:3599–3726) |

A risk score or an ECG finding raises a clinical question; the evidence layer answers
it from published guidance with a citation you can open and check. Model outputs may
provide *context* for a question, but they are never a *source* for a recommendation —
that separation is enforced in the type system, not just in wording.

The app also lets you:
- analyze ECG `.csv` files
- receive live ECG batches from an `ESP32 + AD8232` prototype (optional; no hardware
  is needed for the risk, ECG-file, or evidence features)
- review previous results and monitoring data

## ⚠️ Medical scope & limitations

Cardios is a **monitoring / risk-support and educational tool — not a diagnostic
device**. Its outputs are automated screening estimates and can be wrong.

- ECG capture is **single-lead** (AD8232): it can screen heart rate, rhythm
  regularity, and ectopic beats, but **cannot** detect ischemia / heart attack or
  replace a clinical **12-lead** ECG read by a physician.
- Every result carries a disclaimer, and a **signal-quality gate**
  (`backend/signal_quality.py`) runs before inference — lead-off, flatline,
  clipping, and noisy traces are **flagged and left unclassified** rather than
  given a confident label.
- Always consult a qualified clinician. For chest pain, fainting, or
  breathlessness, seek emergency care.

## What you need first (Windows)

Install these once:
- **Python 3.11** — during installation enable **"Add Python to PATH"**
- **Node.js 18+**

After installing, close and reopen PowerShell (or restart the computer once if
`py` / `npm` are still not recognized).

## First-time setup

Open **PowerShell inside the project folder** and run these one by one:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
npm install
Copy-Item .env.example .env
```

Notes:
- If `Activate.ps1` is blocked with an execution-policy error, run this once and
  retry: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
- `pip install` downloads TensorFlow (~500 MB) — the first install takes several
  minutes on a normal connection. That is expected.
- `.env` works out of the box for a local demo. Supabase keys (login/history)
  and security toggles are documented inside the file.

## Run the app

You need **2 PowerShell windows**, both opened in the project folder.

### Window 1 — backend

```powershell
.venv\Scripts\Activate.ps1
python backend\app.py
```

Wait until the model loads (first start takes ~20–60 s). Then verify it is up by
opening <http://localhost:49232/health> — you should see `{"status":"ok", ...}`.
Leave this window open.

### Window 2 — frontend

```powershell
npm run dev -- --host 127.0.0.1 --port 5176 --strictPort
```

Leave this window open too, then open the app:

**<http://127.0.0.1:5176/>**

## Clinical Evidence Advisor

The evidence layer needs a guideline corpus. Ingest one once:

```powershell
.venv\Scripts\python.exe -m rag.ingest "<guideline.pdf>" --title "2021 ESC Guidelines for the diagnosis and treatment of acute and chronic heart failure" --id esc-hf-2021
# Review backend\rag\corpus\reports\esc-hf-2021_verification_sample.md before continuing:
# at least 19 of 20 sampled chunks must carry the correct document, page and section.
.venv\Scripts\python.exe -m rag.index
```

Then open **Evidence Advisor** in the app. It shows the retrieved guideline passages —
with score, document, section, page and evidence ID — *before* generating anything,
and refuses when the retrieved evidence is too weak to answer safely.

Full module documentation: [backend/rag/README.md](backend/rag/README.md).

## Verify everything works (optional but recommended)

```powershell
# backend test suite (54 tests)
.venv\Scripts\python.exe -m pytest tests\ -q

# frontend build + lint
npm run build
npm run lint
```

## Optional: live ESP32 ECG mode

If you are using the `ESP32 + AD8232` device prototype:
- keep the backend running (it listens on all interfaces by default)
- keep the backend computer and every ESP32 on the same Wi-Fi network
- the backend advertises `_cardios._tcp.local.` over mDNS, so the ESP32 discovers
  the current API address without storing the computer's IP
- every ESP32 derives a unique device ID from its Wi-Fi MAC address; use the
  device selector in `Live device mode` when several devices have sent data
- the sketch and wiring guide are in
  [hardware/esp32-ad8232](hardware/esp32-ad8232/README.md)

No hardware? Simulate the device against the **running** backend — the Live
device panel in the app will behave exactly as with a real ESP32:

```powershell
.venv\Scripts\python.exe scripts\simulate_device.py     # Ctrl+C to stop
```

(There is also `scripts\verify_device_telemetry.py`, a one-shot self-check of
the telemetry path that does not need the server to be running.)

## Stop the app

Press `Ctrl + C` in each PowerShell window.

## If something does not work

| Symptom | Fix |
|---|---|
| `py -3.11` not recognized | Python 3.11 is not installed (or PATH was not added). Reinstall with "Add to PATH". |
| `npm` not recognized | Node.js is not installed correctly. |
| `Activate.ps1` blocked | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry. |
| Backend window shows port error | Another process is using 49232. Find and stop it: `Get-NetTCPConnection -LocalPort 49232 \| Select OwningProcess`, then `Stop-Process -Id <pid>`. (The frontend expects port 49232.) |
| Page does not open | Make sure **both** PowerShell windows are still running, and check <http://localhost:49232/health>. |
| Login fails | The app needs the Supabase keys in `.env` (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`). For an offline demo set `VITE_USE_LOCAL_HEALTH_STORE=true` instead. |
| ESP32 sends nothing | Keep the ESP32 and laptop on the same non-guest Wi-Fi. If Serial Monitor prints `Cardios API not found`, check that multicast/client communication is allowed. Or use the simulator script above. |

## Project documentation

| Topic | File |
|---|---|
| Demo checklist (manual QA) | [docs/DEMO_CHECKLIST.md](docs/DEMO_CHECKLIST.md) |
| Final submission checklist | [docs/FINAL_SUBMISSION_CHECKLIST.md](docs/FINAL_SUBMISSION_CHECKLIST.md) |
| Handoff for another AI/model | [docs/MODEL_HANDOFF.md](docs/MODEL_HANDOFF.md) |
| Supabase doctor/patient demo setup | [docs/SUPABASE_DEMO_SETUP.md](docs/SUPABASE_DEMO_SETUP.md) |
| Presentation script | [docs/PRESENTATION_SCRIPT.md](docs/PRESENTATION_SCRIPT.md) |
| Committee Q&A | [docs/PROFESSOR_QA.md](docs/PROFESSOR_QA.md) |
| AI validation & metrics | [docs/AI_VALIDATION.md](docs/AI_VALIDATION.md) |
| Model cards | [docs/MODEL_CARD_ECG.md](docs/MODEL_CARD_ECG.md) · [docs/MODEL_CARD_RISK.md](docs/MODEL_CARD_RISK.md) |
| Scaling plan | [docs/SCALING.md](docs/SCALING.md) |
| Architecture diagrams | [ARCHITECTURE.md](ARCHITECTURE.md) |
