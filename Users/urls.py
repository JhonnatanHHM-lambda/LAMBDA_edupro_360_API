from django.urls import path
from .views.roles_views import (RolListCreateView, RolDetailView,)
from .views.users_views import (UsuarioListCreateView, UsuarioDetailView, UsuarioYoView,)
from .views.auth_views import (
    CambiarContraseñaView, LoginView,
    SolicitarRecuperacionView, ConfirmarRecuperacionView,
)

urlpatterns = [
    # Roles
    path('roles/', RolListCreateView.as_view(), name='rol-list-create'),
    path('roles/<int:pk>/', RolDetailView.as_view(), name='rol-detail'),

    # Usuarios
    path('usuarios/', UsuarioListCreateView.as_view(), name='usuario-list-create'),
    path('usuarios/<int:pk>/', UsuarioDetailView.as_view(), name='usuario-detail'),
    path('usuarios/yo/', UsuarioYoView.as_view(), name='usuario-yo'),

    # Autenticación
    path('login/', LoginView.as_view(), name='login'),
    path('cambiar-contraseña/', CambiarContraseñaView.as_view(), name='cambiar-contraseña'),

    # Recuperación
    path('recuperar-contraseña/', SolicitarRecuperacionView.as_view(), name='recuperar'),
    path('confirmar-recuperacion/', ConfirmarRecuperacionView.as_view(), name='confirmar-recuperacion'),
]