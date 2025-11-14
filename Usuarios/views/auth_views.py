from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.conf import settings
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
        try:
            user = Usuario.objects.get(correo=correo, is_active=True)
            token = user.crear_token_recuperacion()
            url = f"{settings.FRONTEND_URL}/recuperar/{token}"
            send_mail(
                "Recuperar contraseña",
                f"Ingresa aquí: {url}",
                settings.EMAIL_HOST_USER,
                [correo]
            )
            return Response({"message": "Enlace enviado"})
        except Usuario.DoesNotExist:
            return Response({"error": "Correo no encontrado"}, status=404)


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