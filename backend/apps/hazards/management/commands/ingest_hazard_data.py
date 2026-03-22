from django.core.management.base import BaseCommand

from apps.hazards.tasks import ingest_hazard_data_task


class Command(BaseCommand):
    help = 'Run the hazard ingestion + Gemini risk analysis pipeline once.'

    def handle(self, *args, **options):
        result = ingest_hazard_data_task()
        created = result.get('created_observations', 0)
        dispatched = result.get('dispatched_alert_jobs', 0)
        dedup_skipped = result.get('dedup_skipped_alert_jobs', 0)
        processed = result.get('processed_items', 0)
        self.stdout.write(
            self.style.SUCCESS(
                'Ingestion complete: '
                f'processed_items={processed}, '
                f'created_observations={created}, '
                f'dispatched_alert_jobs={dispatched}, '
                f'dedup_skipped_alert_jobs={dedup_skipped}'
            )
        )
