from celery import shared_task
from datetime import date
from django.db.models import Avg
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags
from django.utils import timezone
from django.template.loader import render_to_string
from datetime import timedelta
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

        estudiantes = Usuario.objects.filter(
            inscripciones_estudiante__asignatura=asignatura,
            inscripciones_estudiante__estado_inscripcion='A', 
            groups__name='Estudiante',
            is_active=True
        ).distinct()

        if not estudiantes.exists():
            logger.info(f"No hay estudiantes activos inscritos para recordatorio de tarea {tarea_id}")
            return

        context = {
            'tarea_titulo': tarea.titulo,
            'asignatura_nombre': asignatura.nombre,
            'tipo_tarea': tarea.get_tipo_tarea_display(),
            'fecha_vencimiento': tarea.fecha_vencimiento.strftime("%d de %B del %Y a las %I:%M %p"),
            'docente_nombre': docente.obtener_nombre_completo().title() if docente else "No asignado",
            'tipo_recordatorio': tipo_recordatorio,
            'url_tarea': f"{settings.FRONTEND_URL}/estudiante/tareas/{tarea.id}",
            'year': timezone.now().year,
        }

        html_message = render_to_string('emails/recordatorio_tarea.html', context)
        plain_message = strip_tags(html_message)

        destinatarios = list(estudiantes.values_list('correo', flat=True))
        if tipo_recordatorio == "1 día antes" and docente and docente.is_active:
            destinatarios.append(docente.correo)

        send_mail(
            subject=f"Recordatorio: {tarea.titulo} ({tipo_recordatorio}) - EduPro360",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=destinatarios,
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Recordatorio '{tipo_recordatorio}' enviado para tarea {tarea.id} a {len(destinatarios)} destinatarios")

    except Tarea.DoesNotExist:
        logger.warning(f"Tarea {tarea_id} no encontrada o inactiva")
    except Exception as e:
        logger.error(f"Error enviando recordatorio tarea {tarea_id}: {e}", exc_info=True)


@shared_task
def generar_reporte_mensual():
    hoy = date.today()
    mes_actual = hoy.strftime("%B %Y").title()

    asignaturas = Asignatura.objects.filter(estado=True).select_related('periodo_academico')
    datos_reporte = []

    def calcular_datos_asignatura(asignatura):
        entregas = Entrega.objects.filter(
            tarea__asignatura=asignatura,
            estado_entrega='C',
            calificacion__isnull=False
        ).select_related('calificacion', 'tarea', 'estudiante')

        if not entregas.exists():
            return 0.0, 0, 0.0

        total_ponderado = 0.0
        aprobados = 0
        procesados = set()

        for e in entregas:
            if e.estudiante.id in procesados:
                continue
            procesados.add(e.estudiante.id)


            pond = sum(
                float(x.calificacion.nota) * float(x.tarea.peso_porcentual) / 100
                for x in entregas.filter(estudiante=e.estudiante)
            )
            total_ponderado += pond
            if pond >= 60:
                aprobados += 1

        cant = len(procesados)
        if cant == 0:
            return 0.0, 0, 0.0

        promedio = round(total_ponderado / cant, 2)
        tasa = round((aprobados / cant) * 100, 1)
        return promedio, cant, tasa


    for asignatura in asignaturas:
        total_estudiantes = asignatura.inscripciones_asignatura.filter(estado_inscripcion='A').count()
        promedio, con_nota, tasa = calcular_datos_asignatura(asignatura)

        periodo = getattr(asignatura.periodo_academico, 'nombre', 'Sin período asignado')

        datos_reporte.append({
            'asignatura': asignatura.nombre,
            'codigo': asignatura.codigo,
            'periodo': periodo,
            'estudiantes': total_estudiantes,
            'calificadas': con_nota,
            'promedio': f"{promedio:.2f}" if con_nota > 0 else "—",
            'tasa_aprobacion': f"{tasa}%" if con_nota > 0 else "—",
        })

    if not datos_reporte:
        logger.info("No hay asignaturas con datos para reporte mensual")
        return

    # === DESTINATARIOS ===
    destinatarios = list(
        Usuario.objects.filter(
            user_permissions__codename='can_receive_monthly_report',
            is_active=True
        ).values_list('correo', flat=True)
    )

    if not destinatarios:
        logger.info("No hay usuarios con permiso 'can_receive_monthly_report'")
        return

    # === ENVÍO ===
    context = {
        'mes_actual': mes_actual,
        'fecha_generacion': hoy.strftime("%d de %B del %Y"),
        'total_asignaturas': len(datos_reporte),
        'datos_reporte': datos_reporte,
        'year': hoy.year,
    }

    html_message = render_to_string('emails/reporte_mensual.html', context)
    plain_message = strip_tags(html_message)

    send_mail(
        subject=f"Reporte Mensual Académico - {mes_actual} - EduPro360",
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=destinatarios,
        html_message=html_message,
        fail_silently=False,
    )

    logger.info(f"Reporte mensual enviado a {len(destinatarios)} destinatarios con promedio ponderado real")


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