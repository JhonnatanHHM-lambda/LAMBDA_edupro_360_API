import logging

from datetime import date, timedelta

import pandas as pd
from io import BytesIO

from celery import shared_task

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMultiAlternatives, get_connection, send_mail
from django.core.mail.message import EmailMultiAlternatives
from django.db import models
from django.db.models import Avg
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from Academicos.models import Asignatura, Entrega, Tarea
from Usuarios.models import Usuario

logger = logging.getLogger(__name__)

# Add this new task to tasks.py

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enviar_correo_asignatura_asignada(self, asignatura_id):
    """
    Tarea asíncrona con Celery para notificar al docente cuando se le asigna una nueva asignatura.
    Reintenta hasta 3 veces si falla (Gmail, red, etc.)
    """
    try:
        asignatura = Asignatura.objects.select_related('docente_responsable', 'periodo_academico').get(id=asignatura_id, estado=True)

        docente = asignatura.docente_responsable
        if not docente or not docente.is_active:
            logger.info(f"[Asignatura {asignatura_id}] No hay docente responsable activo para notificar.")
            return

        correo_docente = docente.correo
        if not correo_docente:
            logger.warning(f"[Asignatura {asignatura_id}] Docente sin correo configurado.")
            return

        context = {
            'docente_nombre': docente.obtener_nombre_completo().title(),
            'asignatura_nombre': asignatura.nombre.title(),
            'codigo': asignatura.codigo.upper(),
            'periodo': asignatura.periodo_academico.nombre.title(),
            'plataforma_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:5173'),
            'year': timezone.now().year,
        }

        # Renderizar plantilla HTML
        html_message = render_to_string('emails/asignatura_asignada.html', context)
        plain_message = strip_tags(html_message)

        # Enviar correo
        send_mail(
            subject=f"Nueva Asignatura Asignada: {asignatura.nombre}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[correo_docente],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"[Asignatura {asignatura_id}] Correo de asignatura asignada enviado a {correo_docente}")

    except Asignatura.DoesNotExist:
        logger.warning(f"[Asignatura {asignatura_id}] No encontrada o inactiva al enviar notificación")
    except Exception as e:
        logger.error(f"[Asignatura {asignatura_id}] Error enviando correo asignatura asignada: {e}", exc_info=True)
        # Reintenta automáticamente hasta 3 veces
        raise self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enviar_correo_tarea_nueva(self, tarea_id):
    """
    Tarea asíncrona con Celery para notificar a estudiantes cuando se crea una tarea nueva.
    Reintenta hasta 3 veces si falla (Gmail, red, etc.)
    """
    try:
        tarea = Tarea.objects.select_related('asignatura').get(id=tarea_id, estado=True)

        # Obtener correos de estudiantes activos e inscritos
        correos = list(
            tarea.asignatura.inscripciones_asignatura.filter(
                estado_inscripcion='A',
                estudiante__is_active=True
            )
            .values_list('estudiante__correo', flat=True)
            .distinct()
        )

        if not correos:
            logger.info(f"[Tarea {tarea_id}] No hay estudiantes inscritos para notificar.")
            return

        # Formatear fecha con zona horaria local
        fecha_local = timezone.localtime(tarea.fecha_vencimiento)

        context = {
            'tarea_titulo': tarea.titulo.title(),
            'asignatura_nombre': tarea.asignatura.nombre.title(),
            'asignatura_codigo': tarea.asignatura.codigo.upper(),
            'fecha_vencimiento': fecha_local.strftime('%d de %B del %Y a las %I:%M %p'),
            'descripcion': tarea.descripcion or "Sin descripción adicional.",
            'tipo_tarea': tarea.get_tipo_tarea_display(),
            'peso': tarea.peso_porcentual,
            'plataforma_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:5173'),
        }

        # Renderizar plantilla HTML
        html_message = render_to_string('emails/tarea_nueva.html', context)
        plain_message = strip_tags(html_message)

        # Enviar correo
        send_mail(
            subject=f"Nueva {tarea.get_tipo_tarea_display().lower()}: {tarea.titulo}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=correos,
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"[Tarea {tarea_id}] Correo de nueva tarea enviado a {len(correos)} estudiantes")

    except Tarea.DoesNotExist:
        logger.warning(f"[Tarea {tarea_id}] No encontrada o inactiva al enviar notificación")
    except Exception as e:
        logger.error(f"[Tarea {tarea_id}] Error enviando correo nueva tarea: {e}", exc_info=True)
        # Reintenta automáticamente hasta 3 veces
        raise self.retry(exc=e)


