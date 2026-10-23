import tensorflow as tf
import numpy as np
from flask import Blueprint, request, jsonify, g
from werkzeug.exceptions import HTTPException
import pandas as pd
from pathlib import Path
from flasgger import swag_from
import logging
import shutil
import tempfile
import os
from datetime import datetime, timezone
from csv_converter import convert_csv_to_format
from safety import MEDICAL_DISCLAIMER, DISCLAIMER_VERSION
from signal_quality import assess_quality
from auth import require_auth, auth_enabled
from security import require_device_auth, safe_error_response
from ratelimit import rate_limit
from pydantic import ValidationError
from contracts import DeviceEcgRequest, format_validation_errors

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ecg_bp = Blueprint('ecg', __name__)

# تحميل النموذج
try:
    model_path = Path(__file__).parent / 'ECG model' / 'ECG_Heart Failure Project_best_model_cnn_lstm.keras'
    logger.info(f"محاولة تحميل النموذج من: {model_path}")
    model = tf.keras.models.load_model(str(model_path), compile=False)
    logger.info("تم تحميل النموذج بنجاح")
except Exception as e:
    logger.error(f"فشل في تحميل النموذج: {str(e)}")
    # لا نرفع استثناء هنا لتجنب فشل تشغيل التطبيق عند البدء
    model = None

# تعريف الفئات
CATEGORIES = [
    'Normal',
    'Atrial Premature',
    'Premature Ventricular Contraction',
    'Fusion of Ventricular and Normal',
    'Fusion of Paced and Normal'
]

MODEL_TIMESTEPS = 180

# Per-device, durable store (SQLite-backed). Replaces the old single global
# ``latest_device_reading`` dict so the backend serves many devices/patients.
from device_store import EcgStore

ecg_store = EcgStore()


def normalize_ecg_length(data, target_length=MODEL_TIMESTEPS):
    data = np.asarray(data, dtype=np.float32).flatten()

    if data.size == 0:
        raise ValueError('No ECG samples provided.')

    if data.size == target_length:
        return data

    original_positions = np.linspace(0, data.size - 1, num=data.size)
    target_positions = np.linspace(0, data.size - 1, num=target_length)
    return np.interp(target_positions, original_positions, data).astype(np.float32)


def estimate_heart_rate_bpm(data, sample_rate_hz):
    samples = np.asarray(data, dtype=np.float32).flatten()
    if samples.size < max(sample_rate_hz, 120):
        return None

    centered = samples - np.mean(samples)
    amplitude = float(np.max(centered) - np.min(centered))
    if amplitude <= 0:
        return None

    threshold = np.mean(centered) + (0.55 * amplitude)
    min_gap = max(int(sample_rate_hz * 0.25), 1)
    peaks = []

    for index in range(1, samples.size - 1):
        if centered[index] <= threshold:
            continue
        if centered[index] <= centered[index - 1] or centered[index] < centered[index + 1]:
            continue
        if peaks and index - peaks[-1] < min_gap:
            if centered[index] > centered[peaks[-1]]:
                peaks[-1] = index
            continue
        peaks.append(index)

    if len(peaks) < 2:
        return None

    intervals = np.diff(peaks)
    average_interval = float(np.mean(intervals))
    if average_interval <= 0:
        return None

    bpm = 60.0 * sample_rate_hz / average_interval
    if bpm < 30 or bpm > 220:
        return None

    return round(bpm, 1)


