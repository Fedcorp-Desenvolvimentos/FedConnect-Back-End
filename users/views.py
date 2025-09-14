from rest_framework.decorators import action
from django.contrib.auth.decorators import login_required
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import viewsets, permissions, generics, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db.models import Q # Importe Q para operações OR em QuerySets
from .serializers import UsuarioSerializer
from .permissions import IsAdmin, IsOwnerOrAdmin
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Q, Case, When, IntegerField 
from rest_framework.views import APIView
import logging
from django.conf import settings
User = get_user_model()
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
                        When(id=user.id, then=0), # O usuário logado recebe a prioridade 0
                        default=1, # Todos os outros recebem a prioridade 1
                        output_field=IntegerField(),
                    )
                ).order_by('is_logged_in_user', 'nome_completo') 
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
        return Response({"detail": "Logout realizado com sucesso."}, status=status.HTTP_200_OK)
    
class PasswordView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        if not user.check_password(old_password):
            return Response({'detail': 'Senha antiga incorreta.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save()
        return Response({'detail': 'Senha alterada com sucesso.'}, status=status.HTTP_200_OK)