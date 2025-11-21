from django.db import models
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from Academicos.models import PeriodoAcademico, Asignatura, Tarea, Entrega, Calificacion
from Academicos.serializers import CalificacionSerializer
from Notificaciones.tasks import (
    enviar_correo_calificacion_modificada,
    enviar_correo_calificacion_nueva
)
from Edupro360.decoradores import require_permission


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
        return self._get_notas(request.user)


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
        return view._get_notas(request.user, periodo_id=periodo_id)


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
        return view._get_notas(request.user, asignatura_id=asignatura_id)


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