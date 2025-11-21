from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from Edupro360.decoradores import require_permission

from Academicos.models import PeriodoAcademico, Asignatura, Inscripcion
from Academicos.serializers import (
    PeriodoAcademicoSerializer,
    AsignaturaSerializer,
    InscripcionSerializer,
)


# ==================== PERIODO ACADÉMICO ====================
class PeriodoAcademicoCRUDView(APIView):

    @require_permission(['add_periodoacademico'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Crear nuevo período académico",
        request_body=PeriodoAcademicoSerializer,
        responses={201: PeriodoAcademicoSerializer, 400: "Errores de validación"},
        tags=['Períodos Académicos']
    )
    def post(self, request):
        serializer = PeriodoAcademicoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    @require_permission(['view_periodoacademico'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Listar períodos activos o detalle por ID",
        operation_description="• Sin pk → lista todos los períodos activos\n• Con pk → detalle del período",
        responses={200: PeriodoAcademicoSerializer(many=True)},
        tags=['Períodos Académicos']
    )
    def get(self, request, pk=None):
        if pk:
            periodo = get_object_or_404(PeriodoAcademico, pk=pk, estado=True)
            serializer = PeriodoAcademicoSerializer(periodo)
        else:
            periodos = PeriodoAcademico.objects.filter(estado=True)
            serializer = PeriodoAcademicoSerializer(periodos, many=True)
        return Response(serializer.data)

    @require_permission(['change_periodoacademico'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Actualizar período académico",
        request_body=PeriodoAcademicoSerializer,
        responses={200: PeriodoAcademicoSerializer, 400: "Datos inválidos"},
        tags=['Períodos Académicos']
    )
    def put(self, request, pk):
        periodo = get_object_or_404(PeriodoAcademico, pk=pk, estado=True)
        serializer = PeriodoAcademicoSerializer(periodo, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @require_permission(['delete_periodoacademico'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Desactivar período académico",
        operation_description="Soft delete: cambia estado=False",
        responses={204: "Período desactivado"},
        tags=['Períodos Académicos']
    )
    def delete(self, request, pk):
        periodo = get_object_or_404(PeriodoAcademico, pk=pk)
        periodo.estado = False
        periodo.save()
        return Response(status=204)


# ==================== ASIGNATURA ====================
class AsignaturaCRUDView(APIView):

    @require_permission(['add_asignatura'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Crear nueva asignatura",
        operation_description="Envía correo automático al docente cuando se le asigna",
        request_body=AsignaturaSerializer,
        responses={201: AsignaturaSerializer, 400: "Errores de validación"},
        tags=['Asignaturas']
    )
    def post(self, request):
        serializer = AsignaturaSerializer(data=request.data)
        if serializer.is_valid():
            asignatura = serializer.save()

            if asignatura.docente_responsable:

                pass 

            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    @require_permission(['view_asignatura'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Listar asignaturas activas o detalle por ID",
        operation_description="• Sin pk → todas las asignaturas activas\n• Con pk → detalle",
        responses={200: AsignaturaSerializer(many=True)},
        tags=['Asignaturas']
    )
    def get(self, request, pk=None):
        if pk:
            asignatura = get_object_or_404(Asignatura, pk=pk, estado=True)
            serializer = AsignaturaSerializer(asignatura)
        else:
            asignaturas = Asignatura.objects.filter(estado=True)
            serializer = AsignaturaSerializer(asignaturas, many=True)
        return Response(serializer.data)

    @require_permission(['change_asignatura'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Actualizar asignatura",
        request_body=AsignaturaSerializer,
        responses={200: AsignaturaSerializer},
        tags=['Asignaturas']
    )
    def put(self, request, pk):
        asignatura = get_object_or_404(Asignatura, pk=pk, estado=True)
        serializer = AsignaturaSerializer(asignatura, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @require_permission(['delete_asignatura'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Desactivar asignatura",
        responses={204: "Asignatura desactivada"},
        tags=['Asignaturas']
    )
    def delete(self, request, pk):
        asignatura = get_object_or_404(Asignatura, pk=pk)
        asignatura.estado = False
        asignatura.save()
        return Response(status=204)


# ==================== INSCRIPCIÓN ====================
class InscribirAsignaturaView(APIView):
    @require_permission(['puede_inscribirse'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Inscribirse en una asignatura",
        operation_description="El estudiante autenticado se inscribe en una asignatura",
        request_body=InscripcionSerializer,
        responses={
            201: openapi.Response("Inscripción exitosa", examples={
                "application/json": {
                    "detail": "Inscripción exitosa",
                    "asignatura": "Matemáticas I",
                    "codigo": "MAT101"
                }
            })
        },
        tags=['Inscripciones - Estudiante']
    )
    def post(self, request):
        serializer = InscripcionSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            inscripcion = serializer.save(estudiante=request.user)
            return Response({
                "detail": "Inscripción exitosa",
                "asignatura": inscripcion.asignatura.nombre,
                "codigo": inscripcion.asignatura.codigo
            }, status=201)
        return Response(serializer.errors, status=400)


class MisAsignaturasView(APIView):
    @require_permission(['puede_inscribirse'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Mis asignaturas inscritas",
        operation_description="Lista todas las asignaturas en las que el estudiante está inscrito y activo",
        responses={200: openapi.Response(
            description="Lista de asignaturas inscritas",
            examples={"application/json": [
                {
                    "id": 5,
                    "asignatura_id": 12,
                    "nombre": "Cálculo II",
                    "codigo": "CAL201",
                    "docente": "Dr. María González",
                    "periodo": "2025-I",
                    "fecha_inscripcion": "2025-11-15T10:30:00Z"
                }
            ]}
        )},
        tags=['Inscripciones - Estudiante']
    )
    def get(self, request):
        try:
            inscripciones = Inscripcion.objects.filter(
                estudiante=request.user,
                estado_inscripcion="A"
            ).select_related(
                'asignatura',
                'asignatura__periodo_academico',
                'asignatura__docente_responsable'
            )

            data = []
            for insc in inscripciones:
                data.append({
                    "id": insc.id,
                    "asignatura_id": insc.asignatura.id,
                    "nombre": insc.asignatura.nombre,
                    "codigo": insc.asignatura.codigo,
                    "docente": insc.asignatura.docente_responsable.get_full_name()
                        if (insc.asignatura.docente_responsable and hasattr(insc.asignatura.docente_responsable, "get_full_name"))
                        else "Sin docente",
                    "periodo": getattr(insc.asignatura.periodo_academico, "nombre", "Sin periodo"),
                    "fecha_inscripcion": insc.fecha_inscripcion
                })
            return Response(data)

        except Exception as e:
            return Response({"error": "Error interno"}, status=500)


class RetirarInscripcionView(APIView):
    @require_permission(['puede_inscribirse'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Retirarse de una asignatura",
        operation_description="Cambia estado de inscripción a 'Retirada'",
        manual_parameters=[
            openapi.Parameter(
                'inscripcion_id',
                openapi.IN_PATH,
                type=openapi.TYPE_INTEGER,
                description='ID de la inscripción (no de la asignatura)'
            )
        ],
        responses={
            200: "Te has retirado de la asignatura",
            404: "Inscripción no encontrada o no pertenece al usuario"
        },
        tags=['Inscripciones - Estudiante']
    )
    def delete(self, request, inscripcion_id):
        inscripcion = get_object_or_404(
            Inscripcion,
            id=inscripcion_id,
            estudiante=request.user,
            estado_inscripcion="A"   
        )
        inscripcion.estado_inscripcion = "R"
        inscripcion.save()
        return Response(
            {"detail": "Te has retirado de la asignatura"},
            status=200
        )