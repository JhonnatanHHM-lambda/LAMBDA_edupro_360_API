from celery import shared_task
from datetime import date
from django.db.models import Avg
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from django.utils import timezone
from Academicos.models import Tarea, Entrega, Asignatura
from Usuarios.models import Usuario
import logging

logger = logging.getLogger(__name__)

@shared_task
def enviar_recordatorio_tarea(tarea_id, tipo_recordatorio):
    try:
        tarea = Tarea.objects.get(id=tarea_id, estado=True)
        asignatura = tarea.asignatura
        docente = asignatura.docente_responsable
        fecha_vencimiento = tarea.fecha_vencimiento

        # Enviar recordatorio
        estudiantes = Usuario.objects.filter(
            inscripciones__asignatura=asignatura,
            inscripciones__estado=True,
            groups__name='Estudiante'
        ).distinct()

        subject = f"Recordatorio: {tarea.titulo} ({tipo_recordatorio})"
        mensaje = f"""
        ¡Hola!

        Recordatorio de tarea pendiente:
        - Asignatura: {asignatura.nombre}
        - Tarea: {tarea.titulo}
        - Tipo: {tarea.get_tipo_tarea_display()}
        - Fecha de vencimiento: {fecha_vencimiento.strftime('%d/%m/%Y %I:%M %p')}
        - Docente: {docente.get_full_name() if docente else 'No asignado'}

        Por favor entrega a tiempo.
        """

        destinatarios = list(estudiantes.values_list('correo', flat=True))
        if tipo_recordatorio == "1 día antes":
            if docente:
                destinatarios.append(docente.correo)

        send_mail(
            subject=subject,
            message=mensaje,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=destinatarios,
            fail_silently=False,
        )
        logger.info(f"Recordatorio {tipo_recordatorio} enviado para tarea {tarea.id}")
    except Exception as e:
        logger.error(f"Error enviando recordatorio: {e}")

@shared_task
def generar_reporte_mensual():

    hoy = date.today()
    mes_actual = hoy.strftime("%B %Y")

    # Métricas generales
    asignaturas = Asignatura.objects.filter(estado=True)
    reporte = f"REPORTE MENSUAL ACADÉMICO - {mes_actual}\n"
    reporte += "="*60 + "\n\n"

    for asignatura in asignaturas:
        entregas = Entrega.objects.filter(tarea__asignatura=asignatura)
        calificadas = entregas.filter(estado_entrega='C', calificacion__isnull=False)
        total_estudiantes = asignatura.inscripciones.filter(estado=True).count()
        promedio = calificadas.aggregate(avg=Avg('calificacion__nota'))['avg'] or 0
        aprobados = calificadas.filter(calificacion__nota__gte=60).count()
        tasa_aprobacion = (aprobados / calificadas.count() * 100) if calificadas.count() > 0 else 0

        reporte += f"{asignatura.nombre} ({asignatura.codigo})\n"
        reporte += f"   Período: {asignatura.periodo_academico.nombre}\n"
        reporte += f"   Estudiantes: {total_estudiantes}\n"
        reporte += f"   Promedio: {promedio:.2f}\n"
        reporte += f"   Tasa de aprobación: {tasa_aprobacion:.1f}%\n\n"

    # Enviar a usuarios con permiso
    usuarios = Usuario.objects.filter(
        user_permissions__codename='can_receive_monthly_report'
    ).distinct()

    send_mail(
        subject=f"Reporte Mensual Académico - {mes_actual}",
        message=reporte,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=list(usuarios.values_list('correo', flat=True)),
        fail_silently=False,
    )


@shared_task
def programar_recordatorios_tareas():

    hoy = timezone.now()
    tres_dias = hoy + timedelta(days=3)
    un_dia = hoy + timedelta(days=1)

    tareas_proximas = Tarea.objects.filter(
        estado=True,
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=tres_dias
    )

    for tarea in tareas_proximas:
        delta = tarea.fecha_vencimiento - hoy

        if abs(delta.days) == 3:
            tipo = "3 días antes"
            enviar_recordatorio_tarea.apply_async(
                args=[tarea.id, tipo],
                eta=tarea.fecha_vencimiento - timedelta(days=3)
            )
        elif abs(delta.days) == 1:
            tipo = "1 día antes"
            enviar_recordatorio_tarea.apply_async(
                args=[tarea.id, tipo],
                eta=tarea.fecha_vencimiento - timedelta(days=1)
            )