# Notificaciones/management/commands/setup_periodic_tasks.py
from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, CrontabSchedule

class Command(BaseCommand):
    help = 'Configura las tareas periódicas de Celery Beat de forma segura'

    def handle(self, *args, **options):
        # === REPORTE MENSUAL: Día 1 de cada mes a las 8:00 AM ===
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='8',
            day_of_week='*',
            day_of_month='1',
            month_of_year='*',
            defaults={'timezone': 'America/Bogota'}
        )

        PeriodicTask.objects.update_or_create(
            crontab=schedule,
            name='Reporte Mensual Automático - 8:00 AM Día 1',
            defaults={
                'task': 'Notificaciones.tasks.generar_reporte_mensual',
                'enabled': True
            }
        )

        # === RECORDATORIOS DIARIOS a las 9:00 AM ===
        daily_schedule, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='9',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
            defaults={'timezone': 'America/Bogota'}
        )

        PeriodicTask.objects.update_or_create(
            crontab=daily_schedule,
            name='Revisar y programar recordatorios de tareas',
            defaults={
                'task': 'Notificaciones.tasks.programar_recordatorios_tareas',
                'enabled': True
            }
        )

        self.stdout.write(
            self.style.SUCCESS('¡Tareas periódicas configuradas correctamente!')
        )