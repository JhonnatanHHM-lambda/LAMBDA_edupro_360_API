from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from Edupro360.decoradores import require_permission
from Academicos.models import Tarea, Entrega
from Academicos.serializers import (TareaSerializer, EntregaSerializer
)

class TareaCRUDView(APIView):
    @require_permission(['add_tarea'], app_label='Academicos')
    def post(self, request):
        serializer = TareaSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
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
            serializer.save(
                estudiante=request.user,
                archivo_entrega=request.FILES.get('archivo_entrega')
            )
            return Response(serializer.data, status=201)

        return Response(serializer.errors, status=400)

    # PUT: Actualizar entrega
    @require_permission(['can_submit_task'], app_label='Usuarios')
    def put(self, request, pk):
        entrega = get_object_or_404(Entrega, pk=pk, estudiante=request.user)

        data = {
            "comentarios_estudiante": request.data.get("comentarios_estudiante", entrega.comentarios_estudiante)
        }

        # Si envían un archivo nuevo, se reemplaza
        archivo = request.FILES.get("archivo_entrega", None)

        serializer = EntregaSerializer(entrega, data=data, partial=True, context={'request': request})

        if serializer.is_valid():
            updated = serializer.save()

            if archivo:
                updated.archivo_entrega = archivo
                updated.save()

            return Response(serializer.data, status=200)

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

    # GET: Obtener entrega por pk o listar todas
    @require_permission(['view_entrega'], app_label='Academicos')
    def get(self, request, pk=None):
        if pk:
            if request.user.groups.filter(name='Docente').exists():
                entrega = get_object_or_404(
                    Entrega,
                    pk=pk,
                    tarea__asignatura__docente_responsable=request.user
                )
            else:
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

        # Listado general
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