def build_prediction_response(raw_data, sample_rate_hz, device_id='local-device', lead_off=False, heart_rate_bpm=None):
    # Signal-quality gate FIRST: a single-lead trace is often lead-off, clipped,
    # or noise-dominated. Classifying such a trace yields a confident-looking but
    # meaningless label, so we assess quality before trusting the model.
    quality = assess_quality(raw_data, sample_rate_hz, lead_off=lead_off)
    quality_ok = quality['usableForClassification']

    processed_input = normalize_ecg_length(raw_data)
    processed_data = preprocess_ecg_data(processed_input)
    predictions = model.predict(processed_data, verbose=0)  # verbose=0: no progress bar (crashes cp1252 logs)

    predicted_class_index = int(np.argmax(predictions[0]))
    confidence = float(predictions[0][predicted_class_index])
    predicted_class = CATEGORIES[predicted_class_index]

    # Express confidence as a 0-100 percentage so the UI (which renders
    # `confidence.toFixed(1)%` and compares deltas in percentage points) shows
    # the real probability, e.g. 0.93 -> 93.0 instead of "0.9%".
    confidence_percent = round(confidence * 100.0, 1)

    if quality_ok:
        # Report the model's actual top class as-is. (A previous low-confidence
        # branch silently re-mapped a "Normal" prediction to the next-best
        # abnormal class, fabricating abnormal findings; that is removed.)
        prediction_note = predicted_class
    else:
        # Poor signal: refuse to present a confident classification.
        prediction_note = 'Inconclusive (poor signal quality)'
        confidence_percent = None

    if heart_rate_bpm is None and quality_ok:
        heart_rate_bpm = estimate_heart_rate_bpm(raw_data, sample_rate_hz)

    response = {
        'deviceId': device_id,
        'receivedAt': datetime.now(timezone.utc).isoformat(),
        'prediction': prediction_note,
        'confidence': confidence_percent,
        'modelClass': predicted_class,
        'modelConfidence': round(confidence * 100.0, 1),
        'ecgData': np.asarray(raw_data, dtype=np.float32).flatten().tolist(),
        'sampleRateHz': sample_rate_hz,
        'heartRateBpm': heart_rate_bpm,
        'leadOff': bool(lead_off),
        'modelSampleCount': MODEL_TIMESTEPS,
        # Signal-quality indicators (lead-off / flatline / clipping / noise).
        'signalQuality': quality,
        'qualityOk': quality_ok,
        # Clinical-safety gate: results are never emitted without the disclaimer.
        'disclaimer': MEDICAL_DISCLAIMER,
        'disclaimerVersion': DISCLAIMER_VERSION,
        'notMedicalAdvice': True,
    }

    return response

def preprocess_ecg_data(data):
    """
    معالجة بيانات ECG قبل التنبؤ
    """
    try:
        # تحويل البيانات إلى مصفوفة numpy
        data = np.array(data)
        logger.info(f"شكل البيانات قبل إعادة التشكيل: {data.shape}")
        
        # إعادة تشكيل البيانات للنموذج (batch_size, timesteps, features)
        data = data.reshape(1, -1, 1)
        logger.info(f"شكل البيانات بعد إعادة التشكيل: {data.shape}")

        # تطبيع min-max إلى المدى [0, 1] — يجب أن يطابق تطبيع وقت التدريب
        # (بيانات MIT-BIH المُدرَّب عليها النموذج مخزّنة في 0..1). استخدام
        # z-normalization هنا يخفض الدقة من ~98% إلى ~70%
        # (مؤكَّد عبر analysis/evaluate_ecg_model.py).
        data_min = np.min(data)
        data_range = np.max(data) - data_min
        if data_range == 0:
            data_range = 1.0
        data = (data - data_min) / data_range

        return data
    except Exception as e:
        logger.error(f"خطأ في معالجة البيانات: {str(e)}")
        raise

