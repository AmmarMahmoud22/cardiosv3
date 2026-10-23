from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flasgger import Swagger, swag_from
from werkzeug.exceptions import HTTPException
import sys
from pathlib import Path

_BACKEND_DIR = str(Path(__file__).resolve().parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Load .env before anything reads os.getenv(). Without this the backend only
# ever saw shell environment variables, so settings written to .env (which Vite
# does read) silently never reached Flask — the RAG module would fall back to a
# provider that did not match the indexed corpus and retrieval would return 503
# with no obvious cause. Existing shell variables still win over the file.
try:
    from dotenv import load_dotenv as _load_dotenv

    _load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except Exception:  # noqa: BLE001 - a missing .env must never stop the server
    pass

# Structured logging must be configured before the blueprints log anything.
from logging_config import configure_logging
configure_logging()

from ecg_service import ecg_bp, ecg_store
from chatbot_service import chatbot_bp
from device_discovery import advertise_cardios_api

import logging
import os
import time
import uuid

from pydantic import ValidationError

# Risk preprocessing + XGBoost inference live in risk_model.py — the single
# source of truth shared with the WAT predict_heart_failure_risk tool.
from risk_model import predict_risk, load_artifacts
# One shared request contract validates both this route and the WAT risk tool.
from contracts import RiskRequest, format_validation_errors
# Optional Supabase JWT gate (enforced only when AUTH_ENABLED=true).
from auth import require_auth
# Centralised, env-driven API security (CORS, size caps, device auth, errors).
import security
from ratelimit import limiter, rate_limit, rate_limit_enabled

logger = logging.getLogger(__name__)

START_TIME = time.time()
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

app = Flask(__name__)


# --- Per-request structured access logging (requestId + latency). ---
@app.before_request
def _start_timer():
    g.request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
    g.t0 = time.perf_counter()


@app.after_request
def _access_log(response):
    duration_ms = round((time.perf_counter() - getattr(g, "t0", time.perf_counter())) * 1000, 1)
    response.headers["X-Request-Id"] = getattr(g, "request_id", "-")
    # Skip noise from health probes to keep logs signal-rich.
    if request.path not in ("/health", "/health/ready"):
        logger.info("request", extra={
            "requestId": getattr(g, "request_id", "-"),
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "durationMs": duration_ms,
        })
    return response

# --- Restricted CORS: only the configured origins (localhost in dev + production Appwrite). ---
CORS(
    app,
    resources={r"/*": {"origins": security.get_allowed_origins()}},
    supports_credentials=True,
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Device-Token"],
)

# --- Cap request body size (clean 413 instead of unbounded reads). ---
app.config["MAX_CONTENT_LENGTH"] = security.max_content_length_bytes()

# --- Rate limiting (per-IP). Default limits applied to every route. ---
if limiter is not None:
    limiter.init_app(app)
    limiter.enabled = rate_limit_enabled()

# تسجيل Blueprint الخاص بـ ECG
app.register_blueprint(ecg_bp)

# Register chatbot blueprint
app.register_blueprint(chatbot_bp, url_prefix='/chatbot')

# --- RAG module (guideline-grounded clinical evidence). Additive and optional.
# Registered defensively: the RAG module is new and still being built out, and a
# failure to import it must never take down the existing prediction/ECG API.
try:
    from rag.service import rag_bp
    app.register_blueprint(rag_bp, url_prefix='/rag')
    logger.info("RAG module registered at /rag")
except Exception as _rag_exc:  # noqa: BLE001
    logger.warning("RAG module not registered (%s: %s). Existing endpoints are unaffected.",
                   type(_rag_exc).__name__, _rag_exc)

# --- Swagger docs: on in dev, OFF in production by default (SWAGGER_ENABLED). ---
if security.swagger_enabled():
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": 'apispec',
                "route": '/apispec.json',
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/docs"
    }
    swagger = Swagger(app, config=swagger_config)
else:
    logger.info("Swagger docs disabled (production or SWAGGER_ENABLED=false).")


# --- Clean, non-leaking error responses ---
@app.errorhandler(413)
def _too_large(_e):
    return jsonify({"error": "Request payload too large"}), 413


@app.errorhandler(429)
def _rate_limited(e):
    return jsonify({"error": "Too many requests", "detail": getattr(e, "description", None)}), 429


@app.errorhandler(Exception)
def _handle_uncaught(e):
    # Let Flask/werkzeug HTTP errors (404, 400, 413, 429, ...) keep their own
    # response; only genericise unexpected server-side exceptions.
    if isinstance(e, HTTPException):
        return e
    logger.exception("Unhandled server error")
    return security.safe_error_response(e)


