import logging
from django.conf import settings
from django.template.loader import render_to_string
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from bigcorp.services.email_service import EmailService
from .models import QuestionarioProcesso
from .serializers import QuestionarioProcessoSerializer

logger = logging.getLogger(__name__)


class QuestionarioProcessoViewSet(viewsets.ModelViewSet):
    queryset = QuestionarioProcesso.objects.all()
    serializer_class = QuestionarioProcessoSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(criado_por=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance

        email_enviado = self._enviar_email(instance)

        if email_enviado:
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(
                {
                    **serializer.data,
                    "aviso": "Questionário salvo, mas houve uma falha ao enviar o e-mail.",
                },
                status=status.HTTP_201_CREATED,
            )

    def _enviar_email(self, instance):
        try:
            assunto = f"Novo questionário respondido - {instance.setor}"
            contexto = {
                "setor": instance.setor,
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
            template_html = render_to_string(
                "email/questionario_processo.html", contexto
            )
            email_to = getattr(
                settings, "QUESTIONARIO_EMAIL_TO", "tecnologia@fedcorp.com.br"
            )
            email_service = EmailService()
            sucesso = email_service.enviar_email(
                para=[email_to], assunto=assunto, template_html=template_html
            )
            if sucesso:
                logger.info(
                    f"E-mail do questionário {instance.id} enviado para {email_to}"
                )
            else:
                logger.warning(
                    f"Falha no envio do e-mail do questionário {instance.id}"
                )
            return sucesso
        except Exception as e:
            logger.error(
                f"Erro ao enviar e-mail do questionário {instance.id}: {str(e)}"
            )
            return False
