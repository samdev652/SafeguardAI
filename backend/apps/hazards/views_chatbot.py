import json
import re
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.cache import cache
from django_redis import get_redis_connection
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.throttling import BaseThrottle
from rest_framework.parsers import JSONParser
from apps.hazards.models import RiskAssessment, WardBoundary
from apps.hazards.services import GeminiRiskAnalyzer

# Emergency keywords (English & Swahili)
EMERGENCY_WORDS = [
    'help', 'sos', 'emergency', 'stuck', 'trapped', 'niokoe', 'msaada', 'nimezingirwa', 'nimeumia'
]

# Rate limit: 30 messages/hour/IP
class RedisRateThrottle(BaseThrottle):
    rate = 30
    period = 3600  # seconds
    redis_prefix = 'chatbot_rate:'

    def allow_request(self, request, view):
        ip = self.get_ident(request)
        key = f'{self.redis_prefix}{ip}'
        conn = get_redis_connection('default')
        count = conn.get(key)
        if count is not None and int(count) >= self.rate:
            return False
        pipe = conn.pipeline()
        pipe.incr(key, 1)
        pipe.expire(key, self.period)
        pipe.execute()
        return True

    def wait(self):
        return None

@method_decorator(csrf_exempt, name='dispatch')
class ChatbotMessageView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RedisRateThrottle]
    parser_classes = [JSONParser]

    def post(self, request):
        data = request.data
        message = data.get('message', '').strip()
        session_id = data.get('session_id')
        ward_name = data.get('ward_name')
        user_lang = self.detect_language(message)
        if not session_id or not message:
            return JsonResponse({'error': 'Missing session_id or message'}, status=400)

        # Get conversation history from Redis
        redis = get_redis_connection('default')
        history_key = f'chatbot:history:{session_id}'
        history_json = redis.get(history_key)
        history = json.loads(history_json) if history_json else []

        # If logged in, use registered ward; else use provided ward
        if request.user.is_authenticated and hasattr(request.user, 'citizenprofile'):
            ward_name = request.user.citizenprofile.ward_name or ward_name

        # Fetch live risk data for the ward
        risks = list(RiskAssessment.objects.filter(ward_name__iexact=ward_name, risk_level__in=['high', 'critical', 'medium']).order_by('-issued_at').values()) if ward_name else []
        now = timezone.localtime(timezone.now())
        nairobi_time = now.strftime('%Y-%m-%d %H:%M:%S')

        # System prompt
        system_prompt = self.build_system_prompt(user_lang, ward_name, risks, nairobi_time)

        # Build Gemini conversation
        gemini_messages = [{'role': 'system', 'content': system_prompt}]
        for turn in history:
            gemini_messages.append({'role': turn['role'], 'content': turn['content']})
        gemini_messages.append({'role': 'user', 'content': message})

        # Call Gemini
        gemini = GeminiRiskAnalyzer()
        response = gemini.chat(gemini_messages, language=user_lang)

        # Emergency detection
        is_emergency = any(word in message.lower() for word in EMERGENCY_WORDS)
        rescue_contacts = self.get_rescue_contacts(ward_name) if is_emergency else None
        if is_emergency and rescue_contacts:
            response = f"<span style='color:#ef4444;font-weight:bold'>Rescue contacts: {rescue_contacts}</span>\n" + response

        # Save conversation history (max 20 turns)
        history.append({'role': 'user', 'content': message})
        history.append({'role': 'assistant', 'content': response})
        redis.set(history_key, json.dumps(history[-20:]), ex=86400)

        return JsonResponse({'response': response, 'lang': user_lang})

    def build_system_prompt(self, lang, ward, risks, nairobi_time):
        risk_context = '\n'.join([
            f"- {r['hazard_type'].title()} risk: {r['risk_level'].title()} (score {int(r['risk_score'])}) at {r['ward_name']} {r['summary']}"
            for r in risks
        ]) or 'No active risks found.'
        prompt = (
            f"You are the official Safeguard AI disaster assistant for Kenya. Today is {nairobi_time} (Africa/Nairobi timezone).\n"
            f"Always answer in the same language as the user ({lang}).\n"
            f"Base every answer on the live risk data below, not general knowledge.\n"
            f"Ward: {ward or 'unknown'}\n"
            f"Live risk data:\n{risk_context}\n"
            "If the user describes an emergency, always include the nearest rescue phone numbers as the first line, highlighted in red.\n"
            "Never say a situation is safe if the risk level is high or critical.\n"
            "Guide new users through registration if they ask.\n"
            "If the user asks about evacuation, provide the best route and survival guidance.\n"
            "If the user asks for help, SOS, or uses emergency words, always respond with rescue contacts first.\n"
        )
        return prompt

    def detect_language(self, text):
        # Simple heuristic: check for Swahili keywords
        swahili_words = ['msaada', 'niokoe', 'nimeumia', 'nimezingirwa', 'habari', 'karibu']
        if any(word in text.lower() for word in swahili_words):
            return 'sw'
        # Default to English
        return 'en'

    def get_rescue_contacts(self, ward_name):
        # Dummy implementation, replace with real lookup
        # Example: return '999, 112, 0712345678'
        return '999, 112, 0712345678'

# Gemini chat method (add to GeminiRiskAnalyzer in services.py):
# def chat(self, messages, language='en'):
#     ...
