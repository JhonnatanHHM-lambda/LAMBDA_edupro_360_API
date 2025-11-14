from rest_framework import serializers
from .models import PeriodoAcademico, Asignatura, Tarea, Entrega, Calificacion
from Usuarios.models import Usuario
from django.utils import timezone
from django.db import models


class PeriodoAcademicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeriodoAcademico
        fields = ['id', 'nombre', 'fecha_inicio', 'fecha_fin', 'estado', 'creado', 'modificado']
        read_only_fields = ['creado', 'modificado']

    def validate(self, data):
        if data['fecha_inicio'] >= data['fecha_fin']:
            raise serializers.ValidationError("La fecha de inicio debe ser anterior a la de fin.")
        return data


class AsignaturaSerializer(serializers.ModelSerializer):
    docente_responsable = serializers.PrimaryKeyRelatedField(
        queryset=Usuario.objects.filter(groups__name='Docente'),
        allow_null=True, required=False
    )
    periodo_academico = serializers.PrimaryKeyRelatedField(
        queryset=PeriodoAcademico.objects.filter(estado=True)
    )

    class Meta:
        model = Asignatura
        fields = [
            'id', 'nombre', 'codigo', 'descripcion', 'estado',
            'docente_responsable', 'periodo_academico',
            'creado', 'modificado'
        ]
        read_only_fields = ['creado', 'modificado']

    def validate_codigo(self, value):
        qs = Asignatura.objects.filter(codigo=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Este código ya está en uso.")
        return value


class TareaSerializer(serializers.ModelSerializer):
    asignatura = serializers.PrimaryKeyRelatedField(
        queryset=Asignatura.objects.filter(estado=True)
    )

    class Meta:
        model = Tarea
        fields = [
            'id', 'asignatura', 'titulo', 'descripcion', 'fecha_publicacion',
            'fecha_vencimiento', 'peso_porcentual', 'tipo_tarea', 'estado',
            'creado', 'modificado'
        ]
        read_only_fields = ['creado', 'modificado']

    def validate(self, data):
        if data['fecha_vencimiento'] <= data['fecha_publicacion']:
            raise serializers.ValidationError("La fecha de vencimiento debe ser posterior a la publicación.")

        asignatura = data['asignatura']
        peso_actual = data['peso_porcentual']
        total = Tarea.objects.filter(asignatura=asignatura)
        if self.instance:
            total = total.exclude(pk=self.instance.pk)
        total_peso = total.aggregate(models.Sum('peso_porcentual'))['peso_porcentual__sum'] or 0
        if total_peso + peso_actual > 100:
            raise serializers.ValidationError(f"La suma de pesos no puede exceder 100%. Actual: {total_peso + peso_actual}%")
        return data


class EntregaSerializer(serializers.ModelSerializer):
    nota = serializers.SerializerMethodField()

    class Meta:
        model = Entrega
        fields = [
            'id',
            'tarea',
            'archivo_entrega',
            'comentarios_estudiante',
            'fecha_entrega',
            'estado_entrega',
            'nota',
        ]
        read_only_fields = ['fecha_entrega', 'estado_entrega', 'nota']

    def get_nota(self, obj):
        return obj.calificacion.nota if hasattr(obj, 'calificacion') else None

    def validate(self, data):
        tarea_id = self.initial_data.get('tarea')
        if not tarea_id:
            raise serializers.ValidationError("La tarea es requerida.")

        try:
            tarea = Tarea.objects.get(pk=tarea_id)
        except Tarea.DoesNotExist:
            raise serializers.ValidationError("La tarea no existe.")

        estudiante = self.context['request'].user

        if tarea.fecha_vencimiento < timezone.now():
            raise serializers.ValidationError("No se puede entregar después de la fecha de vencimiento.")

        if Entrega.objects.filter(tarea=tarea, estudiante=estudiante).exists():
            raise serializers.ValidationError("Ya has entregado esta tarea.")

        return data


class CalificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calificacion
        fields = ['id', 'entrega', 'nota', 'retroalimentacion_docente', 'fecha_calificacion', 'estado']
        read_only_fields = ['fecha_calificacion']

    def validate_nota(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError("La nota debe estar entre 0 y 100.")
        return value

    def validate_entrega(self, value):
        if value.estado_entrega != 'E':
            raise serializers.ValidationError("Solo se puede calificar entregas en estado 'Entregada'.")
        return value