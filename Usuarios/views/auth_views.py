from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags
from django.utils import timezone
from django.template.loader import render_to_string
from Usuarios.models import Usuario
from Usuarios.serializers import UsuarioListSerializer

# LOGIN

class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        correo = request.data.get('correo')
        password = request.data.get('password')

        if not correo or not password:
            return Response(
                {"detail": "Correo y contraseña son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(request, correo=correo, password=password)

        if user is None:
            return Response(
                {"detail": "Credenciales incorrectas."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {"detail": "Cuenta desactivada."},
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = RefreshToken.for_user(user)
        user_data = UsuarioListSerializer(user).data

        return Response({
            "user": user_data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })

# REFRESH


class RefreshTokenAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({"error": "refresh requerido"}, status=400)

        try:
            token = RefreshToken(refresh_token)
            return Response({
                "access": str(token.access_token),
            })
        except Exception:
            return Response({"error": "Token inválido"}, status=401)


# CAMBIAR CONTRASEÑA

class CambiarContrasenaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old = request.data.get('old_password')
        new = request.data.get('new_password')
        if not request.user.check_password(old):
            return Response({"error": "Contraseña actual incorrecta"}, status=400)
        request.user.set_password(new)
        request.user.save()
        return Response({"message": "Contraseña actualizada"})


# RECUPERACIÓN
class SolicitarRecuperacionView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        correo = request.data.get('correo')
        if not correo:
            return Response({"error": "Correo es requerido"}, status=400)

        try:
            user = Usuario.objects.get(correo__iexact=correo, is_active=True)
            token_obj = user.crear_token_recuperacion()  # ← tu método que crea TokenRecuperacionContraseña
            url_recuperacion = f"{settings.FRONTEND_URL}/recuperar/{token_obj.token}"

            context = {
                'nombre': user.obtener_nombre_completo().title(),
                'url_recuperacion': url_recuperacion,
                'expiracion_horas': 1,
                'year': timezone.now().year,
            }

            html_message = render_to_string('emails/recuperacion_contrasena.html', context)
            plain_message = strip_tags(html_message)

            send_mail(
                subject="Recupera tu contraseña - EduPro360",
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,   # ← Correcto y profesional
                recipient_list=[user.correo],
                html_message=html_message,
                fail_silently=False,
            )

            return Response({"message": "Si el correo existe, se ha enviado un enlace de recuperación"})

        except Usuario.DoesNotExist:
            # ← Seguridad: NO revelamos si el correo existe o no
            return Response({"message": "Si el correo existe, se ha enviado un enlace de recuperación"})


class ConfirmarRecuperacionView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        password = request.data.get('password')
        try:
            user = Usuario.objects.get(reset_password_token=token)
            if user.validar_token_recuperacion(token):
                user.set_password(password)
                user.limpiar_token_recuperacion()
                user.save()
                return Response({"message": "Contraseña restablecida"})
            return Response({"error": "Token expirado"}, status=400)
        except Usuario.DoesNotExist:
            return Response({"error": "Token inválido"}, status=400)