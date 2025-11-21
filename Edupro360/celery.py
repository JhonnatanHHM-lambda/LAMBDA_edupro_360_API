from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Edupro360.settings')

app = Celery('Edupro360')

# Cargar configuración desde settings.py con prefijo CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descubre tareas en apps registradas en INSTALLED_APPS
app.autodiscover_tasks()
