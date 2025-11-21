from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from rest_framework import serializers

from .models import Usuario

# 1. LISTADO (solo lectura)

class UsuarioListSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(source='obtener_nombre_completo', read_only=True)
    rol = serializers.CharField(source='rol_principal', read_only=True)

    class Meta:
        model = Usuario
        fields = [
            'id', 'cedula', 'correo', 'nombres', 'apellidos', 'nombre_completo',
            'genero', 'codigo', 'fecha_nacimiento', 'telefono', 'rol',
            'estado', 'creado', 'modificado'
        ]
        read_only_fields = ['creado', 'modificado', 'estado', 'id', 'codigo']


# 2. CREACIÓN (registro público)

class UsuarioCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    grupos = serializers.SlugRelatedField(
        many=True,
        slug_field='name',
        queryset=Group.objects.all(),
        required=False,
        help_text="Ej: ['Estudiante']"
    )

    class Meta:
        model = Usuario
        fields = [
            'cedula', 'correo', 'nombres', 'apellidos', 'password',
            'genero', 'codigo', 'fecha_nacimiento', 'telefono',
            'telefono_emergencia', 'direccion', 'grupos'
        ]

    def validate_cedula(self, value):
        if Usuario.objects.filter(cedula=value).exists():
            raise serializers.ValidationError("Esta cédula ya está registrada.")
        return value

    def validate_correo(self, value):
        if Usuario.objects.filter(correo__iexact=value).exists():
            raise serializers.ValidationError("Este correo ya está registrado.")
        return value.lower()

    def create(self, validated_data):
        password = validated_data.pop('password')
        grupos = validated_data.pop('grupos', [])

        user = Usuario(**validated_data)
        user.set_password(password)
        user.save()

        if grupos:
            user.groups.set(grupos)

        return user


# 3. ACTUALIZACIÓN (admin)

class UsuarioUpdateSerializer(serializers.ModelSerializer):
    grupos = serializers.SlugRelatedField(
        many=True,
        slug_field='name',
        queryset=Group.objects.all(),
        required=False
    )

    class Meta:
        model = Usuario
        fields = [
            'cedula', 'correo', 'nombres', 'apellidos', 'genero', 'codigo',
            'fecha_nacimiento', 'telefono', 'telefono_emergencia', 'direccion',
            'is_staff', 'estado', 'grupos'
        ]
        read_only_fields = ['is_staff']

    def update(self, instance, validated_data):
        grupos = validated_data.pop('grupos', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if grupos is not None:
            instance.groups.set(grupos)

        return instance


# 4. GRUPO (CRUD de roles)

class GrupoSerializer(serializers.ModelSerializer):
    permisos = serializers.ListField(
        child=serializers.CharField(max_length=100),
        write_only=True,
        required=False
    )
    permisos_leidos = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'name', 'permisos', 'permisos_leidos']

    def get_permisos_leidos(self, obj):
        return [p.codename for p in obj.permissions.all()]

    def create(self, validated_data):
        permisos_codenames = validated_data.pop('permisos', [])
        grupo = Group.objects.create(**validated_data)

        if permisos_codenames:
            try:
                ct = ContentType.objects.get(id=6) 
                permisos = Permission.objects.filter(
                    content_type=ct,
                    codename__in=permisos_codenames
                )
                if len(permisos) != len(permisos_codenames):
                    faltantes = set(permisos_codenames) - {p.codename for p in permisos}
                    raise serializers.ValidationError({
                        "permisos": f"Permisos no encontrados: {list(faltantes)}"
                    })
                grupo.permissions.set(permisos)
            except Exception as e:
                grupo.delete()
                raise serializers.ValidationError({"permisos": str(e)})

        return grupo

    def update(self, instance, validated_data):
        permisos_codenames = validated_data.pop('permisos', None)
        instance.name = validated_data.get('name', instance.name)
        instance.save()

        if permisos_codenames is not None:
            try:
                ct = ContentType.objects.get(id=6)
                permisos = Permission.objects.filter(
                    content_type=ct,
                    codename__in=permisos_codenames
                )
                if len(permisos) != len(permisos_codenames):
                    faltantes = set(permisos_codenames) - {p.codename for p in permisos}
                    raise serializers.ValidationError({
                        "permisos": f"Permisos no encontrados: {list(faltantes)}"
                    })
                instance.permissions.set(permisos)
            except Exception as e:
                raise serializers.ValidationError({"permisos": str(e)})

        return instance
