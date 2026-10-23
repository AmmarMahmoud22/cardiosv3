"""Flask-free chatbot response logic.

Extracted verbatim from the ``chat()`` route in ``chatbot_service.py`` so the
exact same logic can be reused by the WAT ``get_health_advice`` tool (and unit
tested) without importing Flask or standing up the server. ``chatbot_service``
now imports ``generate_chat_response`` from here.
"""
from __future__ import annotations

import random

# Simple template-based response system as fallback
FALLBACK_TEMPLATES = [
    "I'd recommend consulting with a healthcare provider about your heart health concerns.",
    "Regular check-ups are important for monitoring your heart health.",
    "A healthy diet and regular exercise are key factors in maintaining good heart health.",
    "If you're experiencing chest pain or discomfort, please seek medical attention immediately.",
    "Monitoring your blood pressure regularly can help detect potential heart issues early.",
    "It's important to maintain a healthy lifestyle to reduce your risk of heart disease.",
]

HEART_RELATED_KEYWORDS = [
    'heart', 'cardiac', 'ecg', 'ekg', 'cardiovascular', 'chest pain',
    'arrhythmia', 'palpitations', 'blood pressure', 'cholesterol',
    'hypertension', 'stroke', 'attack', 'failure', 'health', 'exercise',
    'diet', 'lifestyle', 'risk', 'symptom', 'diagnosis',
]


def generate_chat_response(user_message: str) -> str:
    """Return a heart-health response for ``user_message`` (rule/keyword based)."""
    message = (user_message or "").lower()
    is_heart_related = any(keyword in message for keyword in HEART_RELATED_KEYWORDS)

    if not is_heart_related:
        return ("I'm an assistant focused on heart health topics. Could you please ask a "
                "question related to heart health, ECG analysis, or cardiovascular wellness?")

    if 'chest pain' in message or 'discomfort' in message:
        return ("If you're experiencing chest pain or discomfort, please seek medical "
                "attention immediately. This could be a sign of a serious condition.")
    if 'exercise' in message or 'activity' in message:
        return ("Regular physical activity is excellent for heart health. Aim for at least "
                "150 minutes of moderate exercise each week, but always consult with your "
                "doctor before starting a new exercise program.")
    if 'diet' in message or 'food' in message or 'eat' in message:
        return ("A heart-healthy diet includes plenty of fruits, vegetables, whole grains, "
                "lean proteins, and healthy fats. Limiting sodium, processed foods, and "
                "saturated fats can help reduce heart disease risk.")
    if 'blood pressure' in message or 'hypertension' in message:
        return ("Maintaining healthy blood pressure is crucial for heart health. Regular "
                "monitoring, medication if prescribed, reducing sodium intake, staying "
                "physically active, and managing stress can all help control blood pressure.")
    if 'cholesterol' in message or 'lipids' in message:
        return ("High cholesterol can increase your risk of heart disease. A heart-healthy "
                "diet, regular exercise, and sometimes medication can help manage cholesterol "
                "levels. Regular check-ups can monitor your progress.")
    if 'risk' in message or 'prevention' in message:
        return ("Key factors for heart disease prevention include not smoking, maintaining a "
                "healthy weight, regular exercise, healthy diet, limiting alcohol, managing "
                "stress, and regular health check-ups.")
    if any(word in message for word in ['ecg', 'ekg', 'electrocardiogram']):
        return ("An ECG or EKG (electrocardiogram) is a test that records the electrical "
                "activity of your heart. It helps doctors detect irregularities in heart "
                "rhythm and structure. It's a common, non-invasive diagnostic tool.")
    if 'failure' in message:
        return ("Heart failure is a condition where the heart can't pump blood effectively. "
                "Symptoms may include shortness of breath, fatigue, and swelling. Early "
                "detection through regular check-ups and prompt treatment are essential.")
    return random.choice(FALLBACK_TEMPLATES)
