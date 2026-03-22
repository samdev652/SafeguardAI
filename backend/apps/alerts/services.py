import os

import requests
from django.conf import settings


def _cleaned(value: str | None) -> str:
    if value is None:
        return ''
    cleaned = str(value).strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _normalize_wa_phone(phone: str) -> str:
    # WhatsApp Cloud API expects international format without "+".
    digits = ''.join(ch for ch in str(phone) if ch.isdigit())
    if digits.startswith('0'):
        digits = f'254{digits[1:]}'
    return digits


def _parse_provider_json(response: requests.Response) -> tuple[dict, str]:
    if not response.content:
        return {}, ''
    try:
        payload = response.json()
        if isinstance(payload, dict):
            return payload, ''
        return {}, 'Provider returned a non-object JSON response.'
    except Exception:
        body = (response.text or '').strip()
        if not body:
            return {}, 'Provider returned a non-JSON response with an empty body.'
        # Keep provider body snippets compact in API responses and logs.
        return {}, body[:220]


def _africas_talking_sent(payload: dict, status_code: int, non_json_reason: str = '') -> tuple[bool, str]:
    recipients = payload.get('SMSMessageData', {}).get('Recipients', []) if isinstance(payload, dict) else []
    if not recipients:
        if non_json_reason:
            return False, f'HTTP {status_code}: {non_json_reason}'
        error_message = str(payload.get('errorMessage') or payload.get('message') or '').strip() if payload else ''
        if error_message:
            return False, error_message
        return False, 'No recipient status returned by provider.'
    status_text = str(recipients[0].get('status') or '').strip()
    if status_text.lower().startswith('success'):
        return True, status_text or 'Success'
    return False, status_text or 'Provider did not accept the message.'


class AlertDispatcher:
    def _resolve_sms_sender_id(self, purpose: str) -> str:
        # Optional per-purpose sender IDs keep OTP and alert streams visually distinct for users.
        if purpose == 'otp':
            otp_sender = _cleaned(os.getenv('AFRICASTALKING_OTP_SENDER_ID', ''))
            if otp_sender:
                return otp_sender
        else:
            alert_sender = _cleaned(os.getenv('AFRICASTALKING_ALERT_SENDER_ID', ''))
            if alert_sender:
                return alert_sender

        return _cleaned(os.getenv('AFRICASTALKING_SENDER_ID', ''))

    def send_sms(self, phone: str, message: str, purpose: str = 'alert') -> dict:
        username = _cleaned(
            getattr(settings, 'AFRICASTALKING_USERNAME', '') or os.getenv('AFRICASTALKING_USERNAME', '')
        )
        api_key = _cleaned(
            getattr(settings, 'AFRICASTALKING_API_KEY', '') or os.getenv('AFRICASTALKING_API_KEY', '')
        )
        desired_sender_id = self._resolve_sms_sender_id(purpose)

        if not api_key:
            return {'sent': False, 'channel': 'sms', 'reason': 'missing_api_key'}

        # Use the sandbox endpoint only when the sandbox username is used.
        is_sandbox = username.lower() == 'sandbox'
        url = (
            'https://api.sandbox.africastalking.com/version1/messaging'
            if is_sandbox
            else 'https://api.africastalking.com/version1/messaging'
        )

        # Africa's Talking sandbox frequently rejects custom sender IDs.
        sender_id = '' if is_sandbox else desired_sender_id

        data = {
            'username': username or 'sandbox',
            'to': phone,
            'message': message,
        }
        if sender_id:
            data['from'] = sender_id

        try:
            response = requests.post(
                url,
                headers={
                    'apiKey': api_key,
                    'Accept': 'application/json',
                },
                data=data,
                timeout=15,
            )
            payload, parse_reason = _parse_provider_json(response)
        except requests.RequestException as exc:
            return {
                'sent': False,
                'channel': 'sms',
                'provider': 'africas_talking',
                'reason': str(exc),
            }

        sent, reason = _africas_talking_sent(payload, response.status_code, parse_reason)
        return {
            'sent': sent,
            'channel': 'sms',
            'provider': 'africas_talking',
            'purpose': purpose,
            'sender_id': sender_id or None,
            'desired_sender_id': desired_sender_id or None,
            'username': username or 'sandbox',
            'reason': reason,
            'status_code': response.status_code,
            'response': payload,
        }

    def send_whatsapp(self, phone: str, message: str) -> dict:
        token = _cleaned(
            getattr(settings, 'WHATSAPP_TOKEN', '')
            or os.getenv('WHATSAPP_TOKEN', '')
        )
        phone_id = _cleaned(
            getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')
            or os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
        )

        if not token or not phone_id:
            return {
                'sent': False,
                'channel': 'whatsapp',
                'reason': 'missing_whatsapp_credentials'
            }

        try:
            # Send plain text directly - works for verified test recipients
            response = requests.post(
                f'https://graph.facebook.com/v20.0/{phone_id}/messages',
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                },
                json={
                    'messaging_product': 'whatsapp',
                    'to': _normalize_wa_phone(phone),
                    'type': 'text',
                    'text': {'body': message}
                },
                timeout=15,
            )
            payload, parse_reason = _parse_provider_json(response)

        except requests.RequestException as exc:
            return {
                'sent': False,
                'channel': 'whatsapp',
                'provider': 'meta_whatsapp',
                'reason': str(exc)
            }

        has_message_id = bool(
            (payload.get('messages') or [{}])[0].get('id')
        ) if isinstance(payload, dict) else False

        error_text = ''
        if isinstance(payload, dict) and payload.get('error'):
            error = payload.get('error') or {}
            error_text = str(
                error.get('message') or
                error.get('error_user_msg') or ''
            ).strip()

        sent = response.status_code < 300 and has_message_id
        return {
            'sent': sent,
            'channel': 'whatsapp',
            'provider': 'meta_whatsapp',
            'reason': error_text or (
                'accepted' if sent else
                f'HTTP {response.status_code}: {parse_reason or "provider rejected"}'
            ),
            'status_code': response.status_code,
            'response': payload,
        }

    def send_push(self, _citizen_id: int, _message: str) -> dict:
        return {'status': 'queued', 'channel': 'push'}
