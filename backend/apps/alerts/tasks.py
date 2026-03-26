from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from apps.citizens.models import CitizenProfile
from apps.hazards.models import RiskAssessment, WardBoundary
from apps.rescue.services import find_nearest_rescue_units
from .models import Alert, CommunityVerificationPrompt
from .services import AlertDispatcher

# --- Hazard-specific action steps and don'ts ---
_HAZARD_ACTIONS = {
    'flood': {
        'actions': [
            'Move to higher ground immediately',
            'Disconnect electrical appliances and gas',
            'Keep emergency supplies and documents in a waterproof bag',
        ],
        'donts': [
            'Do NOT cross flooded roads or bridges on foot or by vehicle',
            'Do NOT return to a flooded building until authorities clear it',
        ],
    },
    'landslide': {
        'actions': [
            'Evacuate away from steep slopes and hillsides',
            'Move to stable, flat ground away from drainage paths',
            'Alert neighbours downhill from the slide zone',
        ],
        'donts': [
            'Do NOT stay near hillsides during or after heavy rain',
            'Do NOT attempt to cross a landslide debris field',
        ],
    },
    'drought': {
        'actions': [
            'Conserve all available water for drinking and cooking',
            'Protect livestock by moving them to shaded water points',
            'Contact your county water office for emergency supply schedules',
        ],
        'donts': [
            'Do NOT waste water on non-essential activities',
            'Do NOT rely on unverified water sources without treatment',
        ],
    },
    'earthquake': {
        'actions': [
            'Drop, Cover, and Hold On under sturdy furniture',
            'Move to an open area away from buildings after shaking stops',
            'Check for gas leaks and structural cracks before re-entering',
        ],
        'donts': [
            'Do NOT use elevators or stand near glass windows',
            'Do NOT re-enter damaged buildings without structural clearance',
        ],
    },
}

_DEFAULT_ACTIONS = {
    'actions': [
        'Monitor official channels for updates',
        'Prepare emergency supplies and water',
        'Follow county authority directives immediately',
    ],
    'donts': [
        'Do NOT ignore official evacuation orders',
        'Do NOT spread unverified information',
    ],
}


def _estimate_response_time(distance_m) -> str:
    """Estimate rescue response time from distance in metres."""
    if distance_m is None:
        return 'est. ~15min'
    try:
        km = float(str(distance_m).replace(' m', '')) / 1000.0
    except (TypeError, ValueError):
        return 'est. ~15min'
    if km < 2:
        return 'est. ~5min'
    if km < 5:
        return 'est. ~10min'
    if km < 15:
        return 'est. ~20min'
    return f'est. ~{int(km * 2.5)}min'


def _build_rescue_lines(units, county: str) -> tuple[list[str], str]:
    """Build rescue contact lines and extract top phone for flash SMS."""
    lines = []
    top_phone = ''
    if not units:
        lines = [
            '  1. Police/Response: 999 / 112',
            f'  2. Red Cross ({county}): 0700 395 395',
            f'  3. {county} Hospital: 0800 721 211'
        ]
        return lines, '999'

    for i, unit in enumerate(units[:3]):
        unit_type = str(unit.responder_unit_type or 'rescue').replace('_', ' ')
        distance = getattr(unit, 'distance_m', None)
        eta = _estimate_response_time(distance)
        try:
            dist_str = f'{int(float(str(distance).replace(" m", "")))}m'
        except (TypeError, ValueError):
            dist_str = '—'
        line = f'  {i + 1}. {unit.full_name} ({unit_type}) {unit.phone_number} [{dist_str}, {eta}]'
        lines.append(line)
        if i == 0:
            top_phone = unit.phone_number
    return lines, top_phone


def _build_rich_sms(risk: RiskAssessment, rescue_lines: list[str], county: str) -> str:
    """Build the full detailed SMS with all required info."""
    emoji = {'critical': '🔴', 'high': '🟠'}.get(risk.risk_level, '🟡')
    hazard_key = risk.hazard_type.lower().split()[0]
    info = _HAZARD_ACTIONS.get(hazard_key, _DEFAULT_ACTIONS)

    action_block = '\n'.join(f'  ✅ {a}' for a in info['actions'])
    dont_block = '\n'.join(f'  ❌ {d}' for d in info['donts'])
    rescue_block = '\n'.join(rescue_lines) if rescue_lines else '  Call county emergency center'

    sources = ", ".join(risk.data_sources_used) if risk.data_sources_used else "Open-Meteo"
    message = (
        f'{emoji} SAFEGUARD AI — {risk.risk_level.upper()} ALERT\n'
        f'Hazard: {risk.hazard_type.title()}\n'
        f'Location: {risk.ward_name}, {county}\n'
        f'Probability: {int(risk.risk_score)}%\n'
        f'Verified by: {sources}\n'
        f'Situation: {risk.summary}\n\n'
        f'ACTION STEPS:\n{action_block}\n\n'
        f'DO NOT:\n{dont_block}\n\n'
        f'RESCUE CONTACTS:\n{rescue_block}\n\n'
        f'Guidance: {risk.guidance_en}'
    )
    return message


def _build_flash_sms(risk: RiskAssessment, county: str, top_phone: str) -> str:
    """Build <160 char emergency SMS for CRITICAL alerts."""
    phone_str = f' Call {top_phone}' if top_phone else ''
    flash = (
        f'🔴 EMERGENCY: {risk.hazard_type.title()} in {risk.ward_name}, {county}. '
        f'EVACUATE NOW.{phone_str}'
    )
    return flash[:160]


