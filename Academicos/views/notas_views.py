from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags
from django.utils import timezone
from django.template.loader import render_to_string
from django.db import models
from Edupro360.decoradores import require_permission
from Academicos.models import PeriodoAcademico, Asignatura, Tarea, Entrega, Calificacion
from Academicos.serializers import ( CalificacionSerializer )

# === CALIFICACIÓN (CRUD COMPLETO) ===

class CalificacionCRUDView(APIView):

    @require_permission(['view_calificacion'], app_label='Academicos')
    def get(self, request, pk=None):
        # Si viene pk → obtener una sola calificación
        if pk is not None:
            calificacion = get_object_or_404(Calificacion, pk=pk)
            serializer = CalificacionSerializer(calificacion)
            return Response(serializer.data)

        # Si NO viene pk → listar todas las calificaciones
        calificaciones = Calificacion.objects.all()
        serializer = CalificacionSerializer(calificaciones, many=True)
        return Response(serializer.data)

    @require_permission(['can_grade_task'], app_label='Usuarios')
    def post(self, request):
        serializer = CalificacionSerializer(data=request.data)
        if serializer.is_valid():
            calificacion = serializer.save()
            entrega = calificacion.entrega
            entrega.estado_entrega = 'C'
            entrega.save()

            # === ENVÍO DE CORREO PROFESIONAL ===
            context = {
                'estudiante_nombre': entrega.estudiante.obtener_nombre_completo().title(),
                'tarea_titulo': entrega.tarea.titulo,
                'asignatura': entrega.tarea.asignatura.nombre,
                'nota': calificacion.nota,
                'comentario': calificacion.comentario or "Sin comentarios",
                'fecha_calificacion': calificacion.created_at.strftime("%d/%m/%Y a las %I:%M %p"),
                'plataforma_url': settings.FRONTEND_URL or 'http://localhost:5173',
                'year': timezone.now().year,
            }

            html_message = render_to_string('emails/calificacion_publicada.html', context)
            plain_message = strip_tags(html_message)

            send_mail(
                subject=f"¡Tienes una nueva calificación! - {entrega.tarea.titulo}",
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,  
                recipient_list=[entrega.estudiante.correo],
                html_message=html_message,
                fail_silently=False,
            )

            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


    @require_permission(['change_calificacion'], app_label='Academicos')
    def put(self, request, pk):
        calificacion = get_object_or_404(Calificacion, pk=pk)
        serializer = CalificacionSerializer(calificacion, data=request.data, partial=True)
        if serializer.is_valid():
            calificacion = serializer.save()

            # === CORREO DE ACTUALIZACIÓN ===
            context = {
                'estudiante_nombre': calificacion.entrega.estudiante.obtener_nombre_completo().title(),
                'tarea_titulo': calificacion.entrega.tarea.titulo,
                'asignatura': calificacion.entrega.tarea.asignatura.nombre,
                'nota_anterior': calificacion._previous_nota if hasattr(calificacion, '_previous_nota') else calificacion.nota,
                'nota_nueva': calificacion.nota,
                'comentario': calificacion.comentario or "Sin comentarios adicionales",
                'plataforma_url': settings.FRONTEND_URL or 'http://localhost:5173',
                'year': timezone.now().year,
            }

            html_message = render_to_string('emails/calificacion_actualizada.html', context)
            plain_message = strip_tags(html_message)

            send_mail(
                subject=f"Calificación actualizada - {calificacion.entrega.tarea.titulo}",
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[calificacion.entrega.estudiante.correo],
                html_message=html_message,
                fail_silently=False,
            )

            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @require_permission(['delete_calificacion'], app_label='Academicos')
    def delete(self, request, pk):
        calificacion = get_object_or_404(Calificacion, pk=pk)
        entrega = calificacion.entrega
        calificacion.delete()
        entrega.estado_entrega = 'E'
        entrega.save()
        return Response(status=204)


# === MIS NOTAS ===

