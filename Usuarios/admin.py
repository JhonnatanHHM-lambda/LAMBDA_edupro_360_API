from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    model = Usuario

    list_display = (
        'id',
        'codigo',
        'correo',
        'nombres',
        'apellidos',
        'rol_principal',  
        'is_active',
        'is_staff',
        'is_superuser',
    )

    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups')

    readonly_fields = ('creado', 'modificado', 'codigo') 

    fieldsets = (
        ('Información de acceso', {'fields': ('correo', 'password')}),
        ('Información personal', {
            'fields': (
                'nombres',
                'apellidos',
                'cedula',
                'genero',
                'fecha_nacimiento',
                'telefono',
                'telefono_emergencia',
                'direccion',
            )
        }),
        ('Información de sistema', {
            'fields': (
                'codigo',
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',  
                'user_permissions',
            )
        }),
        ('Tokens de recuperación', {
            'fields': (
                'reset_password_token',
                'reset_password_token_expires_at',
            ),
            'classes': ('collapse',),
        }),
        ('Fechas importantes', {'fields': ('last_login', 'creado', 'modificado')}),  
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'correo',
                'nombres',
                'apellidos',
                'cedula',
                'password1',
                'password2',
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
            ),
        }),
    )

    search_fields = ('correo', 'nombres', 'apellidos', 'cedula', 'codigo')
    ordering = ('correo',)


# PERMISOS - Administrar todos los permisos del sistema

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'codename', 'content_type', 'app_label']
    list_filter = ['content_type__app_label', 'content_type__model']
    search_fields = ['name', 'codename', 'content_type__app_label', 'content_type__model']
    ordering = ['content_type__app_label', 'codename']

    def app_label(self, obj):
        return obj.content_type.app_label
    app_label.short_description = 'Aplicación'
    app_label.admin_order_field = 'content_type__app_label'


# CONTENTTYPE - Ver de qué modelos vienen los permisos

@admin.register(ContentType)
class ContentTypeAdmin(admin.ModelAdmin):
    list_display = ['app_label', 'model', 'id']
    list_filter = ['app_label']
    search_fields = ['app_label', 'model']
    ordering = ['app_label', 'model']