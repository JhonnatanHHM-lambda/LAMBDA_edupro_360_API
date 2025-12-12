from django.db import models
from django.utils import timezone

from rest_framework import serializers

from storages.backends.s3boto3 import S3Boto3Storage

from Usuarios.models import Usuario

from .models import (
    PeriodoAcademico,
    Asignatura,
    Tarea,
    Entrega,
    Calificacion,
    Inscripcion,
)

storage = S3Boto3Storage()


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
    
    # NUEVOS CAMPOS: Nombres para display
    docente_nombre = serializers.CharField(
        source='docente_responsable.obtener_nombre_completo',
        read_only=True,
        allow_null=True
    )
    periodo_nombre = serializers.CharField(
        source='periodo_academico.nombre',
        read_only=True
    )

    class Meta:
        model = Asignatura
        fields = [
            'id', 'nombre', 'codigo', 'descripcion', 'estado',
            'docente_responsable', 'periodo_academico',
            'docente_nombre', 'periodo_nombre',  # ← Agrega aquí
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

class InscripcionSerializer(serializers.ModelSerializer):
    estudiante_nombre = serializers.CharField(source='estudiante.obtener_nombre_completo', read_only=True)
    asignatura_nombre = serializers.CharField(source='asignatura.nombre', read_only=True)
    codigo_asignatura = serializers.CharField(source='asignatura.codigo', read_only=True)
    periodo = serializers.CharField(source='asignatura.periodo_academico.nombre', read_only=True)
    docente = serializers.CharField(source='asignatura.docente_responsable.obtener_nombre_completo', read_only=True)

    class Meta:
        model = Inscripcion
        fields = [
            'id', 'estudiante_nombre',
            'asignatura', 'asignatura_nombre', 'codigo_asignatura',
            'periodo', 'docente', 'fecha_inscripcion', 'estado_inscripcion'
        ]
        read_only_fields = ['fecha_inscripcion', 'estudiante_nombre', 'asignatura_nombre', 'codigo_asignatura', 'periodo', 'docente']

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
        hoy = timezone.now()

        # Validar fecha de publicación: debe ser hoy o en el futuro
        fecha_publicacion = data.get('fecha_publicacion')
        if fecha_publicacion and fecha_publicacion < hoy:
            raise serializers.ValidationError(
                "La fecha de publicación no puede ser anterior a la fecha actual."
            )

        # Validar fecha de vencimiento: debe ser después de la publicación
        fecha_vencimiento = data.get('fecha_vencimiento')
        if fecha_vencimiento and fecha_publicacion and fecha_vencimiento <= fecha_publicacion:
            raise serializers.ValidationError(
                "La fecha de vencimiento debe ser posterior a la fecha de publicación."
            )

        # Validación del peso porcentual
        asignatura = data['asignatura']
        peso_nuevo = data['peso_porcentual']

        queryset = Tarea.objects.filter(asignatura=asignatura, estado=True)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        total_peso = queryset.aggregate(total=models.Sum('peso_porcentual'))['total'] or 0

        if total_peso + peso_nuevo > 100:
            raise serializers.ValidationError(
                f"El peso total no puede exceder 100%. Actual: {total_peso + peso_nuevo}%"
            )

        return data

class EntregaSerializer(serializers.ModelSerializer):
    nota = serializers.SerializerMethodField()
    
    # AÑADIMOS ESTOS CAMPOS
    estudiante_nombre = serializers.CharField(
        source='estudiante.obtener_nombre_completo',
        read_only=True
    )
    estudiante_codigo = serializers.CharField(
        source='estudiante.codigo',
        read_only=True
    )
    
    # Información de la tarea
    tarea_titulo = serializers.CharField(source='tarea.titulo', read_only=True)
    asignatura_nombre = serializers.CharField(source='tarea.asignatura.nombre', read_only=True)
    asignatura_codigo = serializers.CharField(source='tarea.asignatura.codigo', read_only=True)
    calificacion_id = serializers.IntegerField(source='calificacion.id', read_only=True, allow_null=True)
    retroalimentacion = serializers.CharField(source='calificacion.retroalimentacion_docente', read_only=True, allow_null=True)
    class Meta:
        model = Entrega
        fields = [
            'id',
            'tarea',
            'tarea_titulo',
            'estudiante_nombre',
            'estudiante_codigo',
            'asignatura_nombre',
            'asignatura_codigo',
            'archivo_entrega',
            'comentarios_estudiante',
            'fecha_entrega',
            'estado_entrega',
            'nota',
            'calificacion_id',         
            'retroalimentacion',
        ]
        read_only_fields = ['fecha_entrega', 'estado_entrega', 'nota']

    def get_nota(self, obj):
        return obj.calificacion.nota if hasattr(obj, 'calificacion') else None
    
    def get_archivo_entrega(self, obj):
            if obj.archivo_entrega and obj.archivo_entrega.name:
                # URL FIRMADA VÁLIDA POR 1 HORA
                return storage.url(obj.archivo_entrega.name)
            return None

    def validate(self, data):
        request = self.context['request']
        
        if request.method == 'POST':
            tarea_id = self.initial_data.get('tarea')
            if not tarea_id:
                raise serializers.ValidationError({"tarea": "La tarea es requerida."})

            try:
                tarea = Tarea.objects.get(pk=tarea_id)
            except Tarea.DoesNotExist:
                raise serializers.ValidationError({"tarea": "La tarea no existe."})

            estudiante = request.user

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
        request = self.context.get('request')

        # Si es POST → validar que la entrega esté en estado 'E'
        if request and request.method == 'POST':
            if value.estado_entrega != 'E':
                raise serializers.ValidationError("Solo se puede calificar entregas en estado 'Entregada'.")
        
        # Si es PUT o PATCH → permitir actualizar siempre
        return value