class MisNotasView(APIView):
    @require_permission(['can_view_own_grades'], app_label='Usuarios')
    def get(self, request):
        return self._get_notas(request.user)

    def _get_notas(self, estudiante, periodo_id=None, asignatura_id=None):
        asignaturas = Asignatura.objects.filter(estado=True)

        if periodo_id:
            asignaturas = asignaturas.filter(periodo_academico_id=periodo_id)
        if asignatura_id:
            asignaturas = asignaturas.filter(id=asignatura_id)

        data = []
        for asignatura in asignaturas:
            tareas = Tarea.objects.filter(asignatura=asignatura, estado=True)
            notas_tareas = []

            for tarea in tareas:
                entrega = Entrega.objects.filter(tarea=tarea, estudiante=estudiante).first()
                calificacion = entrega.calificacion if entrega and hasattr(entrega, 'calificacion') else None

                estado = "Calificada" if calificacion else ("Entregada" if entrega else "Pendiente")

                notas_tareas.append({
                    "id_tarea": tarea.id,
                    "titulo": tarea.titulo,
                    "tipo_tarea": tarea.get_tipo_tarea_display(),
                    "peso_porcentual": float(tarea.peso_porcentual),
                    "nota": float(calificacion.nota) if calificacion else None,
                    "retroalimentacion": calificacion.retroalimentacion_docente if calificacion else None,
                    "estado": estado,
                    "fecha_entrega": entrega.fecha_entrega.isoformat() if entrega else None,
                })

            promedio = self._calcular_promedio(estudiante, asignatura)
            peso_calificado = self._peso_calificado(estudiante, asignatura)

            data.append({
                "id_asignatura": asignatura.id,
                "asignatura": asignatura.nombre,
                "codigo": asignatura.codigo,
                "periodo": asignatura.periodo_academico.nombre,
                "docente": asignatura.docente_responsable.__str__() if asignatura.docente_responsable else "Sin docente",
                "tareas": notas_tareas,
                "promedio_ponderado": round(promedio, 2),
                "peso_calificado_%": peso_calificado
            })

        data.sort(key=lambda x: (x['periodo'], x['asignatura']))
        return Response(data)

    def _calcular_promedio(self, estudiante, asignatura):
        entregas = Entrega.objects.filter(
            tarea__asignatura=asignatura,
            estudiante=estudiante,
            estado_entrega='C'
        ).select_related('calificacion', 'tarea')

        total = sum(
            (e.calificacion.nota * e.tarea.peso_porcentual / 100)
            for e in entregas if e.calificacion
        )
        return total

    def _peso_calificado(self, estudiante, asignatura):
        peso = Entrega.objects.filter(
            tarea__asignatura=asignatura,
            estudiante=estudiante,
            estado_entrega='C'
        ).aggregate(total=models.Sum('tarea__peso_porcentual'))['total'] or 0
        return float(peso)

class MisNotasPorPeriodoView(APIView):
    @require_permission(['can_view_own_grades'], app_label='Usuarios')
    def get(self, request, periodo_id):
        get_object_or_404(PeriodoAcademico, id=periodo_id, estado=True)
        view = MisNotasView()
        return view._get_notas(request.user, periodo_id=periodo_id)


class MisNotasPorAsignaturaView(APIView):
    @require_permission(['can_view_own_grades'], app_label='Usuarios')
    def get(self, request, asignatura_id):
        get_object_or_404(Asignatura, id=asignatura_id, estado=True)
        view = MisNotasView()
        return view._get_notas(request.user, asignatura_id=asignatura_id)


class MisNotasResumenView(APIView):
    @require_permission(['can_view_own_grades'], app_label='Usuarios')
    def get(self, request):
        estudiante = request.user
        data = []
        for asignatura in Asignatura.objects.filter(estado=True):
            promedio = MisNotasView()._calcular_promedio(estudiante, asignatura)
            peso = MisNotasView()._peso_calificado(estudiante, asignatura)
            if peso > 0 or promedio > 0:
                data.append({
                    "id": asignatura.id,
                    "asignatura": asignatura.nombre,
                    "codigo": asignatura.codigo,
                    "periodo": asignatura.periodo_academico.nombre,
                    "promedio": round(promedio, 2),
                    "peso_calificado_%": peso
                })
        data.sort(key=lambda x: (x['periodo'], x['asignatura']))
        return Response(data)