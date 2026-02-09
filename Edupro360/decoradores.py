from functools import wraps

from rest_framework import status
from rest_framework.response import Response

"""
    Decorador para vistas que verifica permisos.
    
    Uso:
        @require_permission(['add_asignatura'], app_label='Academicos')
        @require_permission(['can_submit_task'], app_label='Usuarios')  # para personalizados
"""

def require_permission(permissions, app_label=None):
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if not request.user.is_authenticated:
                return Response(
                    {"error": "Autenticación requerida"},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Construir lista de permisos completos
            required_perms = [
                f"{app_label}.{perm}" if app_label else perm
                for perm in permissions
            ]

            # USAR has_perms() + all() → NUNCA FALLA
            if not request.user.has_perms(required_perms):
                return Response(
                    {
                        "error": "Permiso denegado",
                        "required": required_perms,
                        "tienes": sorted(list(request.user.get_all_permissions()))
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator