from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404
from ..serializers import GrupoSerializer
from Edupro360.decoradores import require_permission



# LISTADO + CREACIÓN DE GRUPOS

class GrupoListCreateView(APIView):

    @require_permission(['view_group'], app_label='auth')
    def get(self, request):
        grupos = Group.objects.all()
        serializer = GrupoSerializer(grupos, many=True)
        return Response(serializer.data)

    @require_permission(['add_group'], app_label='auth')
    def post(self, request):
        serializer = GrupoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# DETALLE / ACTUALIZAR / ELIMINAR GRUPO

class GrupoDetailView(APIView):

    @require_permission(['view_group'], app_label='auth')
    def get(self, request, pk):
        grupo = get_object_or_404(Group, pk=pk)
        serializer = GrupoSerializer(grupo)
        return Response(serializer.data)
    
    @require_permission(['change_group'], app_label='auth')
    def put(self, request, pk):
        grupo = get_object_or_404(Group, pk=pk)
        serializer = GrupoSerializer(grupo, data=request.data)  
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @require_permission(['change_group'], app_label='auth')
    def patch(self, request, pk):
        grupo = get_object_or_404(Group, pk=pk)
        serializer = GrupoSerializer(grupo, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @require_permission(['delete_group'], app_label='auth')
    def delete(self, request, pk):
        grupo = get_object_or_404(Group, pk=pk)
        grupo.delete()
        return Response(status=204)