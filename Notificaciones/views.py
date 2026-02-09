from rest_framework.response import Response
from rest_framework.views import APIView

from drf_yasg.utils import swagger_auto_schema

from Edupro360.decoradores import require_permission

from Notificaciones.tasks import generar_reporte_mensual

class GenerarReporteMensualView(APIView):
    @swagger_auto_schema(
        operation_summary="Generar reporte mensual MANUALMENTE",
        operation_description="""
        Dispara el reporte mensual inmediatamente (útil para pruebas, auditorías o cuando falle el automático).
        Solo usuarios con permiso 'can_receive_monthly_report'.
        """,
        responses={200: "Reporte iniciado correctamente"},
        tags=['Reportes']
    )
    @require_permission(['can_receive_monthly_report'], app_label='Usuarios')
    def post(self, request):

        task = generar_reporte_mensual.delay()  
        return Response({
            "detail": "Reporte mensual iniciado correctamente",
            "task_id": task.id  
        }, status=202)  