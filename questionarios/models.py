from django.db import models
from django.conf import settings


class QuestionarioProcesso(models.Model):
    setor = models.CharField(max_length=255)
    responsavel_entrevista = models.CharField(max_length=255)
    participantes = models.TextField(blank=True, default="")
    data_entrevista = models.DateField()

    principais_processos = models.TextField(blank=True, default="")
    atividades_frequencia = models.TextField(blank=True, default="")
    informacoes_consultadas = models.TextField(blank=True, default="")

    sistemas_utilizados = models.TextField(blank=True, default="")
    multiplas_fontes = models.TextField(blank=True, default="")

    atividades_manuais_retrabalho = models.TextField(blank=True, default="")
    erros_perda_tempo = models.TextField(blank=True, default="")
    dependencia_outro_setor = models.TextField(blank=True, default="")

    relatorios_indicadores = models.TextField(blank=True, default="")
    melhorias_impacto = models.TextField(blank=True, default="")

    consideracoes_finais = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="questionarios_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Questionário de Processo"
        verbose_name_plural = "Questionários de Processos"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.setor} - {self.responsavel_entrevista} ({self.data_entrevista})"