@shared_task
def enviar_recordatorio_tarea(tarea_id, tipo_recordatorio):
    try:
        tarea = Tarea.objects.select_related('asignatura', 'asignatura__docente_responsable').get(id=tarea_id, estado=True)
        asignatura = tarea.asignatura
        docente = asignatura.docente_responsable

        # === OBTENER TODOS LOS ESTUDIANTES INSCRITOS ACTIVOS ===
        estudiantes_inscritos = Usuario.objects.filter(
            inscripciones_estudiante__asignatura=asignatura,
            inscripciones_estudiante__estado_inscripcion='A',
            groups__name='Estudiante',
            is_active=True
        ).distinct()

        if not estudiantes_inscritos.exists():
            logger.info(f"No hay estudiantes inscritos para recordatorio de tarea {tarea_id}")
            return

        # === OBTENER QUIÉNES YA ENTREGARON (estado 'C', 'P' o 'E') ===
        entregas = Entrega.objects.filter(
            tarea=tarea,
            estado_entrega__in=['C', 'P', 'E']  # C=Calificada, P=Pendiente, E=Entregada
        ).values_list('estudiante_id', flat=True)

        estudiantes_que_entregaron = set(entregas)

        # === ESTUDIANTES QUE AÚN NO HAN ENTREGADO ===
        estudiantes_pendientes = [
            est for est in estudiantes_inscritos 
            if est.id not in estudiantes_que_entregaron
        ]

        if not estudiantes_pendientes:
            logger.info(f"Tarea {tarea_id}: Todos los estudiantes ya entregaron. No se envía recordatorio.")
            return

        # === PREPARAR CORREO ===
        context = {
            'tarea_titulo': tarea.titulo,
            'asignatura_nombre': asignatura.nombre,
            'tipo_tarea': tarea.get_tipo_tarea_display(),
            'fecha_vencimiento': tarea.fecha_vencimiento.strftime("%d de %B del %Y a las %I:%M %p"),
            'docente_nombre': docente.obtener_nombre_completo().title() if docente else "No asignado",
            'tipo_recordatorio': tipo_recordatorio,
            'url_tarea': f"{settings.FRONTEND_URL}/estudiante/tareas/{tarea.id}",
            'year': timezone.now().year,
            'total_pendientes': len(estudiantes_pendientes),
        }

        html_message = render_to_string('emails/recordatorio_tarea.html', context)
        plain_message = strip_tags(html_message)

        # === DESTINATARIOS: solo los que NO entregaron ===
        destinatarios = [est.correo for est in estudiantes_pendientes]

        # === Incluir al docente solo en "1 día antes" ===
        if tipo_recordatorio == "1 día antes" and docente and docente.is_active:
            destinatarios.append(docente.correo)
            context['es_docente'] = True  

        # === ENVIAR CORREO ===
        send_mail(
            subject=f"Recordatorio: {tarea.titulo} ({tipo_recordatorio}) - EduPro360",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=destinatarios,
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(
            f"Recordatorio '{tipo_recordatorio}' enviado para tarea '{tarea.titulo}' "
            f"a {len(destinatarios)} destinatarios "
            f"({len(estudiantes_pendientes)} estudiantes pendientes)"
        )

    except Tarea.DoesNotExist:
        logger.warning(f"Tarea {tarea_id} no encontrada o inactiva")
    except Exception as e:
        logger.error(f"Error enviando recordatorio tarea {tarea_id}: {e}", exc_info=True)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enviar_correo_tarea_modificada(self, tarea_id):
    try:
        tarea = Tarea.objects.select_related('asignatura').get(id=tarea_id, estado=True)

        # Obtener correos de estudiantes activos e inscritos
        correos = list(
            tarea.asignatura.inscripciones_asignatura.filter(
                estado_inscripcion='A',
                estudiante__is_active=True
            )
            .values_list('estudiante__correo', flat=True)
            .distinct()
        )

        if not correos:
            logger.info(f"[Tarea {tarea_id}] No hay estudiantes inscritos para notificar.")
            return

        # Formatear fecha con zona horaria local
        fecha_local = timezone.localtime(tarea.fecha_vencimiento)

        context = {
            'tarea_titulo': tarea.titulo.title(),
            'asignatura_nombre': tarea.asignatura.__str__,
            'asignatura_codigo': tarea.asignatura.codigo.upper(),
            'fecha_vencimiento': fecha_local.strftime('%d de %B del %Y a las %I:%M %p'),
            'descripcion': tarea.descripcion or "Sin descripción adicional.",
            'tipo_tarea': tarea.get_tipo_tarea_display(),
            'peso': tarea.peso_porcentual,
            'plataforma_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:5173'),
        }

        html_message = render_to_string('emails/tarea_modificada.html', context)
        plain_message = strip_tags(html_message)

        send_mail(
            subject=f"Actualización: {tarea.titulo} ha sido modificada",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=correos,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"CORREO DE TAREA MODIFICADA ENVIADO → ID {tarea_id}")

    except Tarea.DoesNotExist:
        logger.warning(f"Tarea {tarea_id} no existe al enviar modificación")
    except Exception as e:
        logger.error(f"Error enviando correo modificación: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def generar_reporte_mensual(self):
    try:
        from Academicos.models import Asignatura, Entrega, Tarea, Calificacion
        from Usuarios.models import Usuario

        hoy = date.today()
        mes_actual = hoy.strftime("%B %Y").title()
        logger.info(f"INICIANDO REPORTE MENSUAL COMPLETO: {mes_actual}")

        # === DATOS REALES PARA RESUMEN Y DETALLE ===
        resumen_data = []
        detalle_completo = []  

        asignaturas = Asignatura.objects.filter(estado=True).select_related('periodo_academico', 'docente_responsable')

        for asignatura in asignaturas:
            # Inscritos activos
            inscritos = asignatura.inscripciones_asignatura.filter(estado_inscripcion='A')
            total_inscritos = inscritos.count()

            # Entregas calificadas
            entregas_calificadas = Entrega.objects.filter(
                tarea__asignatura=asignatura,
                estado_entrega='C',
                calificacion__isnull=False
            ).select_related('estudiante', 'calificacion', 'tarea')

            estudiantes_con_nota = entregas_calificadas.values('estudiante').distinct().count()
            promedios = []
            aprobados = 0

            # === DETALLE POR ESTUDIANTE ===
        for asignatura in asignaturas:
            # Inscritos activos
            inscritos = asignatura.inscripciones_asignatura.filter(estado_inscripcion='A')
            total_inscritos = inscritos.count()

            # === TODAS LAS TAREAS DE LA ASIGNATURA ===
            todas_las_tareas = Tarea.objects.filter(asignatura=asignatura).order_by('fecha_vencimiento')

            # Todas las entregas (para saber qué se entregó y qué se calificó)
            entregas_dict = {
                (entrega.estudiante_id, entrega.tarea_id): entrega
                for entrega in Entrega.objects.filter(
                    tarea__asignatura=asignatura
                ).select_related('calificacion', 'tarea', 'estudiante')
            }

            promedios = []
            aprobados = 0

            # === POR CADA ESTUDIANTE INSCRITO ===
            for inscripcion in inscritos:
                estudiante = inscripcion.estudiante

                total_ponderado = 0.0
                peso_cubierto = 0.0
                tareas_calificadas_count = 0

                # === POR CADA TAREA DE LA ASIGNATURA (la mostramos TODAS) ===
                for tarea in todas_las_tareas:
                    entrega = entregas_dict.get((estudiante.id, tarea.id))

                    if entrega and entrega.estado_entrega == 'C' and entrega.calificacion:
                        # TAREA CALIFICADA
                        nota = float(entrega.calificacion.nota)
                        peso = float(tarea.peso_porcentual)
                        nota_ponderada = round(nota * (peso / 100), 2)

                        total_ponderado += nota_ponderada
                        peso_cubierto += peso
                        tareas_calificadas_count += 1

                        estado_tarea = "Calificada"
                        fecha_entrega = entrega.fecha_entrega.strftime('%d/%m/%Y %H:%M')
                        fecha_calificacion = entrega.calificacion.fecha_calificacion.strftime('%d/%m/%Y')
                    elif entrega and entrega.estado_entrega in ['P', 'E']:
                        # ENTREGADA pero no calificada
                        nota = "-"
                        nota_ponderada = "-"
                        estado_tarea = "Entregada (Pendiente calificar)"
                        fecha_entrega = entrega.fecha_entrega.strftime('%d/%m/%Y %H:%M')
                        fecha_calificacion = "-"
                    else:
                        # SIN ENTREGAR
                        nota = "-"
                        nota_ponderada = "-"
                        estado_tarea = "Sin entregar"
                        fecha_entrega = "-"
                        fecha_calificacion = "-"

                    # === AGREGAMOS UNA FILA POR CADA TAREA (¡TODAS!) ===
                    detalle_completo.append({
                        'Asignatura': asignatura.nombre,
                        'Código': asignatura.codigo,
                        'Docente': asignatura.docente_responsable.obtener_nombre_completo().title() if asignatura.docente_responsable else "Sin docente",
                        'Periodo': asignatura.periodo_academico.nombre,
                        'Estudiante': estudiante.obtener_nombre_completo().title(),
                        'Cédula': estudiante.cedula,
                        'Correo': estudiante.correo,
                        'Tarea': tarea.titulo,
                        'Tipo': tarea.get_tipo_tarea_display(),
                        'Peso (%)': tarea.peso_porcentual,
                        'Fecha Vencimiento': tarea.fecha_vencimiento.strftime('%d/%m/%Y'),
                        'Estado': estado_tarea,
                        'Nota': nota,
                        'Nota Ponderada': "-",
                        'Fecha Entrega': fecha_entrega,
                        'Fecha Calificación': fecha_calificacion,
                    })

                # === PROMEDIO FINAL DEL ESTUDIANTE ===
                promedio_estudiante = round(total_ponderado, 2) if peso_cubierto > 0 else 0.0
                estado_final = "Aprobado" if promedio_estudiante >= 60 else "Reprobado"

                if peso_cubierto > 0:
                    promedios.append(promedio_estudiante)
                    if promedio_estudiante >= 60:
                        aprobados += 1

                # === FILA RESUMEN POR ESTUDIANTE ===
                detalle_completo.append({
                    'Asignatura': asignatura.nombre,
                    'Código': '',
                    'Docente': '',
                    'Periodo': '',
                    'Estudiante': f"RESUMEN → {estudiante.obtener_nombre_completo().title()}",
                    'Cédula': '',
                    'Correo': '',
                    'Tarea': 'PROMEDIO FINAL',
                    'Tipo': '',
                    'Peso (%)': round(peso_cubierto, 2),
                    'Fecha Vencimiento': '',
                    'Estado': estado_final,
                    'Nota': '',
                    'Nota Ponderada': promedio_estudiante,
                    'Fecha Entrega': f"Tareas calificadas: {tareas_calificadas_count}/{todas_las_tareas.count()}",
                    'Fecha Calificación': '',
                })

            # === RESUMEN POR ASIGNATURA ===
            promedio_general = round(sum(promedios) / len(promedios), 2) if promedios else 0
            tasa_aprobacion = round((aprobados / total_inscritos) * 100, 1) if total_inscritos > 0 else 0

            resumen_data.append({
                'asignatura': asignatura.nombre,
                'codigo': asignatura.codigo,
                'docente': asignatura.docente_responsable.obtener_nombre_completo().title() if asignatura.docente_responsable else "Sin asignar",
                'periodo': asignatura.periodo_academico.nombre,
                'estudiantes': total_inscritos,
                'calificadas': len(promedios),
                'promedio': f"{promedio_general:.2f}",
                'tasa_aprobacion': f"{tasa_aprobacion}%",
            })

        if not resumen_data:
            logger.info("No hay datos académicos para el reporte")
            return "no_data"

        # === DESTINATARIOS ===
        try:
            permission = Permission.objects.get(codename='can_receive_monthly_report')
        except Permission.DoesNotExist:
            logger.error("Permiso no existe")
            return "permission_not_found"

        destinatarios = list(
            Usuario.objects.filter(
                models.Q(user_permissions=permission) |
                models.Q(groups__permissions=permission),
                is_active=True
            ).distinct().values_list('correo', flat=True)
        )

        if not destinatarios:
            logger.warning("No hay destinatarios")
            return "no_recipients"

        logger.info(f"ENVIANDO A: {destinatarios}")

        # === ENVÍO CON DATOS REALES EN HTML + EXCEL ===
        context = {
            'mes_actual': mes_actual,
            'fecha_generacion': hoy.strftime("%d de %B del %Y"),
            'total_asignaturas': len(resumen_data),
            'datos_reporte': resumen_data,  
            'year': hoy.year,
        }

        html_message = render_to_string('emails/reporte_mensual.html', context)
        plain_message = strip_tags(html_message)

        # === EXCEL ===
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame(resumen_data).to_excel(writer, sheet_name='Resumen General', index=False, startrow=3)
            pd.DataFrame(detalle_completo).to_excel(writer, sheet_name='Detalle Completo', index=False, startrow=3)

            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            from openpyxl.utils import get_column_letter
            from openpyxl.cell.cell import MergedCell

            # Colores institucionales
            azul_oscuro = "1f4e79"
            verde_aprobado = "d5e8d4"   # Verde claro
            rojo_reprobado = "f8d7da"   # Rojo claro
            blanco = "FFFFFF"

            header_font = Font(bold=True, color=blanco, size=12)
            header_fill = PatternFill(start_color=azul_oscuro, end_color=azul_oscuro, fill_type="solid")
            title_font = Font(size=18, bold=True, color=azul_oscuro)
            border = Border(left=Side(style='thin'), right=Side(style='thin'),
                            top=Side(style='thin'), bottom=Side(style='thin'))
            center = Alignment(horizontal='center', vertical='center', wrap_text=True)
            left = Alignment(horizontal='left', vertical='center', wrap_text=True)

            fill_verde = PatternFill(start_color=verde_aprobado, end_color=verde_aprobado, fill_type="solid")
            fill_rojo = PatternFill(start_color=rojo_reprobado, end_color=rojo_reprobado, fill_type="solid")

            for ws in writer.book.worksheets:
                last_col = get_column_letter(ws.max_column)

                # Título principal
                ws['A1'] = f"REPORTE MENSUAL ACADÉMICO - {mes_actual.upper()}"
                ws['A1'].font = title_font
                ws['A1'].alignment = center
                ws.merge_cells(f'A1:{last_col}1')

                ws['A2'] = f"Generado el: {hoy.strftime('%d de %B del %Y')}"
                ws.merge_cells(f'A2:{last_col}2')

                # Encabezados
                for cell in ws[4]:
                    if cell.value:
                        cell.font = header_font
                        cell.fill = header_fill
                        cell.alignment = center
                        cell.border = border

                # === PINTAR FILAS SEGÚN ESTADO (SOLO EN "Detalle Completo") ===
                if ws.title == "Detalle Completo":
                    # Buscar la columna "Estado"
                    estado_col_idx = None
                    for idx, cell in enumerate(ws[4], 1): 
                        if cell.value == "Estado":
                            estado_col_idx = idx
                            break

                    if estado_col_idx:
                        for row in ws.iter_rows(min_row=5, max_row=ws.max_row):
                            estado_cell = row[estado_col_idx - 1]
                            valor = estado_cell.value

                            # Solo pintamos las filas de RESUMEN (donde dice Aprobado/Reprobado)
                            if valor in ["Aprobado", "Aprobada"]:
                                for cell in row:
                                    if not isinstance(cell, MergedCell):
                                        cell.fill = fill_verde
                            elif valor in ["Reprobado", "Reprobada"]:
                                for cell in row:
                                    if not isinstance(cell, MergedCell):
                                        cell.fill = fill_rojo
                            # Opcional: pintar de gris claro las tareas "Sin entregar"
                            elif valor == "Sin entregar":
                                gris_claro = PatternFill(start_color="f2f2f2", end_color="f2f2f2", fill_type="solid")
                                for cell in row:
                                    if not isinstance(cell, MergedCell):
                                        cell.fill = gris_claro

                # Bordes y alineación general
                for row in ws.iter_rows(min_row=4, max_row=ws.max_row):
                    for cell in row:
                        if not isinstance(cell, MergedCell):
                            cell.border = border
                            if cell.column_letter in ['E','F','G','H','I','J','K','L','M','N']:
                                cell.alignment = center
                            else:
                                cell.alignment = left

                # Ancho de columnas (seguro)
                column_widths = {}
                for row in ws.iter_rows():
                    for cell in row:
                        if not isinstance(cell, MergedCell) and cell.value:
                            length = len(str(cell.value))
                            col = cell.column_letter
                            column_widths[col] = max(column_widths.get(col, 10), length + 2)
                for col, width in column_widths.items():
                    ws.column_dimensions[col].width = min(width + 4, 50)

                ws.freeze_panes = 'A5'

        output.seek(0)
        filename = f"Reporte_Mensual_{hoy.strftime('%Y_%m')}_Completo_EduPro360.xlsx"

        # === ENVÍO FINAL ===
        connection = get_connection(fail_silently=False, timeout=60)
        connection.open()

        email = EmailMultiAlternatives(
            subject=f"Reporte Mensual Académico - {mes_actual} - EduPro360",
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=destinatarios,
            connection=connection,
        )
        email.attach_alternative(html_message, "text/html")
        email.attach(filename, output.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        email.send()

        connection.close()
        logger.info("REPORTE MENSUAL COMPLETO ENVIADO CON ÉXITO")
        return "success"

    except Exception as e:
        logger.error(f"ERROR EN REPORTE: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task
def programar_recordatorios_tareas():
    """
    Se ejecuta 1 vez al día (con celery beat)
    Busca tareas que vencen en 1 o 3 días y programa recordatorios AUTOMÁTICOS
    """
    hoy = timezone.localtime(timezone.now()).date()
    logger.info(f"[RECORDATORIOS] Ejecutando programación diaria - {hoy}")

    # Fechas objetivo
    en_1_dia = hoy + timedelta(days=1)
    en_3_dias = hoy + timedelta(days=3)

    # Tareas que vencen exactamente en 1 o 3 días
    tareas_candidatas = Tarea.objects.filter(
        estado=True,
        fecha_vencimiento__date__in=[en_1_dia, en_3_dias]
    ).select_related('asignatura')

    programados = 0
    for tarea in tareas_candidatas:
        vencimiento_date = tarea.fecha_vencimiento.date()

        if vencimiento_date == en_1_dia:
            tipo = "1 día antes"
            eta = tarea.fecha_vencimiento - timedelta(days=1)
        elif vencimiento_date == en_3_dias:
            tipo = "3 días antes"
            eta = tarea.fecha_vencimiento - timedelta(days=3)
        else:
            continue

        # Evitar programar duplicados 
        from celery import current_app
        inspeccion = current_app.control.inspect()
        scheduled = inspeccion.scheduled() or {}
        reserved = inspeccion.reserved() or {}
        active = inspeccion.active() or {}

        ya_programada = any(
            "enviar_recordatorio_tarea" in str(task.get("request", {}))
            and task.get("request", {}).get("args", []) == [tarea.id, tipo]
            for queue in (scheduled, reserved, active)
            for task in queue.values()
        )

        if ya_programada:
            logger.info(f"Recordatorio '{tipo}' para tarea {tarea.id} ya está programado")
            continue

        # === PROGRAMAR EL RECORDATORIO ===
        enviar_recordatorio_tarea.apply_async(
            args=[tarea.id, tipo],
            eta=eta.replace(second=0, microsecond=0)  
        )
        logger.info(f"Programado recordatorio '{tipo}' para tarea '{tarea.titulo}' → {eta}")
        programados += 1

    logger.info(f"[RECORDATORIOS] Fin de programación diaria - {programados} recordatorios nuevos")

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


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enviar_correo_calificacion_nueva(self, calificacion_id):
    try:
        from Academicos.models import Calificacion
        from django.utils import timezone
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        from django.core.mail import send_mail
        from django.conf import settings

        calificacion = Calificacion.objects.select_related(
            'entrega__estudiante', 'entrega__tarea__asignatura'
        ).get(id=calificacion_id)

        entrega = calificacion.entrega
        estudiante = entrega.estudiante

        context = {
            'estudiante_nombre': estudiante.obtener_nombre_completo().title(),
            'tarea_titulo': entrega.tarea.titulo,
            'asignatura': entrega.tarea.asignatura.nombre,
            'nota': calificacion.nota,
            'comentario': calificacion.retroalimentacion_docente or "Sin comentarios",
            'fecha_calificacion': calificacion.fecha_calificacion.strftime("%d/%m/%Y a las %I:%M %p"),
            'plataforma_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:5173'),
            'year': timezone.now().year,
        }

        html_message = render_to_string('emails/calificacion_publicada.html', context)
        plain_message = strip_tags(html_message)

        send_mail(
            subject=f"¡Tienes una nueva calificación! - {entrega.tarea.titulo}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[estudiante.correo],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Correo de nueva calificación enviado a {estudiante.correo} - Tarea: {entrega.tarea.titulo}")

    except Exception as e:
        logger.error(f"Error enviando correo de calificación nueva (ID {calificacion_id}): {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enviar_correo_calificacion_modificada(self, calificacion_id):
    try:
        from Academicos.models import Calificacion
        from django.utils import timezone
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        from django.core.mail import send_mail
        from django.conf import settings

        calificacion = Calificacion.objects.select_related(
            'entrega__estudiante', 'entrega__tarea__asignatura'
        ).get(id=calificacion_id)

        entrega = calificacion.entrega

        context = {
            'estudiante_nombre': entrega.estudiante.obtener_nombre_completo().title(),
            'tarea_titulo': entrega.tarea.titulo,
            'asignatura': entrega.tarea.asignatura.nombre,
            'nota_nueva': calificacion.nota,
            'comentario': calificacion.retroalimentacion_docente or "Sin comentarios adicionales",
            'plataforma_url': getattr(settings, 'FRONTEND_URL', 'http://localhost:5173'),
            'year': timezone.now().year,
        }

        html_message = render_to_string('emails/calificacion_actualizada.html', context)
        plain_message = strip_tags(html_message)

        send_mail(
            subject=f"Calificación actualizada - {entrega.tarea.titulo}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[entrega.estudiante.correo],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Correo de calificación actualizada enviado a {entrega.estudiante.correo}")

    except Exception as e:
        logger.error(f"Error enviando correo de calificación modificada: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enviar_correo_recuperacion_contrasena(self, usuario_id):
    """
    Envía correo de recuperación usando el token guardado en el modelo Usuario
    """
    try:
        from Usuarios.models import Usuario
        from django.conf import settings
        from django.utils import timezone
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        from django.core.mail import send_mail

        user = Usuario.objects.get(id=usuario_id, is_active=True)

        # Verificar que el token exista y no haya expirado
        if not user.reset_password_token or not user.reset_password_token_expires_at:
            logger.warning(f"Usuario {user.correo} no tiene token de recuperación")
            return

        if timezone.now() > user.reset_password_token_expires_at:
            logger.warning(f"Token expirado para {user.correo}")
            return

        token = user.reset_password_token
        url_recuperacion = f"{settings.FRONTEND_URL}/restablecer-contrasena/{token}"

        context = {
            'nombre': user.obtener_nombre_completo().title(),
            'url_recuperacion': url_recuperacion,
            'expiracion_horas': 1,
            'year': timezone.now().year,
        }

        html_message = render_to_string('emails/recuperacion_contrasena.html', context)
        plain_message = strip_tags(html_message)

        send_mail(
            subject="Recupera tu contraseña - EduPro360",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.correo],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Correo de recuperación enviado a {user.correo}")

    except Usuario.DoesNotExist:
        logger.warning(f"Usuario ID {usuario_id} no existe o está inactivo")
    except Exception as e:
        logger.error(f"Error enviando correo de recuperación: {e}", exc_info=True)
        raise self.retry(exc=e)