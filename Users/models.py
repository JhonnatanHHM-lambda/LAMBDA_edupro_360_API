from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
import uuid
from django.utils import timezone
from datetime import timedelta
from Core.models import BaseModel


class Rol(BaseModel):
    codigo = models.CharField(max_length=20, unique=True, verbose_name="Código")
    nombre = models.CharField(max_length=50, verbose_name="Nombre del Rol")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ['nombre']

    def __str__(self):
            return self.nombre.title()

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.nombre.lower().replace(' ', '_')
        super().save(*args, **kwargs)

class GestorUsuarioPersonalizado(BaseUserManager):
    def crear_usuario(self, correo, contraseña=None, **campos_extra):
        if not correo:
            raise ValueError('El correo es requerido')
        correo = self.normalize_email(correo)
        usuario = self.model(correo=correo, **campos_extra)
        usuario.set_password(contraseña)
        usuario.save(using=self._db)
        return usuario

    def crear_superusuario(self, correo, contraseña=None, **campos_extra):
        campos_extra.setdefault('es_staff', True)
        campos_extra.setdefault('es_superusuario', True)

        # Asignar rol "super_admin" o crear si no existe
        rol, _ = Rol.objects.get_or_create(
            codigo='super_admin',
            defaults={'nombre': 'Super Administrador'}
        )
        campos_extra['rol'] = rol

        return self.crear_usuario(correo, contraseña, **campos_extra)

    def crear_admin_app(self, correo, contraseña=None, **campos_extra):
        campos_extra.setdefault('es_staff', True)
        campos_extra.setdefault('es_superusuario', False)

        # Asignar rol "admin" o crear si no existe
        rol, _ = Rol.objects.get_or_create(
            codigo='admin',
            defaults={'nombre': 'Administrador'}
        )
        campos_extra['rol'] = rol

        if campos_extra.get('es_superusuario'):
            raise ValueError('Un admin del app NO puede ser superusuario')

        return self.crear_usuario(correo, contraseña, **campos_extra)

    def crear_estudiante(self, correo, contraseña=None, **campos_extra):
        rol, _ = Rol.objects.get_or_create(codigo='estudiante', defaults={...})
        campos_extra['rol'] = rol
        return self.crear_usuario(correo, contraseña, **campos_extra)

class UsuarioPersonalizado(BaseModel, AbstractBaseUser, PermissionsMixin):
    correo = models.EmailField(unique=True, verbose_name="Correo Electrónico")
    nombre = models.CharField(max_length=30, verbose_name="Nombre")
    apellido = models.CharField(max_length=30, verbose_name="Apellido")
    rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        related_name='usuarios',
        verbose_name="Rol"
    )

    es_staff = models.BooleanField(default=False, verbose_name="Es Staff")
    es_superusuario = models.BooleanField(default=False, verbose_name="Es Superusuario")

    objects = GestorUsuarioPersonalizado()

    USERNAME_FIELD = 'correo'
    REQUIRED_FIELDS = ['nombre', 'apellido']

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        permissions = [
            ("can_receive_monthly_report", "Puede recibir reporte mensual"),
            ("can_create_subject", "Puede crear asignaturas"),
            ("can_grade_task", "Puede calificar tareas"),
            ("can_view_analytics", "Puede ver reportes analíticos"),
            ("can_view_own_grades", "Puede ver sus propias calificaciones"),
            ("can_view_own_tasks", "Puede ver sus tareas"),
            ("can_submit_task", "Puede entregar tareas"),
        ]

    def __str__(self):
            return f"{self.obtener_nombre_completo()} ({self.rol})".title()

    def obtener_nombre_completo(self):
        return f"{self.nombre} {self.apellido}"

class TokenRecuperacionContraseña(BaseModel):
    usuario = models.ForeignKey(
        UsuarioPersonalizado,
        on_delete=models.CASCADE,
        related_name='tokens_recuperacion',
        verbose_name="Usuario"
    )
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    usado = models.BooleanField(default=False, verbose_name="Usado")
    expira_el = models.DateTimeField(verbose_name="Expira el")

    class Meta:
        verbose_name = "Token de Recuperación"
        verbose_name_plural = "Tokens de Recuperación"

    def __str__(self):
        estado = "Usado" if self.usado else "Válido"
        return f"Token de {self.usuario} - {estado} (Exp: {self.expira_el.strftime('%d/%m %H:%M')})".title()

    def save(self, *args, **kwargs):
        if not self.expira_el:
            self.expira_el = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)

    def es_valido(self):
        return not self.usado and timezone.now() < self.expira_el