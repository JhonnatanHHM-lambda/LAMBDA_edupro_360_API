from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_save
from django.dispatch import receiver

from Academicos.models import Tarea

from Notificaciones.tasks import programar_recordatorios_tareas

@receiver(post_save, sender=Tarea)
def reprogramar_recordatorios(sender, instance, **kwargs):
    """
    Reprograma los recordatorios cuando:
    - Se crea una nueva tarea
    - Se modifica la fecha de vencimiento de una tarea existente
    """


    if kwargs.get('created', False):

        programar_recordatorios_tareas.delay()
        return

    # verificar si cambió fecha_vencimiento
    try:
        # Obtener el estado ANTES de guardar
        old_instance = Tarea.objects.get(pk=instance.pk)
        if old_instance.fecha_vencimiento != instance.fecha_vencimiento:
            programar_recordatorios_tareas.delay()
    except ObjectDoesNotExist:
        # Si por alguna razón no existe (raro), reprogramamos igual
        programar_recordatorios_tareas.delay()