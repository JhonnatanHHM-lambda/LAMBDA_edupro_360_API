from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import OuterRef, Exists

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from storages.backends.s3boto3 import S3Boto3Storage

from Edupro360.decoradores import require_permission

from Academicos.models import Entrega, Tarea
from Academicos.serializers import EntregaSerializer, TareaSerializer

from Notificaciones.tasks import (
    enviar_correo_tarea_modificada,
    enviar_correo_tarea_nueva,
)

storage = S3Boto3Storage()


# ==================== TAREAS (DOCENTE) ====================
class TareaCRUDView(APIView):

    @require_permission(['add_tarea'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Crear nueva tarea",
        operation_description="El docente crea una tarea en una de sus asignaturas. Envía correo automático a todos los estudiantes inscritos.",
        request_body=TareaSerializer,
        responses={201: TareaSerializer, 400: "Errores de validación"},
        tags=['Tareas - Docente']
    )
    def post(self, request):
        serializer = TareaSerializer(data=request.data)
        if serializer.is_valid():
            tarea = serializer.save()
            enviar_correo_tarea_nueva.delay(tarea.id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @require_permission(['change_tarea'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Actualizar tarea existente",
        operation_description="Modifica título, fecha, peso, etc. Envía correo de actualización a estudiantes.",
        request_body=TareaSerializer,
        responses={200: TareaSerializer, 400: "Datos inválidos"},
        tags=['Tareas - Docente']
    )
    def put(self, request, pk):
        tarea = get_object_or_404(Tarea, pk=pk, estado=True)
        serializer = TareaSerializer(tarea, data=request.data, partial=True)
        if serializer.is_valid():
            tarea_actualizada = serializer.save()
            enviar_correo_tarea_modificada.delay(tarea_actualizada.id)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @require_permission(['view_tarea'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Listar mis tareas o ver una específica",
        operation_description="""
        • Sin pk → Lista todas las tareas creadas por el docente autenticado  
        • Con pk → Detalle de una tarea específica
        """,
        responses={200: TareaSerializer(many=True)},
        tags=['Tareas - Docente']
    )
    def get(self, request, pk=None):
        if pk:
            tarea = get_object_or_404(Tarea, pk=pk, estado=True)
            serializer = TareaSerializer(tarea)
            return Response(serializer.data)

        tareas = Tarea.objects.filter(
            asignatura__docente_responsable=request.user,
            estado=True
        ).select_related('asignatura').order_by('-fecha_publicacion')

        serializer = TareaSerializer(tareas, many=True)
        return Response(serializer.data)

# -------------------------------------------------------------
# 1. TAREAS PENDIENTES (con filtro opcional por asignatura)
# -------------------------------------------------------------
class TareasPendientesEstudianteView(APIView):
    @require_permission(['puede_inscribirse'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Tareas pendientes del estudiante",
        operation_description="""
        Devuelve todas las tareas de las asignaturas inscritas donde el estudiante 
        aún no ha entregado.
        
        Filtro opcional: ?asignatura_id=7 → solo tareas de esa asignatura
        """,
        manual_parameters=[
            openapi.Parameter(
                'asignatura_id',
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description='Filtrar por ID de asignatura (opcional)',
                required=False
            )
        ],
        responses={200: TareaSerializer(many=True)},
        tags=['Tareas - Estudiante']
    )
    def get(self, request):
        asignatura_id = request.query_params.get('asignatura_id')

        # Subquery: existe entrega del estudiante para esta tarea?
        entrega_exists = Entrega.objects.filter(
            tarea=OuterRef('pk'),
            estudiante=request.user
        )

        tareas_pendientes = Tarea.objects.filter(
            asignatura__inscripciones_asignatura__estudiante=request.user,
            asignatura__inscripciones_asignatura__estado_inscripcion='A',
            asignatura__estado=True,
            estado=True,
        ).annotate(
            ha_entregado=Exists(entrega_exists)
        ).filter(ha_entregado=False).select_related(
            'asignatura', 'asignatura__docente_responsable', 'asignatura__periodo_academico'
        ).order_by('fecha_vencimiento')

        # APLICAR FILTRO SI VIENE
        if asignatura_id:
            tareas_pendientes = tareas_pendientes.filter(asignatura_id=asignatura_id)

        serializer = TareaSerializer(tareas_pendientes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# -------------------------------------------------------------
# 2. TAREAS ENTREGADAS (sin calificar) (con filtro opcional por asignatura)
# -------------------------------------------------------------
class TareasEntregadasEstudianteView(APIView):
    @require_permission(['puede_inscribirse'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Tareas entregadas por el estudiante (sin calificar)",
        operation_description="""
        Tareas que el estudiante ya entregó pero que aún no tienen calificación.
        
        Filtro opcional: ?asignatura_id=7 → solo tareas entregadas de esa asignatura
        """,
        manual_parameters=[
            openapi.Parameter(
                'asignatura_id',
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description='Filtrar por ID de asignatura (opcional)',
                required=False
            )
        ],
        responses={200: TareaSerializer(many=True)},
        tags=['Tareas - Estudiante']
    )
    def get(self, request):
        asignatura_id = request.query_params.get('asignatura_id')

        tareas_entregadas = Tarea.objects.filter(
            asignatura__inscripciones_asignatura__estudiante=request.user,
            asignatura__inscripciones_asignatura__estado_inscripcion='A',
            asignatura__estado=True,
            estado=True,
            entregas__estudiante=request.user,
            entregas__estado_entrega__in=['E', 'P']
        ).distinct().select_related(
            'asignatura', 'asignatura__docente_responsable', 'asignatura__periodo_academico'
        ).order_by('-entregas__fecha_entrega')

        # APLICAR FILTRO SI VIENE
        if asignatura_id:
            tareas_entregadas = tareas_entregadas.filter(asignatura_id=asignatura_id)

        serializer = TareaSerializer(tareas_entregadas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
# ==================== ENTREGAS (ESTUDIANTE Y DOCENTE) ====================
class EntregaCRUDView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @require_permission(['can_submit_task'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Enviar tarea (subir archivo)",
        operation_description="El estudiante sube su entrega con archivo y comentarios",
        consumes=['multipart/form-data'],
        manual_parameters=[
            openapi.Parameter('tarea', openapi.IN_FORM, type=openapi.TYPE_INTEGER, required=True, description="ID de la tarea"),
            openapi.Parameter('archivo_entrega', openapi.IN_FORM, type=openapi.TYPE_FILE, required=True, description="Archivo PDF, Word, ZIP, etc."),
            openapi.Parameter('comentarios_estudiante', openapi.IN_FORM, type=openapi.TYPE_STRING, required=False, description="Comentario opcional")
        ],
        responses={201: EntregaSerializer, 400: "Faltan datos o archivo inválido"},
        tags=['Entregas - Estudiante']
    )
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

    @require_permission(['can_submit_task'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Actualizar entrega existente",
        operation_description="Permite cambiar comentarios o reemplazar archivo antes de la fecha límite",
        consumes=['multipart/form-data'],
        manual_parameters=[
            openapi.Parameter('comentarios_estudiante', openapi.IN_FORM, type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('archivo_entrega', openapi.IN_FORM, type=openapi.TYPE_FILE, required=False, description="Nuevo archivo (reemplaza el anterior)")
        ],
        responses={200: EntregaSerializer},
        tags=['Entregas - Estudiante']
    )
    def put(self, request, pk=None):  

        if pk is None:
            try:
                pk = int(request.data.get('id'))  
            except (TypeError, ValueError):
                return Response({"error": "ID de entrega requerido"}, status=400)

        entrega = get_object_or_404(Entrega, pk=pk, estudiante=request.user)

        # Verificar que no esté vencida
        if entrega.tarea.fecha_vencimiento < timezone.now():
            return Response({"error": "La tarea ya venció, no se puede modificar"}, status=400)

        # Actualizar comentarios si vienen
        comentarios = request.data.get('comentarios_estudiante')
        archivo = request.FILES.get('archivo_entrega')

        # Usar el serializer para validar y guardar
        serializer = EntregaSerializer(
            entrega,
            data={'comentarios_estudiante': comentarios} if comentarios is not None else {},
            partial=True,
            context={'request': request}
        )

        if serializer.is_valid():
            serializer.save()

            # Reemplazar archivo si viene uno nuevo
            if archivo:
                entrega.archivo_entrega = archivo
                entrega.save()

            return Response(serializer.data, status=200)

        return Response(serializer.errors, status=400)

    @require_permission(['delete_entrega'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Eliminar entrega",
        operation_description="Solo permitido si aún no está calificada",
        responses={204: "Entrega eliminada"},
        tags=['Entregas - Estudiante']
    )
    def delete(self, request, pk):
        entrega = get_object_or_404(Entrega, pk=pk, estudiante=request.user)
        calificacion = getattr(entrega, 'calificacion', None)
        if calificacion:
            calificacion.delete()
        entrega.delete()
        return Response(status=204)

    @require_permission(['view_entrega'], app_label='Academicos')
    @swagger_auto_schema(
        operation_summary="Ver entrega específica o listar mis entregas",
        operation_description="""
        • Con pk → detalle completo de una entrega (con nota si ya fue calificada)  
        • Sin pk → lista todas las entregas del usuario (estudiante: sus entregas | docente: entregas de sus tareas)
        """,
        responses={200: "Detalle o lista de entregas"},
        tags=['Entregas - General']
    )
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
            
            archivo_url = None
            if entrega.archivo_entrega:
                # GENERA URL FIRMADA VÁLIDA POR 1 HORA
                archivo_url = storage.url(entrega.archivo_entrega.name)

            data = {
                "id": entrega.id,
                "tarea": entrega.tarea.id,
                "archivo_entrega": archivo_url,
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

# ==================== BUSCAR MI ENTREGA POR TAREA ====================

class MiEntregaPorTareaView(APIView):
    """
    Busca la entrega del estudiante autenticado para una tarea específica.
    Devuelve 404 si no existe.
    """
    @require_permission(['can_submit_task'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Mi entrega de una tarea específica",
        operation_description="Devuelve la entrega del estudiante autenticado para la tarea indicada. Incluye archivo firmado, nota y retroalimentación si ya fue calificada.",
        responses={
            200: EntregaSerializer,
            404: "No has entregado esta tarea o no existe"
        },
        tags=['Entregas - Estudiante']
    )
    def get(self, request, tarea_id):
        try:
            entrega = Entrega.objects.get(
                tarea_id=tarea_id,
                estudiante=request.user,
                tarea__estado=True,
                tarea__asignatura__estado=True,
                estado=True
            )
        except Entrega.DoesNotExist:
            return Response(
                {"detail": "No has entregado esta tarea o no está disponible."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = EntregaSerializer(entrega)
        return Response(serializer.data, status=status.HTTP_200_OK)
class MisEntregasView(APIView):
    @require_permission(['can_submit_task'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Mis entregas enviadas",
        operation_description="Lista todas las entregas que ha hecho el estudiante autenticado",
        responses={200: EntregaSerializer(many=True)},
        tags=['Entregas - Estudiante']
    )
    def get(self, request):
        entregas = Entrega.objects.filter(estudiante=request.user, estado=True)
        serializer = EntregaSerializer(entregas, many=True)
        return Response(serializer.data)
    
# ==================== ENTREGAS DEL DOCENTE POR ESTADO ====================

class EntregasEntregadasDocenteView(APIView):
    """
    Devuelve solo las entregas a las tareas del docente con estado 'E' (Entregada, sin calificar)
    Soporta filtro opcional por asignatura: ?asignatura_id=ID
    """
    @require_permission(['can_grade_task'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Entregas enviadas a mis tareas (sin calificar)",
        operation_description="Lista todas las entregas a las tareas del docente autenticado con estado 'E'. Filtrar por asignatura con ?asignatura_id=ID",
        manual_parameters=[
            openapi.Parameter('asignatura_id', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description='ID de la asignatura (opcional)')
        ],
        responses={200: EntregaSerializer(many=True)},
        tags=['Entregas - Docente']
    )
    def get(self, request):
        asignatura_id = request.query_params.get('asignatura_id')
        
        entregas = Entrega.objects.filter(
            tarea__asignatura__docente_responsable=request.user,
            tarea__asignatura__estado=True,
            tarea__estado=True,
            estado_entrega='E',
            estado=True
        ).select_related(
            'estudiante', 'tarea', 'tarea__asignatura'
        ).order_by('-fecha_entrega')

        if asignatura_id:
            entregas = entregas.filter(tarea__asignatura_id=asignatura_id)

        serializer = EntregaSerializer(entregas, many=True)
        return Response(serializer.data)


class EntregasCalificadasDocenteView(APIView):
    """
    Devuelve solo las entregas a las tareas del docente con estado 'C' (Calificada)
    Soporta filtro opcional por asignatura: ?asignatura_id=ID
    """
    @require_permission(['can_grade_task'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Entregas calificadas en mis tareas",
        operation_description="Lista todas las entregas a las tareas del docente autenticado con estado 'C' y nota visible. Filtrar por asignatura con ?asignatura_id=ID",
        manual_parameters=[
            openapi.Parameter('asignatura_id', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description='ID de la asignatura (opcional)')
        ],
        responses={200: EntregaSerializer(many=True)},
        tags=['Entregas - Docente']
    )
    def get(self, request):
        asignatura_id = request.query_params.get('asignatura_id')
        
        entregas = Entrega.objects.filter(
            tarea__asignatura__docente_responsable=request.user,
            tarea__asignatura__estado=True,
            tarea__estado=True,
            estado_entrega='C',  
            estado=True
        ).select_related(
            'estudiante',
            'tarea',
            'tarea__asignatura',
            'calificacion' 
        ).order_by('-fecha_entrega')

        if asignatura_id:
            entregas = entregas.filter(tarea__asignatura_id=asignatura_id)

        serializer = EntregaSerializer(entregas, many=True)
        return Response(serializer.data)