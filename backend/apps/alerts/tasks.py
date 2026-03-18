from celery import shared_task
from django.utils import timezone
from apps.citizens.models import CitizenProfile
from apps.hazards.models import RiskAssessment
from .models import Alert
from .services import AlertDispatcher


@shared_task
def dispatch_risk_alerts_task(risk_assessment_id: int) -> dict:
    dispatcher = AlertDispatcher()
    risk = RiskAssessment.objects.get(id=risk_assessment_id)
    citizens = CitizenProfile.objects.filter(ward_name__iexact=risk.ward_name)
    sent_count = 0

    for citizen in citizens:
        emoji = {
            'safe': '🟢',
            'medium': '🟡',
            'high': '🟠',
            'critical': '🔴',
        }.get(risk.risk_level, '🟡')
        guidance = risk.guidance_sw if citizen.preferred_language == 'sw' else risk.guidance_en
        message = (
            f'{emoji} Safeguard AI Alert\n'
            f'Location: {risk.ward_name}/{risk.village_name or "-"}\n'
            f'Hazard: {risk.hazard_type}\n'
            f'Risk: {risk.risk_level.upper()}\n'
            f'What to do: {guidance}'
        )

        for channel in citizen.channels:
            alert = Alert.objects.create(
                risk_assessment=risk,
                citizen=citizen,
                channel=channel,
                message=message,
            )
            try:
                if channel == Alert.CHANNEL_SMS:
                    provider_response = dispatcher.send_sms(citizen.phone_number, message)
                elif channel == Alert.CHANNEL_WHATSAPP:
                    provider_response = dispatcher.send_whatsapp(citizen.phone_number, message)
                else:
                    provider_response = dispatcher.send_push(citizen.id, message)

                alert.status = Alert.STATUS_SENT
                alert.provider_response = provider_response
                alert.sent_at = timezone.now()
                alert.save(update_fields=['status', 'provider_response', 'sent_at'])
                sent_count += 1
            except Exception as exc:
                alert.status = Alert.STATUS_FAILED
                alert.provider_response = {'error': str(exc)}
                alert.save(update_fields=['status', 'provider_response'])

    return {'sent_alerts': sent_count}
