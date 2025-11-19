from Academicos.models import Tarea
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Tarea)
def reprogramar_recordatorios(sender, instance, **kwargs):
    if kwargs.get('created', False):
        # Solo al crear
        from .tasks import programar_recordatorios_tareas
        programar_recordatorios_tareas.delay()
    else:
        # Al modificar fecha_vencimiento
        if 'fecha_vencimiento' in instance.get_dirty_fields(): 
            from .tasks import programar_recordatorios_tareas
            programar_recordatorios_tareas.delay()