from rest_framework.views import APIView
from rest_framework.response import Response
from Edupro360.decoradores import require_permission

class GenerarReporteMensualView(APIView):
    @require_permission(['can_receive_monthly_report'], app_label='auth')
    def post(self, request):
        from .tasks import generar_reporte_mensual
        generar_reporte_mensual.delay()
        return Response({"detail": "Reporte mensual generado y enviado."}, status=200)