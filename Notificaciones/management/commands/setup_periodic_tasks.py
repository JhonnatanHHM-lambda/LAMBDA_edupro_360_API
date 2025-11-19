from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, CrontabSchedule

class Command(BaseCommand):
    help = 'Configura las tareas periódicas de Celery Beat (reporte mensual, recordatorios, etc.)'

    def handle(self, *args, **options):
        # === REPORTE MENSUAL: Día 1 de cada mes a las 8:00 AM ===
        schedule, created = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='8',
            day_of_month='1',
            month_of_year='*',
            timezone='America/Bogota'  
        )

        PeriodicTask.objects.get_or_create(
            crontab=schedule,
            name='Reporte Mensual Automático - 8:00 AM Día 1',
            task='Academicos.tasks.generar_reporte_mensual',
            defaults={'enabled': True}
        )

        # === PROGRAMAR RECORDATORIOS DIARIAMENTE ===
        daily_schedule, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='9',  # Todos los días a las 9:00 AM
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )

        PeriodicTask.objects.get_or_create(
            crontab=daily_schedule,
            name='Revisar y programar recordatorios de tareas',
            task='Academicos.tasks.programar_recordatorios_tareas',
            defaults={'enabled': True}
        )

        self.stdout.write(
            self.style.SUCCESS('¡Tareas periódicas configuradas correctamente!')
        )