@ecg_bp.route('/predict-ecg', methods=['POST'])
@swag_from({
    'tags': ['ECG'],
    'description': 'تحليل بيانات ECG وتصنيفها',
    'parameters': [
        {
            'name': 'file',
            'in': 'formData',
            'type': 'file',
            'required': True,
            'description': 'ملف CSV يحتوي على بيانات ECG'
        }
    ],
    'responses': {
        200: {
            'description': 'نتيجة التحليل',
            'schema': {
                'properties': {
                    'prediction': {'type': 'string', 'description': 'تصنيف ECG'},
                    'confidence': {'type': 'number', 'description': 'نسبة الثقة في التنبؤ'},
                    'ecgData': {'type': 'array', 'description': 'بيانات ECG', 'items': {'type': 'number'}}
                }
            }
        },
        400: {
            'description': 'خطأ في البيانات المدخلة'
        },
        500: {
            'description': 'خطأ في الخادم'
        }
    }
})
@require_auth
@rate_limit(os.getenv("RATE_LIMIT_PREDICT_ECG", "20 per minute"))
def predict_ecg():
    temp_dir = None
    try:
        # التحقق من تحميل النموذج
        if model is None:
            logger.error("النموذج غير محمل. لا يمكن إجراء التنبؤ.")
            return jsonify({'error': 'Model not loaded. Check server logs.'}), 500
            
        # التحقق من وجود الملف
        if 'file' not in request.files:
            logger.error("لم يتم توفير أي ملف في الطلب")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        logger.info(f"تم استلام ملف: {file.filename}, نوع البيانات: {file.content_type}")
        
        if file.filename == '':
            logger.error("تم استلام ملف بدون اسم")
            return jsonify({'error': 'Empty filename'}), 400
        
        # حفظ الملف مؤقتًا
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, file.filename)
        file.save(temp_path)
        logger.info(f"تم حفظ الملف مؤقتًا في: {temp_path}")
        
        # تحويل الملف إلى التنسيق المناسب
        try:
            processed_file = convert_csv_to_format(temp_path)
            logger.info(f"تم تحويل الملف إلى: {processed_file}")
            
            if not processed_file:
                logger.error("فشل في تحويل الملف")
                return jsonify({'error': 'Failed to convert file format'}), 400
        except Exception as e:
            logger.error(f"خطأ أثناء تحويل الملف: {str(e)}")
            return safe_error_response(e, 400, "Error converting file")
            
        # قراءة بيانات CSV
        try:
            df = pd.read_csv(processed_file)
            logger.info(f"تم قراءة ملف CSV المعالج بنجاح. شكل البيانات: {df.shape}")
            
            if df.empty:
                logger.error("ملف CSV فارغ")
                return jsonify({'error': 'Empty CSV file'}), 400
                
            # نفترض أن البيانات في الصف الأول — مع فرض قيم رقمية: ملف نصي بلا
            # أرقام كان يمرّر strings للنموذج ويُرجع 500 بدل 400 نظيف.
            ecg_data = pd.to_numeric(df.iloc[0], errors='coerce').to_numpy(dtype=float)
            if np.isnan(ecg_data).all():
                logger.error("ملف CSV لا يحتوي على قيم رقمية")
                return jsonify({'error': 'CSV contains no numeric ECG samples'}), 400
            ecg_data = np.nan_to_num(ecg_data, nan=0.0)
            logger.info(f"تم استخراج بيانات ECG. طول البيانات: {len(ecg_data)}")
            
        except Exception as e:
            logger.error(f"فشل في قراءة ملف CSV: {str(e)}")
            return safe_error_response(e, 400, "Failed to read CSV file")
        
        try:
            response = build_prediction_response(
                raw_data=ecg_data,
                sample_rate_hz=180,
                device_id='csv-upload',
            )
            logger.info(f"النتيجة النهائية: {response['prediction']}, الثقة: {response['confidence']}")
            return jsonify(response)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"فشل في تنفيذ التنبؤ: {str(e)}")
            return safe_error_response(e, 500, "Failed to make prediction")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {str(e)}")
        return safe_error_response(e, 500)
    finally:
        # الملف المرفوع والملف المعالَج (_processed) كلاهما داخل temp_dir.
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


