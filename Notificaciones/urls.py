from django.urls import path
from Notificaciones.views import GenerarReporteMensualView

urlpatterns = [
path('reporte-mensual/', GenerarReporteMensualView.as_view(), name='reporte-mensual'),
]
