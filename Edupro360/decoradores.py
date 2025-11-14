from rest_framework.response import Response
from rest_framework import status
from functools import wraps

def require_permission(permissions, app_label):
    """
    Decorador para vistas que verifica permisos granulares.
    
    Uso:
        @require_permission(['view_usuario'], app_label='usuarios')
        def get(self, request):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            # Verificar autenticación
            if not request.user.is_authenticated:
                return Response(
                    {"error": "Autenticación requerida"},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Construir permisos completos
            required_perms = [f"{app_label}.{perm}" for perm in permissions]

            # Verificar cada permiso
            has_perm = any(request.user.has_perm(perm) for perm in required_perms)
            if not has_perm:
                return Response(
                    {"error": "No tienes permiso para esta acción"},
                    status=status.HTTP_403_FORBIDDEN
                )

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator