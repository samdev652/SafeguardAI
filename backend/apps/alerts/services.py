import requests
from django.conf import settings


class AlertDispatcher:
    def send_sms(self, phone: str, message: str) -> dict:
        if not settings.AFRICASTALKING_API_KEY:
            return {'status': 'mocked', 'channel': 'sms'}
        response = requests.post(
            'https://api.africastalking.com/version1/messaging',
            headers={
                'apiKey': settings.AFRICASTALKING_API_KEY,
                'Accept': 'application/json',
            },
            data={
                'username': settings.AFRICASTALKING_USERNAME,
                'to': phone,
                'message': message,
            },
            timeout=15,
        )
        return response.json()

    def send_whatsapp(self, phone: str, message: str) -> dict:
        if not settings.WHATSAPP_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
            return {'status': 'mocked', 'channel': 'whatsapp'}
        response = requests.post(
            f'https://graph.facebook.com/v20.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages',
            headers={
                'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}',
                'Content-Type': 'application/json',
            },
            json={
                'messaging_product': 'whatsapp',
                'to': phone,
                'type': 'text',
                'text': {'body': message},
            },
            timeout=15,
        )
        return response.json()

    def send_push(self, _citizen_id: int, _message: str) -> dict:
        return {'status': 'queued', 'channel': 'push'}
