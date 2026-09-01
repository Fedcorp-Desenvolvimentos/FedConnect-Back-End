# questionarios/views.py
import logging
from django.conf import settings
from django.template.loader import render_to_string
from django.db.models import Q
import httpx
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from consultas.utils.get_headers import get_headers
from .models import QuestionarioProcesso
from .serializers import QuestionarioProcessoSerializer

logger = logging.getLogger(__name__)


class QuestionarioProcessoViewSet(viewsets.ModelViewSet):
    serializer_class = QuestionarioProcessoSerializer
    permission_classes = [IsAuthenticated]
    # Adicione um queryset base para o router
    queryset = QuestionarioProcesso.objects.none()  # Queryset vazio como base

    def get_queryset(self):
        user = self.request.user
        
        # Admin e TI veem todos os questionários
        if user.nivel_acesso and user.nivel_acesso.lower() in ['admin', 'ti']:
            return QuestionarioProcesso.objects.all()
        
        # Usuários normais veem apenas os seus próprios questionários
        return QuestionarioProcesso.objects.filter(criado_por=user)

    def perform_create(self, serializer):
        serializer.save(criado_por=self.request.user)

    def create(self, request, *args, **kwargs):
        # Validação: verificar se o usuário já enviou um questionário
        user = request.user
        
        # Verifica se o usuário já tem um questionário (exceto admin/TI)
        if not (user.nivel_acesso and user.nivel_acesso.lower() in ['admin', 'ti']):
            questionario_existente = QuestionarioProcesso.objects.filter(
                criado_por=user
            ).exists()
            
            if questionario_existente:
                logger.warning(f"Usuário {user.id} tentou enviar um segundo questionário")
                return Response(
                    {
                        "status": "error",
                        "message": "Você já enviou um questionário. Cada usuário pode enviar apenas um questionário.",
                        "code": "duplicate_submission"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        
        logger.debug(f"Questionário de processo - dados: {request.data}")
        logger.info(f"Questionário de processo criado com ID {instance.id} por {request.user.username}")
        logger.debug(f"Dados do questionário: {serializer.data}")

        # Tenta enviar o email, mas não bloqueia a resposta se falhar
        try:
            email_enviado = self._enviar_email(instance)
            if not email_enviado:
                logger.warning(f"Falha no envio do e-mail para o questionário {instance.id}")
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar e-mail do questionário {instance.id}: {str(e)}")

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Verifica se o usuário é o dono do questionário
        if instance.criado_por_id != request.user.id:
            return Response(
                {
                    "status": "error",
                    "message": "Você só pode editar seus próprios questionários."
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Verifica se o usuário é o dono do questionário ou admin/ti
        if instance.criado_por_id != request.user.id:
            if not (request.user.nivel_acesso and request.user.nivel_acesso.lower() in ['admin', 'ti']):
                return Response(
                    {
                        "status": "error",
                        "message": "Você só pode excluir seus próprios questionários."
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
        
        return super().destroy(request, *args, **kwargs)
    
    def _enviar_email(self, instance):
        """Envia e-mail usando o serviço de email do projeto"""
        try:
            assunto = f"Novo questionário respondido - {instance.setor}"
            
            # Prepara o contexto para o template
            contexto = {
                "setor": instance.setor,
                "subarea": instance.subarea if hasattr(instance, 'subarea') else "",
                "responsavel_entrevista": instance.responsavel_entrevista,
                "participantes": instance.participantes,
                "data_entrevista": instance.data_entrevista,
                "principais_processos": instance.principais_processos,
                "atividades_frequencia": instance.atividades_frequencia,
                "informacoes_consultadas": instance.informacoes_consultadas,
                "sistemas_utilizados": instance.sistemas_utilizados,
                "multiplas_fontes": instance.multiplas_fontes,
                "atividades_manuais_retrabalho": instance.atividades_manuais_retrabalho,
                "erros_perda_tempo": instance.erros_perda_tempo,
                "dependencia_outro_setor": instance.dependencia_outro_setor,
                "relatorios_indicadores": instance.relatorios_indicadores,
                "melhorias_impacto": instance.melhorias_impacto,
                "consideracoes_finais": instance.consideracoes_finais,
            }
            
            # Renderiza o template HTML
            template_html = render_to_string("email/questionario_processo.html", contexto)
            
            # Email destinatário - pode vir do settings
            email_to = getattr(settings, "QUESTIONARIO_EMAIL_TO", "novosnegocios@grupofedcorp.com.br")
            
            base_url = getattr(settings, "FEDHUB_URL", "http://localhost:8090").rstrip("/")

            with httpx.Client() as client:
                response = client.post(
                    f"{base_url}/api/email/send/gmail",
                    headers=get_headers(),
                    json={
                        "to_email": email_to,
                        "subject": assunto,
                        "body": template_html,
                        "is_html": True
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    logger.info(f"Email enviado com sucesso via Gateway para: {email_to}")
                    return True
                else:
                    logger.error(f"Gateway retornou erro {response.status_code}: {response.text}")
                    return False
                
        except Exception as e:
            logger.error(f"Erro ao enviar e-mail do questionário {instance.id}: {str(e)}")
            return False