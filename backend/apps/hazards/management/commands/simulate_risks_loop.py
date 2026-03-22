from django.core.management.base import BaseCommand
from time import sleep
from django.utils import timezone
from django.db import transaction
from apps.hazards.management.commands.simulate_risks import Command as SimulateRisksCommand

class Command(BaseCommand):
    help = 'Continuously simulate real-time risk events for all wards (every 60 seconds).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting real-time risk simulation loop...'))
        while True:
            with transaction.atomic():
                SimulateRisksCommand().handle()
            self.stdout.write(self.style.SUCCESS(f'[{timezone.now()}] Simulated risk events.'))
            sleep(60)
