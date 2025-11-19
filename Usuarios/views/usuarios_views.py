from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import Q
from ..models import Usuario
from ..serializers import (
    UsuarioListSerializer, UsuarioCreateSerializer, UsuarioUpdateSerializer
)
from Edupro360.decoradores import require_permission

# Registro

class RegistroView(APIView):
    permission_classes = [AllowAny]   
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

# 1. LISTADO

class UsuarioListView(APIView):

    @require_permission(['view_usuario'], app_label='Usuarios')
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


# 2. DETALLE / ACTUALIZAR / ELIMINAR

class UsuarioDetailView(APIView):

    @require_permission(['view_usuario'], app_label='Usuarios')
    def get(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk, is_active=True)
        serializer = UsuarioListSerializer(usuario)
        return Response(serializer.data)

    @require_permission(['change_usuario'], app_label='Usuarios')
    def put(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk, is_active=True)
        serializer = UsuarioUpdateSerializer(usuario, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(UsuarioListSerializer(usuario).data)
        return Response(serializer.errors, status=400)

    @require_permission(['change_usuario'], app_label='Usuarios')
    def patch(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk, is_active=True)
        serializer = UsuarioUpdateSerializer(usuario, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(UsuarioListSerializer(usuario).data)
        return Response(serializer.errors, status=400)

    @require_permission(['delete_usuario'], app_label='Usuarios')
    def delete(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk, is_active=True)
        usuario.is_active = False
        usuario.save()
        return Response(status=204)

# 3. YO (perfil propio)

class UsuarioYoView(APIView):

    def get(self, request):
        serializer = UsuarioListSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UsuarioUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(UsuarioListSerializer(request.user).data)
        return Response(serializer.errors, status=400)