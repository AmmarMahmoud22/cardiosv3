"""Grad-CAM explainability for the ECG CNN-LSTM model.

Produces a heatmap over the ECG trace showing WHICH parts of the signal drove
the model's classification — the "why" visual a cardiologist (and a graduation
committee) wants to see, instead of a black-box label.

Run (with the project .venv):
    .venv\\Scripts\\python.exe analysis\\explain_ecg_gradcam.py
Outputs: analysis/outputs/gradcam_<sample>.png
"""
from __future__ import annotations

import os
import re
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import numpy as np
import matplotlib

matplotlib.use("Agg")  # headless: save figures, no display
import matplotlib.pyplot as plt
import tensorflow as tf

REPO = Path(__file__).resolve().parents[1]
MODEL_PATH = REPO / "backend" / "ECG model" / "ECG_Heart Failure Project_best_model_cnn_lstm.keras"
SAMPLES_DIR = REPO / "backend" / "ECG model"
OUT = REPO / "analysis" / "outputs"

# Same 5 AAMI classes the model was trained on (MIT-BIH style).
CATEGORIES = [
    "Normal", "Atrial Premature", "Premature Ventricular Contraction",
    "Fusion of Ventricular and Normal", "Fusion of Paced and Normal",
]
TARGET_LAYER = "conv1d_2"   # last Conv1D before the LSTM stack
MODEL_TIMESTEPS = 180


def load_samples(path: Path) -> np.ndarray:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return np.array([float(x) for x in re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", text)], dtype=np.float32)


def preprocess(raw: np.ndarray):
    """Mirror backend/ecg_service.py: interpolate to 180 samples, reshape, z-normalize."""
    raw = np.asarray(raw, np.float32).flatten()
    positions = np.linspace(0, raw.size - 1, raw.size)
    targets = np.linspace(0, raw.size - 1, MODEL_TIMESTEPS)
    sig = np.interp(targets, positions, raw).astype(np.float32)
    x = sig.reshape(1, MODEL_TIMESTEPS, 1)
    std = x.std() or 1.0
    return sig, (x - x.mean()) / std


def grad_cam(model, x, class_idx: int) -> np.ndarray:
    """1D Grad-CAM on the last conv layer, upsampled to the signal length.

    The saved model is Sequential, whose symbolic outputs aren't directly
    tappable in Keras 3, so we re-run its layers functionally on a fresh Input
    (reusing the same weights) to expose the target conv output.
    """
    inputs = tf.keras.Input(shape=x.shape[1:])
    h = inputs
    conv_output = None
    for layer in model.layers:
        h = layer(h)
        if layer.name == TARGET_LAYER:
            conv_output = h
    grad_model = tf.keras.Model(inputs, [conv_output, h])
    with tf.GradientTape() as tape:
        conv_out, preds = grad_model(x)
        score = preds[:, class_idx]
    grads = tape.gradient(score, conv_out)                 # (1, T, C)
    weights = tf.reduce_mean(grads, axis=1)                # (1, C) channel importance
    cam = tf.reduce_sum(conv_out * weights[:, None, :], axis=-1)[0]   # (T,)
    cam = tf.nn.relu(cam).numpy()
    cam = cam / (cam.max() + 1e-8)
    return np.interp(np.linspace(0, len(cam) - 1, MODEL_TIMESTEPS), np.arange(len(cam)), cam)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    model = tf.keras.models.load_model(str(MODEL_PATH), compile=False)
    csvs = [c for c in sorted(SAMPLES_DIR.glob("*.csv")) if "_processed" not in c.name]
    if not csvs:
        print("No sample CSVs found in 'backend/ECG model/'")
        return 1
    for csv in csvs:
        raw = load_samples(csv)
        if raw.size == 0:
            continue
        sig, x = preprocess(raw)
        preds = model.predict(x, verbose=0)[0]
        idx = int(np.argmax(preds))
        conf = float(preds[idx])
        cam = grad_cam(model, x, idx)

        fig, ax = plt.subplots(figsize=(11, 4))
        t = np.arange(MODEL_TIMESTEPS)
        ax.plot(t, sig, color="black", lw=1.3, zorder=3, label="ECG (length-normalized)")
        ax.scatter(t, sig, c=cam, cmap="jet", s=18, zorder=4)
        sm = plt.cm.ScalarMappable(cmap="jet")
        sm.set_array(cam)
        fig.colorbar(sm, ax=ax, label="Grad-CAM importance")
        ax.set_title(f"{csv.name}  →  {CATEGORIES[idx]}  ({conf:.1%})")
        ax.set_xlabel("sample index")
        ax.set_ylabel("amplitude")
        ax.legend(loc="upper right")
        fig.tight_layout()
        out = OUT / f"gradcam_{csv.stem}.png"
        fig.savefig(out, dpi=130)
        plt.close(fig)
        print(f"{csv.name}: {CATEGORIES[idx]} ({conf:.1%})  ->  {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