@ecg_bp.route('/device-ecg', methods=['POST'])
@require_device_auth
@rate_limit(os.getenv("RATE_LIMIT_DEVICE_ECG", "120 per minute"))
def receive_device_ecg():
    try:
        if model is None:
            return jsonify({'error': 'Model not loaded. Check server logs.'}), 500

        # Boundary validation via the shared contract.
        try:
            payload = DeviceEcgRequest(**(request.get_json(silent=True) or {}))
        except ValidationError as exc:
            return jsonify({"error": "Invalid input",
                            "details": format_validation_errors(exc)}), 400

        numeric_samples = [float(value) for value in payload.samples]
        response = build_prediction_response(
            raw_data=numeric_samples,
            sample_rate_hz=payload.sampleRateHz,
            device_id=payload.deviceId,
            lead_off=payload.leadOff,
            heart_rate_bpm=payload.heartRateBpm,
        )

        # Additive: proper multi-beat screening (R-peak detection -> per-beat
        # classification -> rhythm). Kept separate so the existing fields the
        # frontend relies on stay intact.
        try:
            import ecg_analysis
            if ecg_analysis._model is None:
                ecg_analysis._model = model  # reuse the already-loaded CNN-LSTM
            response['analysis'] = ecg_analysis.analyze(
                numeric_samples, payload.sampleRateHz, lead_off=payload.leadOff)
        except Exception as analysis_error:
            from security import is_production
            logger.error(f"Analysis pipeline failed: {analysis_error}")
            response['analysis'] = {'error': 'Analysis pipeline failed'}
            if not is_production():
                response['analysis']['detail'] = str(analysis_error)

        # Owner = explicit payload.userId, else the authenticated caller (if any).
        owner_id = payload.userId or getattr(g, 'user_id', None)
        ecg_store.record_reading(response, user_id=owner_id)
        logger.info(
            "device ECG batch stored",
            extra={
                'deviceId': payload.deviceId,
                'userId': owner_id,
                'prediction': response.get('prediction'),
                'qualityOk': response.get('qualityOk'),
                'numSamples': len(numeric_samples),
            },
        )

        return jsonify(response)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"فشل في استقبال بيانات الجهاز: {str(e)}")
        return safe_error_response(e, 500)


def _ownership_ok(requested_user_id):
    """Auth-aware ownership check for scoped retrieval.

    When AUTH is enabled, a caller may only read their own (userId == token sub).
    When AUTH is disabled (local dev), retrieval is unrestricted.
    """
    if not auth_enabled():
        return True
    caller = getattr(g, 'user_id', None)
    return caller is not None and (requested_user_id is None or requested_user_id == caller)


@ecg_bp.route('/device-ecg/latest', methods=['GET'])
@require_auth
def get_latest_device_ecg():
    """Latest reading for a specific device (``?deviceId=``) or, if omitted, the
    most recent across all devices (kept for backward compatibility)."""
    device_id = request.args.get('deviceId')
    reading = ecg_store.latest_by_device(device_id) if device_id else ecg_store.latest_overall()

    if not reading:
        return jsonify({
            'connected': False,
            'message': 'No device ECG batch has been received yet.',
        }), 404

    return jsonify(reading)


@ecg_bp.route('/device-ecg/devices', methods=['GET'])
@require_auth
def get_device_ecg_devices():
    user_id = getattr(g, 'user_id', None) if auth_enabled() else None
    return jsonify({'devices': ecg_store.list_devices(user_id=user_id)})


@ecg_bp.route('/patients/<user_id>/ecg/latest', methods=['GET'])
@require_auth
def get_latest_patient_ecg(user_id):
    """Latest reading owned by a patient. Auth-scoped: callers can only read their own."""
    if not _ownership_ok(user_id):
        return jsonify({'error': 'Forbidden'}), 403
    reading = ecg_store.latest_by_user(user_id)
    if not reading:
        return jsonify({'connected': False,
                        'message': 'No ECG reading found for this patient.'}), 404
    return jsonify(reading)


@ecg_bp.route('/device-ecg/history', methods=['GET'])
@require_auth
def get_ecg_history():
    """Metadata history filtered by device and/or patient (auth-scoped)."""
    device_id = request.args.get('deviceId')
    user_id = request.args.get('userId')
    try:
        limit = int(request.args.get('limit', 50))
    except (TypeError, ValueError):
        limit = 50

    # When auth is on, force the query to the caller's own scope.
    if auth_enabled():
        caller = getattr(g, 'user_id', None)
        if user_id and user_id != caller:
            return jsonify({'error': 'Forbidden'}), 403
        user_id = caller

    return jsonify({'items': ecg_store.history(device_id=device_id, user_id=user_id, limit=limit)})
