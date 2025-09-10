# consultas/management/commands/purge_history.py
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from consultas.models import HistoricoConsulta # Ajuste o nome do seu modelo se for diferente

class Command(BaseCommand):
    help = 'Deletes records from HistoricoConsulta older than 2 weeks.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting data purging for HistoricoConsulta...'))

        # Calcula a data limite: 2 semanas atrás a partir de agora
        two_weeks_ago = timezone.now() - timedelta(weeks=2)

        try:
            deleted_count, _ = HistoricoConsulta.objects.filter(
                data_consulta__lt=two_weeks_ago
            ).delete()

            self.stdout.write(self.style.SUCCESS(
                f'Successfully deleted {deleted_count} records from HistoricoConsulta older than {two_weeks_ago}.'
            ))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'An error occurred during purging: {e}'))