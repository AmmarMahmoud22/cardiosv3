from flask import Blueprint, request, jsonify
import os

# Response logic lives in a flask-free module so it can be reused by the WAT
# get_health_advice tool (and unit tested) without the web server.
from chatbot_logic import generate_chat_response
from ratelimit import rate_limit

# Create blueprint for chatbot routes
chatbot_bp = Blueprint('chatbot', __name__)

@chatbot_bp.route('/chat', methods=['POST'])
@rate_limit(os.getenv("RATE_LIMIT_CHAT", "30 per minute"))
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        response = generate_chat_response(user_message)
        return jsonify({"response": response})
        
    except Exception as e:
        print(f"Error in chatbot: {str(e)}")
        return jsonify({"response": "I'm having trouble processing your request right now. Please try asking about heart health in a different way."}), 200

# Health check endpoint for the chatbot service
@chatbot_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "Healthy", "service": "ECG Chatbot"})

