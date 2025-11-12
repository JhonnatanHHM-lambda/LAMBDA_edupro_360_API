from rest_framework import serializers
from django.core.mail import send_mail
from django.conf import settings
from .models import Rol, UsuarioPersonalizado
from django.contrib.auth.password_validation import validate_password
from rest_framework.exceptions import ValidationError


class RolSerializer(serializers.ModelSerializer):
    usuarios_count = serializers.SerializerMethodField()

    class Meta:
        model = Rol
        fields = ['id', 'codigo', 'nombre', 'descripcion', 'is_active', 'created_at', 'updated_at', 'usuarios_count']
        read_only_fields = ['created_at', 'updated_at', 'usuarios_count']

    def get_usuarios_count(self, obj):
        return obj.usuarios.filter(is_active=True).count()

    def validate_nombre(self, value):
        if self.instance is None and Rol.objects.filter(nombre__iexact=value).exists():
            raise ValidationError("Ya existe un rol con este nombre.")
        return value.title()


class UsuarioListSerializer(serializers.ModelSerializer):
    rol = RolSerializer(read_only=True)
    rol_nombre = serializers.CharField(source='rol.nombre', read_only=True)
    nombre_completo = serializers.CharField(source='obtener_nombre_completo', read_only=True)

    class Meta:
        model = UsuarioPersonalizado
        fields = [
            'id', 'correo', 'nombre', 'apellido', 'nombre_completo',
            'rol', 'rol_nombre', 'is_active', 'created_at', 'updated_at'
        ]


class UsuarioCreateSerializer(serializers.ModelSerializer):
    contraseña = serializers.CharField(write_only=True, validators=[validate_password])
    rol_id = serializers.PrimaryKeyRelatedField(
        queryset=Rol.objects.filter(is_active=True), source='rol', write_only=True
    )

    class Meta:
        model = UsuarioPersonalizado
        fields = ['correo', 'nombre', 'apellido', 'contraseña', 'rol_id', 'is_active']

    def validate_correo(self, value):
        if UsuarioPersonalizado.objects.filter(correo__iexact=value).exists():
            raise ValidationError("Este correo ya está registrado.")
        return value.lower()

    def create(self, validated_data):
        contraseña = validated_data.pop('contraseña')
        rol = validated_data.pop('rol')

        usuario = UsuarioPersonalizado.objects.crear_usuario(
            correo=validated_data['correo'],
            contraseña=contraseña,
            nombre=validated_data['nombre'],
            apellido=validated_data['apellido'],
            rol=rol,
            is_active=validated_data.get('is_active', True)
        )

        # Email de bienvenida
        try:
            send_mail(
                "Bienvenido a EduPro 360",
                f"Hola {usuario.obtener_nombre_completo()},\n\nTu cuenta ha sido creada.\n"
                f"Rol: {usuario.rol}\nCorreo: {usuario.correo}",
                settings.EMAIL_HOST_USER,
                [usuario.correo]
            )
        except:
            pass  # En producción: loggear

        return usuario


class UsuarioUpdateSerializer(serializers.ModelSerializer):
    rol_id = serializers.PrimaryKeyRelatedField(
        queryset=Rol.objects.filter(is_active=True), source='rol', write_only=True, required=False
    )

    class Meta:
        model = UsuarioPersonalizado
        fields = ['nombre', 'apellido', 'rol_id', 'is_active']


class CambiarContraseñaSerializer(serializers.Serializer):
    contraseña_actual = serializers.CharField(write_only=True)
    nueva_contraseña = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_contraseña_actual(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise ValidationError("Contraseña actual incorrecta.")
        return value


class SolicitarRecuperacionSerializer(serializers.Serializer):
    correo = serializers.EmailField()

    def validate_correo(self, value):
        try:
            UsuarioPersonalizado.objects.get(correo__iexact=value, is_active=True)
        except UsuarioPersonalizado.DoesNotExist:
            raise ValidationError("No existe un usuario activo con este correo.")
        return value.lower()


class ConfirmarRecuperacionSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    nueva_contraseña = serializers.CharField(write_only=True, validators=[validate_password])