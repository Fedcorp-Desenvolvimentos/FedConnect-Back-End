from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser # Exemplo de permissões
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model # Importa seu modelo Usuario

from .models import Empresa
from .serializers import EmpresaSerializer
from users.serializers import UsuarioSerializer # Importa o Serializer do seu Usuario

User = get_user_model() # Obtém o modelo Usuario

class EmpresaViewSet(viewsets.ModelViewSet): # ModelViewSet para CRUD completo
    queryset = Empresa.objects.all().order_by('nome')
    serializer_class = EmpresaSerializer
    permission_classes = [IsAuthenticated] # Exemplo: apenas autenticados podem ver empresas

    # Opcional: Restringir quem pode criar, atualizar ou deletar empresas
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAdminUser] # Apenas admins podem modificar/deletar
        return super().get_permissions()

    # Rota para listar usuários de uma empresa específica
    # GET /api/empresas/{empresa_id}/usuarios/
    @action(detail=True, methods=['get'])
    def usuarios(self, request, pk=None):
        empresa = get_object_or_404(Empresa, pk=pk)

        # Lógica de permissão para ver usuários da empresa:
        # 1. Admins e Moderadores podem ver usuários de QUALQUER empresa.
        # 2. Usuários comuns (incluindo 'comercial') só podem ver usuários da SUA PRÓPRIA empresa.
        if request.user.nivel_acesso not in ['admin', 'moderador']:
            if not (request.user.empresa and request.user.empresa.id == empresa.id):
                return Response(
                    {"detail": "Você não tem permissão para ver usuários desta empresa."},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Filtra os usuários que pertencem a esta empresa
        usuarios = User.objects.filter(empresa=empresa).order_by('email')

        page = self.paginate_queryset(usuarios)
        if page is not None:
            serializer = UsuarioSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = UsuarioSerializer(usuarios, many=True)
        return Response(serializer.data)