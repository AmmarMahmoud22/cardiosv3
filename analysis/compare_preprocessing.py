"""Visual before/after proof of the preprocessing discovery.

Produces a side-by-side confusion-matrix figure comparing the WRONG deployment
preprocessing (z-normalization) against the CORRECT one (min-max 0..1, matching
training). This is the figure to show the committee: it demonstrates that the
quantitative evaluation did not merely report a number, it uncovered and fixed a
real defect.

Run (with the project .venv):
    .venv\\Scripts\\python.exe analysis\\compare_preprocessing.py [path\\to\\mitbih_test.csv]
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import tensorflow as tf
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

REPO = Path(__file__).resolve().parents[1]
MODEL_PATH = REPO / "backend" / "ECG model" / "ECG_Heart Failure Project_best_model_cnn_lstm.keras"
OUT = REPO / "analysis" / "outputs"
CLASSES = ["Normal", "Atrial Prem.", "PVC", "Fusion V+N", "Paced+N"]


def find_data() -> Path | None:
    if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
        return Path(sys.argv[1])
    for c in [REPO / "data" / "mitbih_test.csv",
              Path(r"D:/Final Project/cardios/data/mitbih_test.csv")]:
        if c.exists():
            return c
    return None


def minmax(a):
    lo = a.min(axis=1, keepdims=True)
    rng = a.max(axis=1, keepdims=True) - lo
    rng[rng == 0] = 1.0
    return (a - lo) / rng


def znorm(a):
    mu = a.mean(axis=1, keepdims=True)
    sd = a.std(axis=1, keepdims=True)
    sd[sd == 0] = 1.0
    return (a - mu) / sd


def panel(ax, cm, title):
    cmn = cm.astype(float) / cm.sum(axis=1, keepdims=True).clip(min=1)
    im = ax.imshow(cmn, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(5)); ax.set_yticks(range(5))
    ax.set_xticklabels(CLASSES, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(CLASSES, fontsize=8)
    for i in range(5):
        for j in range(5):
            ax.text(j, i, f"{cmn[i, j]:.0%}", ha="center", va="center",
                    color="white" if cmn[i, j] > 0.5 else "black", fontsize=8)
    ax.set_xlabel("Predicted"); ax.set_ylabel("True")
    ax.set_title(title, fontsize=11)
    return im


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    data = find_data()
    if data is None:
        print("mitbih_test.csv not found - pass its path as an argument.")
        return 1

    df = pd.read_csv(data, header=None)
    X = df.iloc[:, :187].values.astype("float32")
    y = df.iloc[:, 187].astype(int).values
    model = tf.keras.models.load_model(str(MODEL_PATH), compile=False)

    # Simulate a real sensor at a different scale/offset (ADC-like) so the
    # comparison reflects deployment, not the already-normalized dataset.
    Xs = X * 350.0 + 1700.0

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6))
    results = {}
    for ax, (name, fn) in zip(axes, [("z-normalization (OLD - deployment bug)", znorm),
                                     ("min-max 0..1 (FIX - matches training)", minmax)]):
        yhat = model.predict(fn(Xs).reshape(len(X), 187, 1), verbose=0, batch_size=512).argmax(1)
        acc = accuracy_score(y, yhat); mf1 = f1_score(y, yhat, average="macro")
        results[name] = (acc, mf1)
        panel(ax, confusion_matrix(y, yhat), f"{name}\nacc={acc:.1%} | macro-F1={mf1:.2f}")

    fig.suptitle("Effect of Preprocessing on the ECG CNN-LSTM (sensor-scaled input)",
                 fontsize=13, fontweight="bold")
    fig.colorbar(axes[1].images[0], ax=axes, label="row-normalized", fraction=0.04)
    out = OUT / "preprocessing_comparison.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out.relative_to(REPO)}")
    for k, (a, f) in results.items():
        print(f"  {k:42s} acc={a:.4f} macro-F1={f:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
