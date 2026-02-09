from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from Edupro360.decoradores import require_permission

from ..serializers import GrupoSerializer


# ==================== LISTADO + CREACIÓN DE GRUPOS ====================
class GrupoListCreateView(APIView):

    @require_permission(['view_group'], app_label='auth')
    @swagger_auto_schema(
        operation_summary="Listar todos los grupos (roles)",
        operation_description="Devuelve todos los grupos del sistema (Estudiante, Docente, Administrador, etc.)",
        responses={200: GrupoSerializer(many=True)},
        tags=['Grupos / Roles']
    )
    def get(self, request):
        grupos = Group.objects.all()
        serializer = GrupoSerializer(grupos, many=True)
        return Response(serializer.data)

    @require_permission(['add_group'], app_label='auth')
    @swagger_auto_schema(
        operation_summary="Crear nuevo grupo (rol)",
        operation_description="Crea un nuevo rol en el sistema",
        request_body=GrupoSerializer,
        responses={
            201: GrupoSerializer,
            400: "Errores de validación"
        },
        tags=['Grupos / Roles']
    )
    def post(self, request):
        serializer = GrupoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== DETALLE / ACTUALIZAR / ELIMINAR GRUPO ====================
class GrupoDetailView(APIView):

    @require_permission(['view_group'], app_label='auth')
    @swagger_auto_schema(
        operation_summary="Obtener grupo por ID",
        operation_description="Devuelve los detalles de un grupo específico",
        responses={
            200: GrupoSerializer,
            404: "Grupo no encontrado"
        },
        tags=['Grupos / Roles']
    )
    def get(self, request, pk):
        grupo = get_object_or_404(Group, pk=pk)
        serializer = GrupoSerializer(grupo)
        return Response(serializer.data)
    
    @require_permission(['change_group'], app_label='auth')
    @swagger_auto_schema(
        operation_summary="Actualizar grupo completo",
        operation_description="Reemplaza todos los datos del grupo",
        request_body=GrupoSerializer,
        responses={
            200: GrupoSerializer,
            400: "Datos inválidos",
            404: "Grupo no encontrado"
        },
        tags=['Grupos / Roles']
    )
    def put(self, request, pk):
        grupo = get_object_or_404(Group, pk=pk)
        serializer = GrupoSerializer(grupo, data=request.data)  
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @require_permission(['change_group'], app_label='auth')
    @swagger_auto_schema(
        operation_summary="Actualizar grupo parcialmente",
        operation_description="Actualiza solo los campos enviados (ej: solo el nombre)",
        request_body=GrupoSerializer,
        responses={
            200: GrupoSerializer,
            400: "Datos inválidos",
            404: "Grupo no encontrado"
        },
        tags=['Grupos / Roles']
    )
    def patch(self, request, pk):
        grupo = get_object_or_404(Group, pk=pk)
        serializer = GrupoSerializer(grupo, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @require_permission(['delete_group'], app_label='auth')
    @swagger_auto_schema(
        operation_summary="Eliminar grupo",
        operation_description="Elimina permanentemente un grupo del sistema (cuidado: puede afectar usuarios)",
        responses={
            204: "Grupo eliminado correctamente",
            404: "Grupo no encontrado"
        },
        tags=['Grupos / Roles']
    )
    def delete(self, request, pk):
        grupo = get_object_or_404(Group, pk=pk)
        grupo.delete()
        return Response(status=204)