@shared_task
def dispatch_risk_alerts_task(risk_assessment_id: int) -> dict:
    dispatcher = AlertDispatcher()
    risk = RiskAssessment.objects.get(id=risk_assessment_id)
    citizens = list(CitizenProfile.objects.filter(ward_name__iexact=risk.ward_name))
    sent_count = 0
    flash_count = 0

    # Resolve county name
    ward_boundary = WardBoundary.objects.filter(ward_name__iexact=risk.ward_name).first()
    county = ward_boundary.county_name if ward_boundary else 'Kenya'

    # Get nearest rescue units
    nearest_units = list(find_nearest_rescue_units(risk.location.x, risk.location.y))
    rescue_lines, top_phone = _build_rescue_lines(nearest_units, county)

    # Build messages
    rich_message = _build_rich_sms(risk, rescue_lines, county)
    flash_message = (
        _build_flash_sms(risk, county, top_phone)
        if risk.risk_level == RiskAssessment.RISK_CRITICAL
        else None
    )

    for citizen in citizens:
        # --- CRITICAL: send flash SMS first (<160 chars, arrives instantly) ---
        if flash_message and Alert.CHANNEL_SMS in citizen.channels:
            flash_alert = Alert.objects.create(
                risk_assessment=risk,
                citizen=citizen,
                channel=Alert.CHANNEL_SMS,
                message=flash_message,
            )
            try:
                flash_response = dispatcher.send_sms(
                    citizen.phone_number, flash_message, purpose='alert'
                )
                if flash_response.get('sent'):
                    flash_alert.status = Alert.STATUS_SENT
                    flash_alert.provider_response = flash_response
                    flash_alert.sent_at = timezone.now()
                    flash_alert.save(update_fields=['status', 'provider_response', 'sent_at'])
                    flash_count += 1
                else:
                    flash_alert.status = Alert.STATUS_FAILED
                    flash_alert.provider_response = flash_response
                    flash_alert.save(update_fields=['status', 'provider_response'])
            except Exception as exc:
                flash_alert.status = Alert.STATUS_FAILED
                flash_alert.provider_response = {'error': str(exc)}
                flash_alert.save(update_fields=['status', 'provider_response'])

        # --- Full detailed SMS/WhatsApp/Push ---
        for channel in citizen.channels:
            alert = Alert.objects.create(
                risk_assessment=risk,
                citizen=citizen,
                channel=channel,
                message=rich_message,
            )
            try:
                if channel == Alert.CHANNEL_SMS:
                    provider_response = dispatcher.send_sms(
                        citizen.phone_number, rich_message, purpose='alert'
                    )
                elif channel == Alert.CHANNEL_WHATSAPP:
                    provider_response = dispatcher.send_whatsapp(
                        citizen.phone_number, rich_message
                    )
                else:
                    provider_response = dispatcher.send_push(citizen.id, rich_message)

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

    # Follow-up ground-truth prompt after major threats
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
                pass

    return {
        'sent_alerts': sent_count,
        'flash_alerts': flash_count,
        'citizens_notified': len(citizens),
    }


@shared_task
def send_periodic_risk_updates_task() -> dict:
    dispatcher = AlertDispatcher()
    
    # Get active high/critical risks that are less than 24 hours old
    time_threshold = timezone.now() - timezone.timedelta(hours=24)
    active_risks = RiskAssessment.objects.filter(
        risk_level__in=[RiskAssessment.RISK_HIGH, RiskAssessment.RISK_CRITICAL],
        community_status__in=[RiskAssessment.COMMUNITY_PENDING, RiskAssessment.COMMUNITY_VERIFIED],
        issued_at__gte=time_threshold
    )

    update_count = 0
    for risk in active_risks:
        # Avoid sending updates too frequently by caching a marker per risk
        lock_key = f'periodic_update_sent_{risk.id}'
        if cache.get(lock_key):
            continue
            
        citizens = CitizenProfile.objects.filter(ward_name__iexact=risk.ward_name)
        if not citizens.exists():
            continue

        ward_boundary = WardBoundary.objects.filter(ward_name__iexact=risk.ward_name).first()
        county = ward_boundary.county_name if ward_boundary else 'Kenya'
        nearest_units = list(find_nearest_rescue_units(risk.location.x, risk.location.y))
        rescue_lines, _ = _build_rescue_lines(nearest_units, county)
        rescue_block = '\n'.join(rescue_lines) if rescue_lines else '  Call county emergency center'
        
        sources = ", ".join(risk.data_sources_used) if risk.data_sources_used else "Open-Meteo"
        message = (
            f'[Safeguard UPDATE] {risk.risk_level.upper()} ALERT Active.\n'
            f'{risk.hazard_type.title()} in {risk.ward_name} remains critical.\n'
            f'Verified by: {sources}.\n'
            f'Continue following official guidance.\n\n'
            f'RESCUE CONTACTS:\n{rescue_block}'
        )

        for citizen in citizens:
            if Alert.CHANNEL_SMS in citizen.channels:
                try:
                    dispatcher.send_sms(citizen.phone_number, message, purpose='alert')
                    update_count += 1
                except Exception:
                    pass
                
        # Lock for 60 minutes (3600 seconds) so users aren't spammed before the next run
        cache.set(lock_key, True, timeout=3600)

    return {'periodic_updates_sent': update_count}
