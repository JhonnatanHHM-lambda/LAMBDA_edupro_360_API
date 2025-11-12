from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from Users.models import Rol
from Users.serializers import (RolSerializer)

class RolListCreateView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        roles = Rol.objects.filter(is_active=True).order_by('nombre')
        serializer = RolSerializer(roles, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = RolSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RolDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get_object(self, pk):
        try:
            return Rol.objects.get(pk=pk, is_active=True)
        except Rol.DoesNotExist:
            return None

    def get(self, request, pk):
        rol = self.get_object(pk)
        if not rol:
            return Response({"error": "Rol no encontrado"}, status=404)
        serializer = RolSerializer(rol)
        return Response(serializer.data)

    def put(self, request, pk):
        rol = self.get_object(pk)
        if not rol:
            return Response({"error": "Rol no encontrado"}, status=404)
        serializer = RolSerializer(rol, data=request.data, partial=False)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def patch(self, request, pk):
        rol = self.get_object(pk)
        if not rol:
            return Response({"error": "Rol no encontrado"}, status=404)
        serializer = RolSerializer(rol, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        rol = self.get_object(pk)
        if not rol:
            return Response({"error": "Rol no encontrado"}, status=404)
        rol.is_active = False
        rol.save()
        return Response(status=status.HTTP_204_NO_CONTENT)