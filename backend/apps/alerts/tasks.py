from celery import shared_task
from django.utils import timezone
from apps.citizens.models import CitizenProfile
from apps.hazards.models import RiskAssessment
from apps.rescue.services import find_nearest_rescue_units
from .models import Alert, CommunityVerificationPrompt
from .services import AlertDispatcher


@shared_task
def dispatch_risk_alerts_task(risk_assessment_id: int) -> dict:
    dispatcher = AlertDispatcher()
    risk = RiskAssessment.objects.get(id=risk_assessment_id)
    citizens = list(CitizenProfile.objects.filter(ward_name__iexact=risk.ward_name))
    sent_count = 0

    nearest_units = list(find_nearest_rescue_units(risk.location.x, risk.location.y))
    contacts = []
    for unit in nearest_units[:3]:
        unit_type = str(unit.responder_unit_type or 'rescue_team').replace('_', ' ')
        contacts.append(f'{unit.full_name} ({unit_type}) {unit.phone_number}')

    contacts_line = (
        'Nearest rescue contacts: ' + '; '.join(contacts)
        if contacts
        else 'Nearest rescue contacts: call county emergency center.'
    )

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
            f'What to do: {guidance}\n'
            f'{contacts_line}'
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
                    provider_response = dispatcher.send_sms(citizen.phone_number, message, purpose='alert')
                elif channel == Alert.CHANNEL_WHATSAPP:
                    provider_response = dispatcher.send_whatsapp(citizen.phone_number, message)
                else:
                    provider_response = dispatcher.send_push(citizen.id, message)

                if channel == Alert.CHANNEL_PUSH or provider_response.get('sent'):
                    alert.status = Alert.STATUS_SENT
                    alert.provider_response = provider_response
                    alert.sent_at = timezone.now()
                    alert.save(update_fields=['status', 'provider_response', 'sent_at'])
                    sent_count += 1
                else:
                    alert.status = Alert.STATUS_FAILED
                    alert.provider_response = provider_response
                    alert.save(update_fields=['status', 'provider_response'])
            except Exception as exc:
                alert.status = Alert.STATUS_FAILED
                alert.provider_response = {'error': str(exc)}
                alert.save(update_fields=['status', 'provider_response'])

    # Follow-up ground-truth prompt after major threats so residents can verify field reality.
    if risk.risk_level in {RiskAssessment.RISK_HIGH, RiskAssessment.RISK_CRITICAL}:
        for citizen in citizens:
            prompt_message = (
                f'[Safeguard VERIFY] {risk.hazard_type.title()} risk in {risk.ward_name}. '
                'Reply YES if you can see the disaster, or NO if everything looks normal.'
            )
            prompt, created = CommunityVerificationPrompt.objects.get_or_create(
                risk_assessment=risk,
                citizen=citizen,
                defaults={
                    'phone_number': citizen.phone_number,
                    'prompt_message': prompt_message,
                },
            )
            if not created:
                continue
            try:
                dispatcher.send_sms(citizen.phone_number, prompt_message, purpose='alert')
            except Exception:
                # Prompt persistence allows webhook replies even if provider intermittently fails.
                pass

    return {'sent_alerts': sent_count}
