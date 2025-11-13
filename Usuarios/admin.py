from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
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
