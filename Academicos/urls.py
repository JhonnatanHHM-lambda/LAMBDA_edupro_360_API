from django.urls import path
from .views import (
    PeriodoAcademicoCRUDView, AsignaturaCRUDView, TareaCRUDView,
    EntregaCRUDView, CalificacionCRUDView, MisNotasView, MisEntregasView
)

urlpatterns = [
    # Periodo Académico
    path('periodos/', PeriodoAcademicoCRUDView.as_view(), name='periodos-list'),
    path('periodos/<int:pk>/', PeriodoAcademicoCRUDView.as_view(), name='periodos-detail'),

    # Asignatura
    path('asignaturas/', AsignaturaCRUDView.as_view(), name='asignaturas-list'),
    path('asignaturas/<int:pk>/', AsignaturaCRUDView.as_view(), name='asignaturas-detail'),

    # Tarea
    path('tareas/', TareaCRUDView.as_view(), name='tareas-list'),
    path('tareas/<int:pk>/', TareaCRUDView.as_view(), name='tareas-detail'),

    # Entrega
    path('entregas/', EntregaCRUDView.as_view(), name='entregas'),
    path('entregas/<int:pk>/', EntregaCRUDView.as_view(), name='entregas-detail'),
    path('mis-entregas/', MisEntregasView.as_view(), name='mis-entregas'),

    # Calificación
    path('calificaciones/', CalificacionCRUDView.as_view(), name='calificaciones'),
    path('calificaciones/<int:pk>/', CalificacionCRUDView.as_view(), name='calificaciones-detail'),

    # Estudiante
    path('mis-notas/', MisNotasView.as_view(), name='mis-notas'),
]