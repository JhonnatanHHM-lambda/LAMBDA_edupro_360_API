from django.contrib.auth import authenticate
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from Usuarios.models import Usuario
from Usuarios.serializers import UsuarioListSerializer

from Notificaciones.tasks import enviar_correo_recuperacion_contrasena


# ==================== LOGIN ====================
class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Iniciar sesión",
        operation_description="Autentica al usuario y devuelve tokens JWT + datos del perfil",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['correo', 'password'],
            properties={
                'correo': openapi.Schema(type=openapi.TYPE_STRING, format='email'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, format='password')
            }
        ),
        responses={
            200: openapi.Response('Login exitoso', examples={
                "application/json": {
                    "user": { "id": 1, "nombres": "Juan", "correo": "juan@ejemplo.com" },
                    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6...",
                    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6..."
                }
            }),
            401: "Credenciales incorrectas",
            400: "Faltan datos"
        },
        tags=['Autenticación']
    )
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


# ==================== REFRESH TOKEN ====================
class RefreshTokenAPIView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="Renovar token de acceso",
        operation_description="Recibe un refresh token válido y devuelve un nuevo access token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['refresh'],
            properties={
                'refresh': openapi.Schema(type=openapi.TYPE_STRING)
            }
        ),
        responses={
            200: openapi.Response('Token renovado', examples={
                "application/json": { "access": "eyJhbGciOiJIUzI1NiIs..." }
            }),
            401: "Token inválido o expirado"
        },
        tags=['Autenticación']
    )
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


# ==================== CAMBIAR CONTRASEÑA ====================
class CambiarContrasenaView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Cambiar contraseña (usuario autenticado)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['old_password', 'new_password'],
            properties={
                'old_password': openapi.Schema(type=openapi.TYPE_STRING, format='password'),
                'new_password': openapi.Schema(type=openapi.TYPE_STRING, format='password')
            }
        ),
        responses={
            200: "Contraseña actualizada",
            400: "Contraseña actual incorrecta"
        },
        tags=['Perfil']
    )
    def post(self, request):
        old = request.data.get('old_password')
        new = request.data.get('new_password')
        if not request.user.check_password(old):
            return Response({"error": "Contraseña actual incorrecta"}, status=400)
        request.user.set_password(new)
        request.user.save()
        return Response({"message": "Contraseña actualizada"})


# ==================== SOLICITAR RECUPERACIÓN ====================
class SolicitarRecuperacionView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="Solicitar recuperación de contraseña",
        operation_description="Envía un correo con enlace de recuperación (reseteo (seguridad: no revela si el correo existe)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['correo'],
            properties={
                'correo': openapi.Schema(type=openapi.TYPE_STRING, format='email')
            }
        ),
        responses={
            200: openapi.Response(
                description="Mensaje genérico (por seguridad)",
                examples={"application/json": {"message": "Si el correo existe, se ha enviado un enlace de recuperación"}}
            )
        },
        tags=['Recuperación de contraseña']
    )
    def post(self, request):
        correo = request.data.get('correo', '').strip().lower()
        if not correo:
            return Response({"error": "Correo es requerido"}, status=400)

        try:
            user = Usuario.objects.get(correo__iexact=correo, is_active=True)
            user.crear_token_recuperacion()
            enviar_correo_recuperacion_contrasena.delay(user.id)

            return Response({
                "message": "Si el correo existe, se ha enviado un enlace de recuperación"
            }, status=200)

        except Usuario.DoesNotExist:
            return Response({
                "message": "Si el correo existe, se ha enviado un enlace de recuperación"
            }, status=200)


# ==================== CONFIRMAR RECUPERACIÓN ====================
class ConfirmarRecuperacionView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="Confirmar restablecimiento de contraseña",
        operation_description="Cambia la contraseña usando un token válido de recuperación",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['token', 'password'],
            properties={
                'token': openapi.Schema(type=openapi.TYPE_STRING, description="Token recibido por correo"),
                'password': openapi.Schema(type=openapi.TYPE_STRING, format='password', description="Nueva contraseña")
            }
        ),
        responses={
            200: "Contraseña restablecida",
            400: "Token inválido o expirado"
        },
        tags=['Recuperación de contraseña']
    )
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