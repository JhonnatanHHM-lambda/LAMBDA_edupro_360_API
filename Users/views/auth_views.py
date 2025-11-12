from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.conf import settings
from django.core.mail import send_mail
from Users.models import UsuarioPersonalizado, TokenRecuperacionContraseña
from Users.serializers import ( UsuarioListSerializer,
    CambiarContraseñaSerializer,
    SolicitarRecuperacionSerializer, ConfirmarRecuperacionSerializer
)

class CambiarContraseñaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CambiarContraseñaSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['nueva_contraseña'])
            user.save()

            send_mail(
                "Contraseña actualizada",
                f"Tu contraseña ha sido cambiada exitosamente.",
                settings.EMAIL_HOST_USER,
                [user.correo]
            )
            return Response({"success": "Contraseña actualizada."})
        return Response(serializer.errors, status=400)


class LoginView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        correo = request.data.get('correo')
        contraseña = request.data.get('contraseña')

        if not correo or not contraseña:
            return Response({"error": "Faltan credenciales"}, status=400)

        usuario = authenticate(correo=correo, password=contraseña)
        if usuario and usuario.is_active:
            refresh = RefreshToken.for_user(usuario)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'usuario': UsuarioListSerializer(usuario).data
            })
        return Response({"error": "Credenciales inválidas o usuario inactivo"}, status=401)


class SolicitarRecuperacionView(APIView):
    def post(self, request):
        serializer = SolicitarRecuperacionSerializer(data=request.data)
        if serializer.is_valid():
            correo = serializer.validated_data['correo']
            usuario = UsuarioPersonalizado.objects.get(correo=correo)

            token = TokenRecuperacionContraseña.objects.create(usuario=usuario)
            reset_url = f"{settings.FRONTEND_URL}/recuperar/{token.token}"

            send_mail(
                "Recuperar contraseña",
                f"Usa este enlace para restablecer tu contraseña:\n{reset_url}\n\nVálido por 1 hora.",
                settings.EMAIL_HOST_USER,
                [correo]
            )
            return Response({"success": "Enlace enviado al correo."})
        return Response(serializer.errors, status=400)


class ConfirmarRecuperacionView(APIView):
    def post(self, request):
        serializer = ConfirmarRecuperacionSerializer(data=request.data)
        if serializer.is_valid():
            try:
                token = TokenRecuperacionContraseña.objects.get(
                    token=serializer.validated_data['token']
                )
                if not token.es_valido():
                    return Response({"error": "Token expirado o usado"}, status=400)

                usuario = token.usuario
                usuario.set_password(serializer.validated_data['nueva_contraseña'])
                usuario.save()

                token.usado = True
                token.save()

                send_mail(
                    "Contraseña restablecida",
                    "Tu contraseña ha sido cambiada con éxito.",
                    settings.EMAIL_HOST_USER,
                    [usuario.correo]
                )
                return Response({"success": "Contraseña restablecida."})
            except TokenRecuperacionContraseña.DoesNotExist:
                return Response({"error": "Token inválido"}, status=400)
        return Response(serializer.errors, status=400)

