from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from Edupro360.decoradores import require_permission

from ..models import Usuario
from ..serializers import (
    UsuarioListSerializer,
    UsuarioCreateSerializer,
    UsuarioUpdateSerializer,
)


# ==================== REGISTRO ====================
class RegistroView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="Registrar nuevo usuario",
        operation_description="Crea un usuario y devuelve tokens JWT + datos del usuario",
        request_body=UsuarioCreateSerializer,
        responses={
            201: openapi.Response(
                description="Usuario creado exitosamente",
                examples={
                    "application/json": {
                        "message": "Usuario creado exitosamente",
                        "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6...",
                        "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6...",
                        "usuario": { "id": 1, "nombres": "Juan", "correo": "juan@ejemplo.com" }
                    }
                }
            ),
            400: "Errores de validación"
        },
        tags=['Autenticación']
    )
    def post(self, request):
        serializer = UsuarioCreateSerializer(data=request.data)
        if serializer.is_valid():
            usuario = serializer.save()
            refresh = RefreshToken.for_user(usuario)
            return Response({
                'message': 'Usuario creado exitosamente',
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'usuario': UsuarioListSerializer(usuario).data
            }, status=201)
        return Response(serializer.errors, status=400)


# ==================== LISTADO DE USUARIOS ====================
class UsuarioListView(APIView):

    @require_permission(['view_usuario'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Listar usuarios activos",
        operation_description="Busca por nombres, apellidos, correo o cédula con parámetro ?search=",
        manual_parameters=[
            openapi.Parameter(
                name='search',
                in_=openapi.IN_QUERY,
                required=False,
                type=openapi.TYPE_STRING,
                description='Búsqueda en nombres, apellidos, correo o cédula'
            )
        ],
        responses={200: UsuarioListSerializer(many=True)},
        tags=['Usuarios']
    )
    def get(self, request):
        queryset = Usuario.objects.filter(is_active=True)
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(nombres__icontains=search) |
                Q(apellidos__icontains=search) |
                Q(correo__icontains=search) |
                Q(cedula__icontains=search)
            )
        serializer = UsuarioListSerializer(queryset, many=True)
        return Response(serializer.data)


# ==================== DETALLE / ACTUALIZAR / ELIMINAR ====================
class UsuarioDetailView(APIView):

    @require_permission(['view_usuario'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Obtener usuario por ID",
        responses={200: UsuarioListSerializer, 404: "No encontrado"},
        tags=['Usuarios']
    )
    def get(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk, is_active=True)
        serializer = UsuarioListSerializer(usuario)
        return Response(serializer.data)

    @require_permission(['change_usuario'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Actualizar todos los campos del usuario",
        request_body=UsuarioUpdateSerializer,
        responses={200: UsuarioListSerializer},
        tags=['Usuarios']
    )
    def put(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk, is_active=True)
        serializer = UsuarioUpdateSerializer(usuario, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(UsuarioListSerializer(usuario).data)
        return Response(serializer.errors, status=400)

    @require_permission(['change_usuario'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Actualizar campos parciales del usuario",
        request_body=UsuarioUpdateSerializer,
        responses={200: UsuarioListSerializer},
        tags=['Usuarios']
    )
    def patch(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk, is_active=True)
        serializer = UsuarioUpdateSerializer(usuario, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(UsuarioListSerializer(usuario).data)
        return Response(serializer.errors, status=400)

    @require_permission(['delete_usuario'], app_label='Usuarios')
    @swagger_auto_schema(
        operation_summary="Eliminar usuario (soft delete)",
        operation_description="Marca is_active=False",
        responses={204: "Eliminado correctamente"},
        tags=['Usuarios']
    )
    def delete(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk, is_active=True)
        usuario.is_active = False
        usuario.save()
        return Response(status=204)


# ==================== PERFIL PROPIO (YO) ====================
class UsuarioYoView(APIView):

    @swagger_auto_schema(
        operation_summary="Obtener mi perfil",
        operation_description="Devuelve los datos del usuario autenticado",
        responses={200: UsuarioListSerializer},
        tags=['Perfil']
    )
    def get(self, request):
        serializer = UsuarioListSerializer(request.user)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_summary="Actualizar mi perfil",
        operation_description="Actualización parcial de mis datos personales",
        request_body=UsuarioUpdateSerializer,
        responses={200: UsuarioListSerializer},
        tags=['Perfil']
    )
    def patch(self, request):
        serializer = UsuarioUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(UsuarioListSerializer(request.user).data)
        return Response(serializer.errors, status=400)