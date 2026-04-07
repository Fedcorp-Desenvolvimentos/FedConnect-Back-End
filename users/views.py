from rest_framework.decorators import action
from django.contrib.auth.decorators import login_required
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import viewsets, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db.models import Q  # Importe Q para operações OR em QuerySets
from .serializers import UsuarioSerializer
from .permissions import IsAdmin, IsOwnerOrAdmin
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Q, Case, When, IntegerField
from rest_framework.views import APIView

from consultas.services.firebird_service import FirebirdService

import httpx
import secrets
import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone

User = get_user_model()

import logging
logger = logging.getLogger(__name__)

class UsuarioViewSet(viewsets.ModelViewSet):
    serializer_class = UsuarioSerializer

    def get_permissions(self):
        if self.action == "create":
            permission_classes = [AllowAny]
        elif self.action in ["list", "retrieve", "update", "partial_update", "destroy"]:
            permission_classes = [IsOwnerOrAdmin]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_authentication_classes(self):
        if self.action == "create":
            return []
        return [JWTAuthentication]

    def get_queryset(self):
        """
        Filtra o queryset baseado no nível de acesso do usuário
        e coloca o usuário logado em primeiro para admins, usando ordenação condicional.
        """
        user = self.request.user

        if user.is_authenticated:
            if hasattr(user, "nivel_acesso") and user.nivel_acesso == "admin":
                # Para admins, queremos todos os usuários, mas com o logado primeiro
                queryset = User.objects.all()

                queryset = queryset.annotate(
                    is_logged_in_user=Case(
                        When(
                            id=user.id, then=0
                        ),  # O usuário logado recebe a prioridade 0
                        default=1,  # Todos os outros recebem a prioridade 1
                        output_field=IntegerField(),
                    )
                ).order_by("is_logged_in_user", "nome_completo")
                # Primeiro ordena pela prioridade (0 vem antes de 1)
                # Depois, para usuários com a mesma prioridade (os "outros"), ordena por nome_completo

                return queryset
            else:
                # Usuários não-admin veem apenas a si mesmos
                return User.objects.filter(id=user.id)

        # Se não há usuário autenticado
        return User.objects.none()

    def perform_create(self, serializer):
        """Cria um novo usuário."""
        serializer.save()

    def perform_update(self, serializer):
        """Atualiza um usuário."""
        serializer.save()

    def perform_destroy(self, instance):
        """Deleta um usuário."""
        instance.delete()

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Endpoint para obter os dados do usuário atual."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class CustomTokenObtainPairView(TokenObtainPairView):
    # Não há necessidade de sobrescrever o método post
    # O comportamento padrão já retorna os tokens no corpo da resposta
    pass


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Com a autenticação via localStorage, não há cookies para deletar no backend.
        # O logout é gerenciado inteiramente no frontend, limpando o localStorage.
        return Response(
            {"detail": "Logout realizado com sucesso."}, status=status.HTTP_200_OK
        )


class PasswordView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        if not user.check_password(old_password):
            return Response(
                {"detail": "Senha antiga incorreta."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(new_password)
        user.save()
        return Response(
            {"detail": "Senha alterada com sucesso."}, status=status.HTTP_200_OK
        )


class SolicitarResetSenhaView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get("email")
        
        logger.info(f"Solicitação de reset de senha para email: {email}")
        
        if not email:
            return Response(
                {"detail": "E-mail é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
            logger.info(f"Usuário encontrado: {user.email}")
        except User.DoesNotExist:
            logger.warning(f"Usuário não encontrado para o email: {email}")
            return Response(
                {"detail": "Se o e-mail estiver cadastrado, você receberá as instruções."},
                status=status.HTTP_200_OK
            )
        
        # Enviar email via Gateway
        try:
            
            service = FirebirdService()
            
            email_enviado = service.enviar_email_recuperacao_senha(
                email=user.email,
                user=user
            )
            
            if email_enviado:
                logger.info(f"E-mail de recuperação enviado com sucesso para: {user.email}")
            else:
                logger.error(f"Falha ao enviar e-mail de recuperação para: {user.email}")
                    
        except Exception as e:
            logger.error(f"Erro ao chamar Gateway: {str(e)}")
        
        return Response(
            {"detail": "Se o e-mail estiver cadastrado, você receberá as instruções."},
            status=status.HTTP_200_OK
        )

class ValidarTokenResetView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, token):
        """Valida se o token de reset é válido (busca pelo token diretamente)"""
        logger.info(f"Validando token de reset: {token[:20]}...")
        
        # Buscar usuário pelo token
        try:
            user = User.objects.get(reset_password_token=token)
        except User.DoesNotExist:
            logger.warning(f"Token não encontrado: {token[:20]}...")
            return Response(
                {"valid": False, "detail": "Link inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar se o token não expirou
        if not user.reset_password_token_expires_at:
            logger.warning(f"Token sem data de expiração para usuário: {user.email}")
            return Response(
                {"valid": False, "detail": "Link inválido."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if user.reset_password_token_expires_at < timezone.now():
            logger.warning(f"Token expirado para usuário: {user.email}")
            return Response(
                {"valid": False, "detail": "Link expirado. Solicite um novo."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logger.info(f"Token válido para usuário: {user.email}")
        return Response(
            {"valid": True, "detail": "Token válido.", "user_id": user.id},
            status=status.HTTP_200_OK
        )

class ResetarSenhaView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        token = request.data.get("token")
        nova_senha = request.data.get("nova_senha")
        
        logger.info(f"Solicitação de reset de senha para token: {token[:20] if token else 'None'}...")
        
        if not token or not nova_senha:
            return Response(
                {"detail": "Dados incompletos."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(nova_senha) < 6:
            return Response(
                {"detail": "A senha deve ter no mínimo 6 caracteres."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Buscar usuário pelo token
        try:
            user = User.objects.get(reset_password_token=token)
        except User.DoesNotExist:
            logger.warning(f"Token não encontrado: {token[:20]}...")
            return Response(
                {"detail": "Link inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar expiração
        if not user.reset_password_token_expires_at:
            logger.warning(f"Token sem data de expiração para usuário: {user.email}")
            return Response(
                {"detail": "Link inválido."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if user.reset_password_token_expires_at < timezone.now():
            logger.warning(f"Token expirado para usuário: {user.email}")
            return Response(
                {"detail": "Link expirado. Solicite um novo."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Redefinir a senha
        user.set_password(nova_senha)
        user.last_password_reset = timezone.now()
        user.password_reset_count += 1
        
        # Limpar o token após uso (IMPORTANTE: não pode reusar)
        user.reset_password_token = None
        user.reset_password_token_created_at = None
        user.reset_password_token_expires_at = None
        user.save(update_fields=[
            'reset_password_token',
            'reset_password_token_created_at',
            'reset_password_token_expires_at',
            'password',
            'last_password_reset',
            'password_reset_count'
        ])
        
        logger.info(f"Senha redefinida com sucesso para usuário: {user.email}")
        
        return Response(
            {"detail": "Senha redefinida com sucesso."},
            status=status.HTTP_200_OK
        )