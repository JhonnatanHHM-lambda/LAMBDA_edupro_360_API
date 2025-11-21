import shortuuid
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

from Base.models import BaseModel

def generar_codigo_unico():
    """
    Genera un código único de 8 caracteres usando shortuuid.
    """
    return shortuuid.uuid()[:8].upper()

# 1. USER MANAGER

class UserManager(BaseUserManager):
    def create_user(self, correo, nombres, apellidos, password=None, **extra_fields):
        if not correo:
            raise ValueError('El correo es obligatorio')
        if not nombres or not apellidos:
            raise ValueError('Nombre y apellido son obligatorios')

        correo = self.normalize_email(correo)
        user = self.model(correo=correo, nombres=nombres, apellidos=apellidos, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, correo, nombres, apellidos, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_superuser') is not True:
                    raise ValueError('El superusuario debe tener is_superuser=True.')

        return self.create_user(correo, nombres, apellidos, password, **extra_fields)


# 2. USUARIO PERSONALIZADO

class Usuario(BaseModel, AbstractBaseUser, PermissionsMixin):
    cedula = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Cédula",
        help_text="Cédula de identidad o documento único"
    )
    correo = models.EmailField(unique=True, verbose_name="Correo Electrónico")
    nombres = models.CharField(max_length=50, verbose_name="Nombres")
    apellidos = models.CharField(max_length=50, verbose_name="Apellidos")
    genero = models.CharField(
        max_length=10,
        choices=[('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')],
        blank=True,
        null=True,
        verbose_name="Género"
    )
    codigo = models.CharField(
        max_length=8,
        unique=True,
        default=generar_codigo_unico,
        editable=False,
        verbose_name="Codigo Usuario"
    )
    fecha_nacimiento = models.DateField(blank=True, null=True, verbose_name="Fecha Nacimiento")
    telefono = models.CharField(max_length=15, blank=True, null=True, verbose_name="Teléfono")
    telefono_emergencia = models.CharField(max_length=15, blank=True, null=True, verbose_name="Teléfono de Emergencia")
    direccion = models.TextField(blank=True, null=True, verbose_name="Dirección")

    # Tokens de recuperación
    reset_password_token = models.CharField(max_length=200, blank=True, null=True)
    reset_password_token_expires_at = models.DateTimeField(blank=True, null=True)

    # Django auth
    is_staff = models.BooleanField(default=False, verbose_name="Es Staff")
    is_superuser = models.BooleanField(default=False, verbose_name="Es Superusuario")
    is_active = models.BooleanField(default=True, verbose_name="Esta activado")

    objects = UserManager()

    USERNAME_FIELD = 'correo'
    REQUIRED_FIELDS = ['nombres', 'apellidos']

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        permissions = [
            ("can_receive_monthly_report", "Puede recibir reporte mensual"),
            ("can_grade_task", "Puede calificar tareas"),
            ("can_view_analytics", "Puede ver reportes analíticos"),
            ("can_view_own_grades", "Puede ver sus propias calificaciones"),
            ("can_view_own_tasks", "Puede ver sus tareas"),
            ("can_submit_task", "Puede entregar tareas"),
        ]
        indexes = [
            models.Index(fields=['correo']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.nombres} {self.apellidos}".title()

    def obtener_nombre_completo(self):
        return f"{self.nombres} {self.apellidos}".title()

    @property
    def rol_principal(self):
        """Devuelve el nombre del primer grupo (rol)"""
        if self.groups.exists():
            return self.groups.first().name
        return "Sin rol"

    # RECUPERACIÓN DE CONTRASEÑA

    def crear_token_recuperacion(self):
        self.reset_password_token = get_random_string(50)
        self.reset_password_token_expires_at = timezone.now() + timedelta(hours=1)
        self.save(update_fields=['reset_password_token', 'reset_password_token_expires_at'])
        return self.reset_password_token

    def validar_token_recuperacion(self, token):
        if (self.reset_password_token == token and
            self.reset_password_token_expires_at and
            timezone.now() < self.reset_password_token_expires_at):
            return True
        return False

    def limpiar_token_recuperacion(self):
        self.reset_password_token = None
        self.reset_password_token_expires_at = None
        self.save(update_fields=['reset_password_token', 'reset_password_token_expires_at'])