# Load the risk model artifacts at startup (fail-fast if the model files are missing).
load_artifacts()

@app.route('/')
@swag_from({
    'responses': {
        200: {
            'description': 'Welcome to the Cardios Prediction API'
        }
    }
})
def home():
    return jsonify({"message": "Welcome to Cardios Prediction API!"})


@app.route('/health', methods=['GET'])
def health():
    """Liveness probe: the process is up and serving."""
    return jsonify({
        "status": "ok",
        "version": APP_VERSION,
        "uptimeSeconds": round(time.time() - START_TIME, 1),
    })


@app.route('/health/ready', methods=['GET'])
def health_ready():
    """Readiness probe: dependencies (models + store) are usable."""
    from ecg_service import model as ecg_model
    checks = {
        "ecgModel": ecg_model is not None,
        "riskModel": True,                 # load_artifacts() ran at startup (fail-fast)
        "ecgStore": ecg_store.healthcheck(),
    }
    # Core readiness is unchanged: the RAG corpus is reported for visibility but
    # is NOT part of the ready/degraded decision, so an in-progress RAG build
    # can never mark the existing Cardios API unhealthy.
    ready = all(checks.values())
    body = {
        "status": "ready" if ready else "degraded",
        "version": APP_VERSION,
        "checks": checks,
        "store": ecg_store.stats(),
    }
    try:
        from rag.store import CorpusStore
        body["ragCorpus"] = CorpusStore().stats()
    except Exception:  # noqa: BLE001
        body["ragCorpus"] = {"state": "not_configured"}
    return jsonify(body), (200 if ready else 503)


@app.route('/predict', methods=['POST'])
@swag_from({
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'id': 'PredictionInput',
                'required': ['BMI', 'Smoking', 'AlcoholDrinking', 'Stroke', 'PhysicalHealth', 
                           'MentalHealth', 'DiffWalking', 'Sex', 'AgeCategory', 'Race', 
                           'Diabetic', 'PhysicalActivity', 'GenHealth', 'SleepTime', 
                           'Asthma', 'KidneyDisease', 'SkinCancer'],
                'properties': {
                    'BMI': {'type': 'number', 'description': 'Body Mass Index'},
                    'Smoking': {'type': 'string', 'enum': ['Yes', 'No']},
                    'AlcoholDrinking': {'type': 'string', 'enum': ['Yes', 'No']},
                    'Stroke': {'type': 'string', 'enum': ['Yes', 'No']},
                    'PhysicalHealth': {'type': 'integer', 'minimum': 0, 'maximum': 30},
                    'MentalHealth': {'type': 'integer', 'minimum': 0, 'maximum': 30},
                    'DiffWalking': {'type': 'string', 'enum': ['Yes', 'No']},
                    'Sex': {'type': 'string', 'enum': ['Male', 'Female']},
                    'AgeCategory': {'type': 'string'},
                    'Race': {'type': 'string'},
                    'Diabetic': {'type': 'string'},
                    'PhysicalActivity': {'type': 'string', 'enum': ['Yes', 'No']},
                    'GenHealth': {'type': 'string'},
                    'SleepTime': {'type': 'number', 'minimum': 0, 'maximum': 24},
                    'Asthma': {'type': 'string', 'enum': ['Yes', 'No']},
                    'KidneyDisease': {'type': 'string', 'enum': ['Yes', 'No']},
                    'SkinCancer': {'type': 'string', 'enum': ['Yes', 'No']}
                }
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Prediction result',
            'schema': {
                'properties': {
                    'HeartFailureRisk': {'type': 'string'}
                }
            }
        },
        400: {
            'description': 'Invalid input data'
        }
    }
})
@require_auth
@rate_limit(os.getenv("RATE_LIMIT_PREDICT", "30 per minute"))
def predict():
    # Boundary validation: turn bad input into a clear 400 instead of a deep failure.
    try:
        payload = RiskRequest(**(request.get_json(silent=True) or {}))
    except ValidationError as exc:
        return jsonify({"error": "Invalid input", "details": format_validation_errors(exc)}), 400
    result, status = predict_risk(payload.model_dump())
    return jsonify(result), status


if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('PORT', os.getenv('FLASK_PORT', '49232')))
    # Debug OFF unless explicitly enabled: the Werkzeug debugger allows
    # arbitrary code execution and must never be the default.
    debug = os.getenv('FLASK_DEBUG', '0').lower() in {'1', 'true', 'yes', 'on'}
    with advertise_cardios_api(port):
        app.run(debug=debug, use_reloader=debug, port=port, host=host)
