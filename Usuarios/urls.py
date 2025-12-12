
from django.urls import path
from Usuarios.views.auth_views import (
    LoginView, RefreshTokenAPIView, CambiarContrasenaView,
    SolicitarRecuperacionView, ConfirmarRecuperacionView
)
from Usuarios.views.usuarios_views import UsuarioListView, UsuarioDetailView, UsuarioYoView, RegistroView, DocentesListView
from Usuarios.views.grupos_views import GrupoListCreateView, GrupoDetailView


urlpatterns = [

    # Registro
    path('registro/', RegistroView.as_view()),

    # Usuarios
    path('usuarios/', UsuarioListView.as_view(), name='usuario-list-create'),
    path('usuarios/<int:pk>/', UsuarioDetailView.as_view(), name='usuario-detail'),
    path('usuarios/yo/', UsuarioYoView.as_view(), name='usuario-yo'),

    # Docentes
    path('docentes/', DocentesListView.as_view(), name='docentes-list'),

    # Autenticación
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', RefreshTokenAPIView.as_view(), name='refresh'),
    path('cambiar-contrasena/', CambiarContrasenaView.as_view(), name='cambiar-contrasena'),

    # Recuperación
    path('recuperar-contrasena/', SolicitarRecuperacionView.as_view(), name='recuperar'),
    path('confirmar-recuperacion/', ConfirmarRecuperacionView.as_view(), name='confirmar'),

    # Grupos (roles)
    path('grupos/', GrupoListCreateView.as_view(), name='grupo-list-create'),
    path('grupos/<int:pk>/', GrupoDetailView.as_view(), name='grupo-detail'),
]