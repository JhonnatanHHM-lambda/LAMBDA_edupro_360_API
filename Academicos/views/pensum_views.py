from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from Edupro360.decoradores import require_permission
from Academicos.models import PeriodoAcademico, Asignatura, Inscripcion
from Academicos.serializers import (
    PeriodoAcademicoSerializer, AsignaturaSerializer, InscripcionSerializer
)

class PeriodoAcademicoCRUDView(APIView):
    @require_permission(['add_periodoacademico'], app_label='Academicos')
    def post(self, request):
        serializer = PeriodoAcademicoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    @require_permission(['view_periodoacademico'], app_label='Academicos')
    def get(self, request, pk=None):
        if pk:
            periodo = get_object_or_404(PeriodoAcademico, pk=pk, estado=True)
            serializer = PeriodoAcademicoSerializer(periodo)
        else:
            periodos = PeriodoAcademico.objects.filter(estado=True)
            serializer = PeriodoAcademicoSerializer(periodos, many=True)
        return Response(serializer.data)

    @require_permission(['change_periodoacademico'], app_label='Academicos')
    def put(self, request, pk):
        periodo = get_object_or_404(PeriodoAcademico, pk=pk, estado=True)
        serializer = PeriodoAcademicoSerializer(periodo, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @require_permission(['delete_periodoacademico'], app_label='Academicos')
    def delete(self, request, pk):
        periodo = get_object_or_404(PeriodoAcademico, pk=pk)
        periodo.estado = False
        periodo.save()
        return Response(status=204)


class AsignaturaCRUDView(APIView):
    @require_permission(['add_asignatura'], app_label='Academicos')
    def post(self, request):
        serializer = AsignaturaSerializer(data=request.data)
        if serializer.is_valid():
            asignatura = serializer.save()
            if asignatura.docente_responsable:
                send_mail(
                    "Asignatura asignada",
                    f"Has sido asignado a: {asignatura.nombre}",
                    settings.EMAIL_HOST_USER,
                    [asignatura.docente_responsable.correo]
                )
                pass
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    @require_permission(['view_asignatura'], app_label='Academicos')
    def get(self, request, pk=None):
        if pk:
            asignatura = get_object_or_404(Asignatura, pk=pk, estado=True)
            serializer = AsignaturaSerializer(asignatura)
        else:
            asignaturas = Asignatura.objects.filter(estado=True)
            serializer = AsignaturaSerializer(asignaturas, many=True)
        return Response(serializer.data)

    @require_permission(['change_asignatura'], app_label='Academicos')
    def put(self, request, pk):
        asignatura = get_object_or_404(Asignatura, pk=pk, estado=True)
        serializer = AsignaturaSerializer(asignatura, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @require_permission(['delete_asignatura'], app_label='Academicos')
    def delete(self, request, pk):
        asignatura = get_object_or_404(Asignatura, pk=pk)
        asignatura.estado = False
        asignatura.save()
        return Response(status=204)

class InscribirAsignaturaView(APIView):
    @require_permission(['puede_inscribirse'], app_label='Academicos')
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
    def get(self, request):
        inscripciones = Inscripcion.objects.filter(
            estudiante=request.user,
            estado=True
        ).select_related('asignatura__periodo_academico', 'asignatura__docente_responsable')

        data = []
        for insc in inscripciones:
            data.append({
                "id": insc.id,
                "asignatura_id": insc.asignatura.id,
                "nombre": insc.asignatura.nombre,
                "codigo": insc.asignatura.codigo,
                "docente": insc.asignatura.docente_responsable.get_full_name() if insc.asignatura.docente_responsable else "Sin docente",
                "periodo": insc.asignatura.periodo_academico.nombre,
                "fecha_inscripcion": insc.fecha_inscripcion
            })
        return Response(data)


class RetirarInscripcionView(APIView):
    @require_permission(['puede_inscribirse'], app_label='Academicos')
    def delete(self, request, inscripcion_id):
        inscripcion = get_object_or_404(
            Inscripcion,
            id=inscripcion_id,
            estudiante=request.user,
            estado=True
        )
        inscripcion.estado = False
        inscripcion.save()
        return Response({"detail": "Te has retirado de la asignatura"}, status=200)