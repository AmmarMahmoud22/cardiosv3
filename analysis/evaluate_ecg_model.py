"""Quantitative evaluation of the ECG CNN-LSTM on the MIT-BIH test set.

Produces the numbers a committee asks for: overall accuracy, per-class
precision / recall / F1, macro & weighted averages, and a confusion-matrix
figure. Also reports the severe class imbalance so accuracy isn't read naively.

The model was trained on 187-sample beats, so we evaluate at native length. Two
input normalizations are tried (raw 0-1 as stored in the dataset, and per-beat
z-score); the better one is reported as the headline — which also reveals the
preprocessing the model was trained with.

Run (with the project .venv):
    .venv\\Scripts\\python.exe analysis\\evaluate_ecg_model.py [path\\to\\mitbih_test.csv]
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
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score)

REPO = Path(__file__).resolve().parents[1]
MODEL_PATH = REPO / "backend" / "ECG model" / "ECG_Heart Failure Project_best_model_cnn_lstm.keras"
OUT = REPO / "analysis" / "outputs"
CLASSES = ["Normal", "Atrial Premature", "PVC", "Fusion V+N", "Fusion Paced+N"]


def find_data() -> Path | None:
    if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
        return Path(sys.argv[1])
    candidates = [
        REPO / "data" / "mitbih_test.csv",
        REPO.parents[2] / "data" / "mitbih_test.csv",        # main repo (worktree is nested)
        Path(r"D:/Final Project/cardios/data/mitbih_test.csv"),
    ]
    return next((c for c in candidates if c.exists()), None)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    data = find_data()
    if data is None:
        print("mitbih_test.csv not found — pass its path as an argument.")
        return 1
    print(f"data: {data}")

    df = pd.read_csv(data, header=None)
    X = df.iloc[:, :187].values.astype("float32")
    y = df.iloc[:, 187].astype(int).values
    print(f"loaded {len(y)} beats; class counts = {np.bincount(y).tolist()}\n")

    model = tf.keras.models.load_model(str(MODEL_PATH), compile=False)

    def prep(mode: str):
        x = X.copy()
        if mode == "znorm":
            mu = x.mean(axis=1, keepdims=True)
            sd = x.std(axis=1, keepdims=True)
            sd[sd == 0] = 1.0
            x = (x - mu) / sd
        return x.reshape(len(x), 187, 1)

    best = None
    for mode in ("native", "znorm"):
        yhat = model.predict(prep(mode), verbose=0, batch_size=512).argmax(1)
        acc = accuracy_score(y, yhat)
        mf1 = f1_score(y, yhat, average="macro")
        print(f"  preprocessing={mode:6s}  accuracy={acc:.4f}  macro-F1={mf1:.4f}")
        if best is None or acc > best[2]:
            best = (mode, yhat, acc, mf1)

    mode, yhat, acc, mf1 = best
    print(f"\n=== headline (preprocessing = {mode}) ===")
    print(f"Accuracy = {acc:.4f}   Macro-F1 = {mf1:.4f}\n")
    print(classification_report(y, yhat, target_names=CLASSES, digits=3, zero_division=0))

    cm = confusion_matrix(y, yhat)
    cmn = cm.astype(float) / cm.sum(axis=1, keepdims=True).clip(min=1)
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    im = ax.imshow(cmn, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(5))
    ax.set_yticks(range(5))
    ax.set_xticklabels(CLASSES, rotation=45, ha="right")
    ax.set_yticklabels(CLASSES)
    for i in range(5):
        for j in range(5):
            ax.text(j, i, f"{cm[i, j]}\n{cmn[i, j]:.0%}", ha="center", va="center",
                    color="white" if cmn[i, j] > 0.5 else "black", fontsize=8)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(f"ECG CNN-LSTM — Confusion Matrix (acc={acc:.1%}, macro-F1={mf1:.2f})")
    fig.colorbar(im, ax=ax, label="row-normalized")
    fig.tight_layout()
    out = OUT / "confusion_matrix.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"saved {out.relative_to(REPO)}")

    counts = np.bincount(y)
    total = counts.sum()
    print("\nClass imbalance: " + ", ".join(
        f"{CLASSES[i]} {counts[i] / total:.1%}" for i in range(len(counts))))
    print("=> Normal dominates; report macro-F1 and per-class recall, not raw accuracy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
