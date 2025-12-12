from django.db import models
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from Academicos.models import PeriodoAcademico, Asignatura, Tarea, Entrega, Calificacion, Inscripcion
from Academicos.serializers import CalificacionSerializer
from Notificaciones.tasks import (
    enviar_correo_calificacion_modificada,
    enviar_correo_calificacion_nueva
)
from Edupro360.decoradores import require_permission
from decimal import Decimal


# ==================== CALIFICACIÓN (CRUD COMPLETO) ====================
class CalificacionCRUDView(APIView):

    @require_permission(['view_calificacion'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Listar todas las calificaciones o una específica",
        operation_description="""
        • Sin pk → lista todas las calificaciones  
        • Con pk en la URL → devuelve solo esa calificación
        """,
        responses={
            200: CalificacionSerializer(many=True)
        },
        tags=['Calificaciones - Docente']
    )
    def get(self, request, pk=None):
        if pk is not None:
            calificacion = get_object_or_404(Calificacion, pk=pk)
            serializer = CalificacionSerializer(calificacion)
            return Response(serializer.data)

        calificaciones = Calificacion.objects.all()
        serializer = CalificacionSerializer(calificaciones, many=True)
        return Response(serializer.data)

    @require_permission(['can_grade_task'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Crear nueva calificación",
        operation_description="Califica una entrega y envía correo automático al estudiante (asíncrono con Celery)",
        request_body=CalificacionSerializer,
        responses={
            201: CalificacionSerializer,
            400: "Datos inválidos"
        },
        tags=['Calificaciones - Docente']
    )
    def post(self, request):
        serializer = CalificacionSerializer(data=request.data)
        if serializer.is_valid():
            calificacion = serializer.save()
            entrega = calificacion.entrega
            entrega.estado_entrega = 'C'
            entrega.save()
            enviar_correo_calificacion_nueva.delay(calificacion.id)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    @require_permission(['change_calificacion'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Actualizar calificación existente",
        operation_description="Modifica nota o retroalimentación. Envía correo de actualización al estudiante",
        request_body=CalificacionSerializer,
        responses={
            200: CalificacionSerializer,
            400: "Datos inválidos",
            404: "No encontrada"
        },
        tags=['Calificaciones - Docente']
    )
    def put(self, request, pk):
        calificacion = get_object_or_404(Calificacion, pk=pk)
        serializer = CalificacionSerializer(calificacion, data=request.data, partial=True)
        if serializer.is_valid():
            calificacion = serializer.save()
            enviar_correo_calificacion_modificada.delay(calificacion.id)
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @require_permission(['delete_calificacion'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Eliminar calificación",
        operation_description="Elimina la calificación y cambia estado de entrega a 'Entregada'",
        responses={
            204: "Calificación eliminada",
            404: "No encontrada"
        },
        tags=['Calificaciones - Docente']
    )
    def delete(self, request, pk):
        calificacion = get_object_or_404(Calificacion, pk=pk)
        entrega = calificacion.entrega
        calificacion.delete()
        entrega.estado_entrega = 'E'
        entrega.save()
        return Response(status=204)


# ==================== MIS NOTAS (ESTUDIANTE) ====================
class MisNotasView(APIView):
    @require_permission(['can_view_own_grades'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Mis notas completas",
        operation_description="Devuelve todas las tareas, notas, promedios y peso calificado por asignatura del estudiante autenticado",
        responses={200: openapi.Response(
            description="Lista detallada de notas por asignatura",
            examples={"application/json": [
                {
                    "id_asignatura": 1,
                    "asignatura": "Matemáticas",
                    "codigo": "MAT101",
                    "periodo": "2025-I",
                    "docente": "Dr. Pérez",
                    "promedio_ponderado": 85.5,
                    "peso_calificado_%": 70.0,
                    "tareas": [
                        {
                            "id_tarea": 5,
                            "titulo": "Tarea 1 - Álgebra",
                            "tipo_tarea": "Examen",
                            "peso_porcentual": 30.0,
                            "nota": 90.0,
                            "retroalimentacion": "Excelente trabajo",
                            "estado": "Calificada",
                            "fecha_entrega": "2025-11-10T15:30:00Z"
                        }
                        
                    ]
                }
            ]}
        )},
        tags=['Notas - Estudiante']
    )
    def get(self, request):
        return Response(self._get_notas(request.user))

    def _get_notas(self, estudiante, periodo_id=None, asignatura_id=None):
        # Filtros base: asignaturas inscritas activas
        filtros = Q(
            inscripciones_asignatura__estudiante=estudiante,
            inscripciones_asignatura__estado_inscripcion='A',
            estado=True
        )
        if periodo_id:
            filtros &= Q(periodo_academico_id=periodo_id)
        if asignatura_id:
            filtros &= Q(id=asignatura_id)

        asignaturas = Asignatura.objects.filter(filtros).select_related(
            'periodo_academico', 'docente_responsable'
        ).prefetch_related('tareas', 'tareas__entregas', 'tareas__entregas__calificacion')

        data = []
        for asignatura in asignaturas:
            promedio = self._calcular_promedio(estudiante, asignatura)
            peso_calificado = self._peso_calificado(estudiante, asignatura)

            tareas_data = []
            for tarea in asignatura.tareas.filter(estado=True):
                entrega = tarea.entregas.filter(estudiante=estudiante).first()
                if entrega and entrega.estado_entrega == 'C' and entrega.calificacion:
                    tareas_data.append({
                        "id_tarea": tarea.id,
                        "titulo": tarea.titulo,
                        "descripcion": tarea.descripcion or "",                    
                        "fecha_vencimiento": tarea.fecha_vencimiento.isoformat(),
                        "tipo_tarea": tarea.get_tipo_tarea_display(),
                        "peso_porcentual": float(tarea.peso_porcentual),
                        "nota": float(entrega.calificacion.nota),
                        "retroalimentacion": entrega.calificacion.retroalimentacion_docente or "",
                        "estado": "Calificada",
                        "fecha_entrega": entrega.fecha_entrega.isoformat() if entrega.fecha_entrega else None
                    })

            data.append({
                "id_asignatura": asignatura.id,
                "asignatura": asignatura.nombre,
                "codigo": asignatura.codigo,
                "periodo": asignatura.periodo_academico.nombre,
                "docente": asignatura.docente_responsable.obtener_nombre_completo() if asignatura.docente_responsable else "Sin asignar",
                "promedio_ponderado": round(float(promedio), 2),
                "peso_calificado_%": float(peso_calificado),
                "tareas": tareas_data
            })

        # Ordenar por período y asignatura
        data.sort(key=lambda x: (x['periodo'], x['asignatura']))
        return data

    def _calcular_promedio(self, estudiante, asignatura):
        entregas = Entrega.objects.filter(
            estudiante=estudiante,
            tarea__asignatura=asignatura,
            estado_entrega='C',
            calificacion__isnull=False
        ).select_related('tarea', 'calificacion')

        total_ponderado = Decimal('0.00')
        for entrega in entregas:
            total_ponderado += entrega.calificacion.nota * entrega.tarea.peso_porcentual / Decimal('100')
        return total_ponderado

    def _peso_calificado(self, estudiante, asignatura):
        entregas = Entrega.objects.filter(
            estudiante=estudiante,
            tarea__asignatura=asignatura,
            estado_entrega='C',
            calificacion__isnull=False
        ).select_related('tarea')

        total_peso = entregas.aggregate(
            total=models.Sum('tarea__peso_porcentual')
        )['total'] or Decimal('0.00')
        return total_peso


class MisNotasPorPeriodoView(APIView):
    @require_permission(['can_view_own_grades'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Mis notas por período académico",
        manual_parameters=[
            openapi.Parameter('periodo_id', openapi.IN_PATH, type=openapi.TYPE_INTEGER, description='ID del período')
        ],
        tags=['Notas - Estudiante']
    )
    def get(self, request, periodo_id):
        get_object_or_404(PeriodoAcademico, id=periodo_id, estado=True)
        view = MisNotasView()
        data = view._get_notas(request.user, periodo_id=periodo_id)
        return Response(data)


class MisNotasPorAsignaturaView(APIView):
    @require_permission(['can_view_own_grades'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Mis notas de una asignatura específica",
        manual_parameters=[
            openapi.Parameter('asignatura_id', openapi.IN_PATH, type=openapi.TYPE_INTEGER, description='ID de la asignatura')
        ],
        tags=['Notas - Estudiante']
    )
    def get(self, request, asignatura_id):
        get_object_or_404(Asignatura, id=asignatura_id, estado=True)
        view = MisNotasView()
        data = view._get_notas(request.user, asignatura_id=asignatura_id)
        return Response(data)


class MisNotasResumenView(APIView):
    @require_permission(['can_view_own_grades'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Resumen rápido de mis promedios",
        operation_description="Solo asignaturas con al menos una nota o peso calificado",
        responses={200: openapi.Response(
            description="Resumen compacto",
            examples={"application/json": [
                {"asignatura": "Matemáticas", "promedio": 88.5, "peso_calificado_%": 70}
            ]}
        )},
        tags=['Notas - Estudiante']
    )
    def get(self, request):
        estudiante = request.user
        view = MisNotasView()
        data = []
        asignaturas = Asignatura.objects.filter(
            inscripciones_asignatura__estudiante=estudiante,
            inscripciones_asignatura__estado_inscripcion='A',
            estado=True
        ).select_related('periodo_academico')

        for asignatura in asignaturas:
            promedio = view._calcular_promedio(estudiante, asignatura)
            peso = view._peso_calificado(estudiante, asignatura)
            if float(peso) > 0 or float(promedio) > 0:
                data.append({
                    "id": asignatura.id,
                    "asignatura": asignatura.nombre,
                    "codigo": asignatura.codigo,
                    "periodo": asignatura.periodo_academico.nombre,
                    "promedio": round(float(promedio), 2),
                    "peso_calificado_%": float(peso)
                })
        data.sort(key=lambda x: (x['periodo'], x['asignatura']))
        return Response(data)