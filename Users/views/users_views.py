from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from Users.models import UsuarioPersonalizado
from Users.serializers import (UsuarioListSerializer, UsuarioCreateSerializer,
    UsuarioUpdateSerializer
)

class UsuarioListCreateView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        usuarios = UsuarioPersonalizado.objects.select_related('rol').filter(is_active=True)
        rol_codigo = request.query_params.get('rol')
        if rol_codigo:
            usuarios = usuarios.filter(rol__codigo=rol_codigo)
        usuarios = usuarios.order_by('apellido', 'nombre')
        serializer = UsuarioListSerializer(usuarios, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = UsuarioCreateSerializer(data=request.data)
        if serializer.is_valid():
            usuario = serializer.save()
            return Response(UsuarioListSerializer(usuario).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UsuarioDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get_object(self, pk):
        try:
            return UsuarioPersonalizado.objects.select_related('rol').get(pk=pk, is_active=True)
        except UsuarioPersonalizado.DoesNotExist:
            return None

    def get(self, request, pk):
        usuario = self.get_object(pk)
        if not usuario:
            return Response({"error": "Usuario no encontrado"}, status=404)
        serializer = UsuarioListSerializer(usuario)
        return Response(serializer.data)

    def put(self, request, pk):
        usuario = self.get_object(pk)
        if not usuario:
            return Response({"error": "Usuario no encontrado"}, status=404)
        serializer = UsuarioUpdateSerializer(usuario, data=request.data, partial=False)
        if serializer.is_valid():
            serializer.save()
            return Response(UsuarioListSerializer(usuario).data)
        return Response(serializer.errors, status=400)

    def patch(self, request, pk):
        usuario = self.get_object(pk)
        if not usuario:
            return Response({"error": "Usuario no encontrado"}, status=404)
        serializer = UsuarioUpdateSerializer(usuario, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(UsuarioListSerializer(usuario).data)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        usuario = self.get_object(pk)
        if not usuario:
            return Response({"error": "Usuario no encontrado"}, status=404)
        usuario.is_active = False
        usuario.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UsuarioYoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UsuarioListSerializer(request.user)
        return Response(serializer.data)
