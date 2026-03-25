import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeguard_ai.settings')
django.setup()

from apps.hazards.tasks import ingest_hazard_data_task
from apps.hazards.models import RiskAssessment

# Clean up
RiskAssessment.objects.filter(ward_name='Westlands', hazard_type='flood').delete()

# Call the task with demo mode
result = ingest_hazard_data_task(force_demo_ward='Westlands')
print('Task result:', result)

# verify it was saved
risk = RiskAssessment.objects.filter(ward_name='Westlands').order_by('-issued_at').first()
print('Risk saved:', risk.risk_level if risk else 'None')
