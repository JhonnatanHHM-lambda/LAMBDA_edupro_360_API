from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from Edupro360.decoradores import require_permission
from .models import PeriodoAcademico, Asignatura, Tarea, Entrega, Calificacion
from .serializers import (
    PeriodoAcademicoSerializer, AsignaturaSerializer, TareaSerializer,
    EntregaSerializer, CalificacionSerializer
)


# === PERIODO ACADÉMICO (CRUD) ===
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


# === ASIGNATURA (CRUD) ===
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


# === TAREA (CRUD) ===
class TareaCRUDView(APIView):
    @require_permission(['add_tarea'], app_label='Academicos')
    def post(self, request):
        serializer = TareaSerializer(data=request.data)
        if serializer.is_valid():
            tarea = serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    @require_permission(['view_tarea'], app_label='Academicos')
    def get(self, request, pk=None):
        if pk:
            tarea = get_object_or_404(Tarea, pk=pk, estado=True)
            serializer = TareaSerializer(tarea)
        else:
            tareas = Tarea.objects.filter(estado=True)
            serializer = TareaSerializer(tareas, many=True)
        return Response(serializer.data)

    @require_permission(['change_tarea'], app_label='Academicos')
    def put(self, request, pk):
        tarea = get_object_or_404(Tarea, pk=pk, estado=True)
        serializer = TareaSerializer(tarea, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @require_permission(['delete_tarea'], app_label='Academicos')
    def delete(self, request, pk):
        tarea = get_object_or_404(Tarea, pk=pk)
        tarea.estado = False
        tarea.save()
        return Response(status=204)


# === ENTREGA ===

class EntregaCRUDView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    # POST: Crear entrega
    @require_permission(['can_submit_task'], app_label='Usuarios')
    def post(self, request):
        data = {
            'tarea': request.data.get('tarea'),
            'comentarios_estudiante': request.data.get('comentarios_estudiante'),
        }

        serializer = EntregaSerializer(data=data, context={'request': request})

        if serializer.is_valid():
            entrega = serializer.save(
                estudiante=request.user,
                archivo_entrega=request.FILES.get('archivo_entrega')
            )
            return Response(serializer.data, status=201)

        return Response(serializer.errors, status=400)

    # DELETE: Eliminar entrega

    @require_permission(['delete_entrega'], app_label='Academicos')
    def delete(self, request, pk):
        entrega = get_object_or_404(Entrega, pk=pk, estudiante=request.user)
        calificacion = getattr(entrega, 'calificacion', None)
        if calificacion:
            calificacion.delete()
        entrega.delete()
        return Response(status=204)

    # GET: Obtener entrega por pk

    @require_permission(['view_entrega'], app_label='Academicos')
    def get(self, request, pk=None):
        # Obtener entrega por pk
        if pk:
            # Docente puede ver cualquier entrega de sus asignaturas
            if request.user.groups.filter(name='Docente').exists():
                entrega = get_object_or_404(
                    Entrega,
                    pk=pk,
                    tarea__asignatura__docente_responsable=request.user
                )
            else:  # Estudiante solo puede ver su propia entrega
                entrega = get_object_or_404(Entrega, pk=pk, estudiante=request.user)

            calificacion = getattr(entrega, 'calificacion', None)
            data = {
                "id": entrega.id,
                "tarea": entrega.tarea.id,
                "archivo_entrega": entrega.archivo_entrega.url if entrega.archivo_entrega else None,
                "comentarios_estudiante": entrega.comentarios_estudiante,
                "fecha_entrega": entrega.fecha_entrega,
                "estado_entrega": entrega.estado_entrega,
                "nota": calificacion.nota if calificacion else None,
                "retroalimentacion": calificacion.retroalimentacion_docente if calificacion else None
            }
            return Response(data)
        
        # Listar todas las entregas
        if request.user.groups.filter(name='Docente').exists():
            entregas = Entrega.objects.filter(tarea__asignatura__docente_responsable=request.user)
        else:
            entregas = Entrega.objects.filter(estudiante=request.user)

        data = []
        for entrega in entregas:
            calificacion = getattr(entrega, 'calificacion', None)
            data.append({
                "id": entrega.id,
                "tarea": entrega.tarea.id,
                "archivo_entrega": entrega.archivo_entrega.url if entrega.archivo_entrega else None,
                "comentarios_estudiante": entrega.comentarios_estudiante,
                "fecha_entrega": entrega.fecha_entrega,
                "estado_entrega": entrega.estado_entrega,
                "nota": calificacion.nota if calificacion else None,
                "retroalimentacion": calificacion.retroalimentacion_docente if calificacion else None
            })
        return Response(data)
    
    
class MisEntregasView(APIView):
    @require_permission(['can_submit_task'], app_label='Usuarios')
    def get(self, request):
        entregas = Entrega.objects.filter(estudiante=request.user, estado=True)
        serializer = EntregaSerializer(entregas, many=True)
        return Response(serializer.data)

# === CALIFICACIÓN (CRUD COMPLETO) ===
class CalificacionCRUDView(APIView):
    @require_permission(['can_grade_task'], app_label='Usuarios')
    def post(self, request):
        serializer = CalificacionSerializer(data=request.data)
        if serializer.is_valid():
            calificacion = serializer.save()
            entrega = calificacion.entrega
            entrega.estado_entrega = 'C'
            entrega.save()
            send_mail(
                "Calificación publicada",
                f"Tu nota en {entrega.tarea.titulo}: {calificacion.nota}",
                settings.EMAIL_HOST_USER,
                [entrega.estudiante.correo]
            )
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    @require_permission(['can_grade_task'], app_label='Usuarios')
    def put(self, request, pk):
        calificacion = get_object_or_404(Calificacion, pk=pk)
        serializer = CalificacionSerializer(calificacion, data=request.data, partial=True)
        if serializer.is_valid():
            calificacion = serializer.save()
            send_mail(
                "Calificación actualizada",
                f"Tu nota en {calificacion.entrega.tarea.titulo} fue actualizada: {calificacion.nota}",
                settings.EMAIL_HOST_USER,
                [calificacion.entrega.estudiante.correo]
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @require_permission(['can_grade_task'], app_label='Usuarios')
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
        estudiante = request.user
        data = []

        for asignatura in Asignatura.objects.filter(estado=True):
            tareas = Tarea.objects.filter(asignatura=asignatura, estado=True)
            notas = []

            for tarea in tareas:
                entrega = Entrega.objects.filter(tarea=tarea, estudiante=estudiante).first()
                calificacion = getattr(entrega, 'calificacion', None)  

                notas.append({
                    "titulo": tarea.titulo,
                    "tipo": tarea.get_tipo_tarea_display(),
                    "peso": tarea.peso_porcentual,
                    "nota": calificacion.nota if calificacion else None,
                    "retroalimentacion": calificacion.retroalimentacion_docente if calificacion else None
                })

            promedio = calcular_promedio(estudiante, asignatura)
            data.append({
                "asignatura": asignatura.nombre,
                "codigo": asignatura.codigo,
                "notas": notas,
                "promedio": promedio
            })

        return Response(data)


def calcular_promedio(estudiante, asignatura):
    entregas = Entrega.objects.filter(
        tarea__asignatura=asignatura,
        estudiante=estudiante,
        estado_entrega='C'
    ).select_related('calificacion', 'tarea')
    total = sum(
        (e.calificacion.nota * e.tarea.peso_porcentual / 100)
        for e in entregas if e.calificacion
    )
    return round(total, 2)