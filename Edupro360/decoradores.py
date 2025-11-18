# Edupro360/decoradores.py
from rest_framework.response import Response
from rest_framework import status
from functools import wraps

def require_permission(permissions, app_label=None):
    """
    Decorador para vistas que verifica permisos.
    
    Uso:
        @require_permission(['add_asignatura'], app_label='Academicos')
        @require_permission(['can_submit_task'], app_label='Usuarios')  # para personalizados
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if not request.user.is_authenticated:
                return Response(
                    {"error": "Autenticación requerida"},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Construir permisos completos
            required_perms = []
            for perm in permissions:
                if app_label:
                    required_perms.append(f"{app_label}.{perm}")
                else:
                    # Si no hay app_label, asumir que es global (como can_*)
                    required_perms.append(perm)

            # Verificar si tiene AL MENOS UNO de los permisos
            if not any(request.user.has_perm(perm) for perm in required_perms):
                return Response(
                    {"error": "Permiso denegado", "required": required_perms},
                    status=status.HTTP_403_FORBIDDEN
                )

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator