from django.urls import path
from Academicos.views.pensum_views import (
    PeriodoAcademicoCRUDView, AsignaturaCRUDView
)
from Academicos.views.tareas_views import ( TareaCRUDView,
    EntregaCRUDView, MisEntregasView
)
from Academicos.views.notas_views import (
    CalificacionCRUDView, MisNotasView, MisNotasPorAsignaturaView,
    MisNotasPorPeriodoView, MisNotasResumenView
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
    path('mis-notas/periodo/<int:periodo_id>/', MisNotasPorPeriodoView.as_view(), name='mis-notas-periodo'),
    path('mis-notas/asignatura/<int:asignatura_id>/', MisNotasPorAsignaturaView.as_view(), name='mis-notas-asignatura'),
    path('mis-notas/resumen/', MisNotasResumenView.as_view(), name='mis-notas-resumen'),
]