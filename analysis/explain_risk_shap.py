"""SHAP-style feature attribution for the heart-failure risk model (XGBoost).

Uses XGBoost's *exact* tree SHAP values via booster.predict(pred_contribs=True)
— no extra dependency. Shows which health factors pushed a patient's predicted
risk UP (red) or DOWN (green): the interpretability a committee will ask for.

Run (with the project .venv):
    .venv\\Scripts\\python.exe analysis\\explain_risk_shap.py
Output: analysis/outputs/risk_shap_sample.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import xgboost as xgb

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
import risk_model as rm  # noqa: E402  (flask-free)

OUT = REPO / "analysis" / "outputs"

# A deliberately high-risk example patient.
SAMPLE = {
    "BMI": 31.2, "Smoking": "Yes", "AlcoholDrinking": "No", "Stroke": "Yes",
    "PhysicalHealth": 12, "MentalHealth": 8, "DiffWalking": "Yes", "Sex": "Male",
    "AgeCategory": "70-74", "Race": "White", "Diabetic": "Yes",
    "PhysicalActivity": "No", "GenHealth": "Poor", "SleepTime": 5,
    "Asthma": "Yes", "KidneyDisease": "No", "SkinCancer": "No",
}


def build_features(data: dict):
    """Run the exact risk_model preprocessing and return (feature_names, scaled_row)."""
    rm.load_artifacts()
    df = pd.DataFrame([data])
    df["AgeCategory"] = df["AgeCategory"].map(
        {age: i for i, age in enumerate(rm.valid_options["AgeCategory"])})
    for col in ["Smoking", "AlcoholDrinking", "Stroke", "DiffWalking", "Sex",
                "PhysicalActivity", "Asthma", "KidneyDisease", "SkinCancer"]:
        if col in rm.label_encoders:
            df[col] = rm.label_encoders[col].transform(df[col])
    nominal = ["Race", "Diabetic", "GenHealth"]
    ohe = rm.one_hot_encoder.transform(df[nominal])
    ohe_df = pd.DataFrame(ohe, columns=rm.one_hot_encoder.get_feature_names_out(nominal))
    df = pd.concat([df.drop(nominal, axis=1), ohe_df], axis=1).reindex(
        columns=rm.expected_feature_names, fill_value=0)
    return rm.expected_feature_names, rm.scaler.transform(df)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    names, X = build_features(SAMPLE)

    booster = rm.model.get_booster()
    contribs = booster.predict(xgb.DMatrix(X), pred_contribs=True)[0]  # last entry = bias
    feat_contribs = contribs[:-1]

    order = np.argsort(np.abs(feat_contribs))[::-1][:12]
    top_names = [names[i] for i in order]
    top_vals = [float(feat_contribs[i]) for i in order]
    colors = ["#d62728" if v > 0 else "#2ca02c" for v in top_vals]

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(range(len(top_vals)), top_vals, color=colors)
    ax.set_yticks(range(len(top_vals)))
    ax.set_yticklabels(top_names)
    ax.invert_yaxis()
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("SHAP contribution   (→ pushes risk HIGHER / ← LOWER)")
    pred = int(rm.model.predict(X)[0])
    ax.set_title(f"Risk drivers — prediction: {'High' if pred == 1 else 'Low'} cardiac risk profile")
    fig.tight_layout()
    out = OUT / "risk_shap_sample.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)

    print("Top risk drivers for the sample patient:")
    for name, val in zip(top_names, top_vals):
        arrow = "[+] raises" if val > 0 else "[-] lowers"
        print(f"  {arrow:11s} {name}: {val:+.3f}")
    print(f"saved {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
