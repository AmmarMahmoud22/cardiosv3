"""WAT framework tests.

Runs with pytest *or* standalone: ``python tests/test_wat.py``.

Coverage:
- contracts validate / reject bad input (schema gate),
- the engine runs a fully green pipeline end to end (state + telemetry written),
- the engine classifies a missing-dependency failure and continues,
- a wrapped tool returns exactly what the underlying backend function returns
  (proves "wrap, don't reimplement"),
- reference resolution and unknown-tool handling.
"""
from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from pydantic import ValidationError  # noqa: E402

from wat import registry  # noqa: E402
from wat.engine import _resolve, run_workflow  # noqa: E402
from wat.errors import WatError, classify_exception  # noqa: E402
from wat.paths import ensure_backend_on_path  # noqa: E402

EXPECTED_TOOLS = {
    "read_ecg_device", "normalize_ecg_csv", "classify_ecg",
    "predict_heart_failure_risk", "get_health_advice", "persist_result",
}

VALID_RISK = {
    "BMI": 28.5, "Smoking": "Yes", "AlcoholDrinking": "No", "Stroke": "No",
    "PhysicalHealth": 5, "MentalHealth": 3, "DiffWalking": "No", "Sex": "Male",
    "AgeCategory": "60-64", "Race": "White", "Diabetic": "Yes",
    "PhysicalActivity": "Yes", "GenHealth": "Fair", "SleepTime": 6,
    "Asthma": "No", "KidneyDisease": "No", "SkinCancer": "No",
}


def test_registry_lists_all_tools():
    names = set(registry.all_tools())
    assert EXPECTED_TOOLS <= names, f"missing tools: {EXPECTED_TOOLS - names}"


def test_unknown_tool_raises_dependency():
    try:
        registry.get("does_not_exist")
    except WatError as exc:
        assert exc.category == "dependency"
    else:
        raise AssertionError("expected WatError for unknown tool")


def test_contract_rejects_bad_input():
    classify = registry.get("classify_ecg")
    advice = registry.get("get_health_advice")
    for bad in (lambda: classify.Input(samples=[], sampleRateHz=250),
                lambda: advice.Input(message="")):
        try:
            bad()
        except ValidationError as exc:
            assert classify_exception(exc) == "schema"
        else:
            raise AssertionError("expected ValidationError")


def test_risk_contract_validates_enums():
    # The risk tool's Input is the shared backend contract (RiskRequest) with
    # typed enums, so a bad category is a schema error (no ML deps needed).
    risk = registry.get("predict_heart_failure_risk")
    good = dict(BMI=28.5, Smoking="Yes", AlcoholDrinking="No", Stroke="No",
                PhysicalHealth=5, MentalHealth=3, DiffWalking="No", Sex="Male",
                AgeCategory="60-64", Race="White", Diabetic="Yes",
                PhysicalActivity="Yes", GenHealth="Fair", SleepTime=6,
                Asthma="No", KidneyDisease="No", SkinCancer="No")
    risk.Input(**good)                                    # valid -> no error
    try:
        risk.Input(**{**good, "Sex": "Other"})            # not in {Male, Female}
    except ValidationError as exc:
        assert classify_exception(exc) == "schema"
    else:
        raise AssertionError("expected ValidationError for bad enum")


def test_reference_resolution():
    ctx = {"read": {"samples": [1.0, 2.0], "sampleRateHz": 250}}
    resolved = _resolve({"samples": "${read.samples}", "rate": "${read.sampleRateHz}",
                         "literal": "x"}, ctx)
    assert resolved == {"samples": [1.0, 2.0], "rate": 250, "literal": "x"}
    try:
        _resolve("${read.missing}", ctx)
    except WatError as exc:
        assert exc.category == "schema"
    else:
        raise AssertionError("expected WatError for missing field")


def test_green_csv_pipeline_end_to_end():
    result = run_workflow("wat/workflows/ecg_csv_pipeline.yaml")
    assert result.status == "completed", result.errors
    assert result.context["read"]["sampleCount"] > 0
    # state checkpoint + telemetry trace were written
    from wat.paths import STATE_DIR, TELEMETRY_DIR
    assert (STATE_DIR / f"{result.run_id}.json").exists()
    trace = TELEMETRY_DIR / f"{result.run_id}.jsonl"
    assert trace.exists() and trace.read_text(encoding="utf-8").strip()


def test_live_pipeline_runs_or_degrades_cleanly():
    # Environment-agnostic: with TensorFlow + the .keras model present, classify
    # succeeds (status completed); without them it degrades to a clean
    # 'dependency' error and the run continues (on_error: continue). Either way
    # the run is well-formed: read produced samples and persist stored a record.
    result = run_workflow("wat/workflows/ecg_live_pipeline.yaml")
    assert result.context["read"]["sampleCount"] > 0
    assert result.context["persist"]["stored"] is True

    classify = result.context["classify"]
    if "prediction" in classify:                      # green path (models available)
        assert result.status == "completed", result.errors
        assert classify["prediction"]
        # confidence is a 0-100 percentage, OR null when the signal-quality gate
        # refuses to classify a poor/short trace (then prediction is inconclusive).
        conf = classify["confidence"]
        assert conf is None or 0.0 <= conf <= 100.0
        assert classify.get("disclaimer")            # clinical-safety gate present
        assert classify.get("notMedicalAdvice") is True
    else:                                             # degraded path (no TF/model)
        assert result.status == "completed_with_errors"
        assert classify["_category"] == "dependency"


def test_safety_disclaimer_is_attached():
    # Env-agnostic: the clinical-safety helper attaches a non-empty disclaimer
    # and the not-medical-advice flag to any prediction payload.
    ensure_backend_on_path()
    from safety import attach_disclaimer, MEDICAL_DISCLAIMER

    enriched = attach_disclaimer({"HeartFailureRisk": "Low cardiac risk profile"})
    assert enriched["HeartFailureRisk"] == "Low cardiac risk profile"   # original kept
    assert enriched["disclaimer"] == MEDICAL_DISCLAIMER and MEDICAL_DISCLAIMER
    assert enriched["notMedicalAdvice"] is True
    assert "not a medical diagnosis" in MEDICAL_DISCLAIMER.lower()


def test_wrapped_tool_matches_underlying_function():
    # get_health_advice must return exactly what chatbot_logic produces.
    ensure_backend_on_path()
    from chatbot_logic import generate_chat_response

    tool = registry.get("get_health_advice")
    message = "Tell me about exercise for my heart"
    wrapped = tool.run(tool.Input(message=message)).response
    assert wrapped == generate_chat_response(message)


def test_health_qa_workflow_with_params():
    # Runtime params (${params.message}) drive the workflow; fully green, no ML.
    result = run_workflow("wat/workflows/health_qa.yaml",
                          params={"message": "How much exercise is good for my heart?"})
    assert result.status == "completed", result.errors
    assert result.context["answer"]["response"]
    assert result.context["persist"]["stored"] is True


def test_risk_workflow_runs_or_degrades():
    # Parametrized risk workflow: green when XGBoost + artifacts are present,
    # else a clean dependency error. Persist always stores a record.
    result = run_workflow("wat/workflows/risk_assessment.yaml", params=VALID_RISK)
    assert result.context["persist"]["stored"] is True
    assess = result.context["assess"]
    if "HeartFailureRisk" in assess:               # green path
        assert result.status == "completed", result.errors
        assert assess["HeartFailureRisk"]
        assert assess.get("disclaimer")            # safety gate carried through
    else:                                          # degraded path
        assert result.status == "completed_with_errors"
        assert assess["_category"] == "dependency"


def _main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL {test.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_main())
