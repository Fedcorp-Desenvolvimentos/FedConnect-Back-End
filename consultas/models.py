from django.db import models
from users.models import Usuario
from django.utils.translation import gettext_lazy as _


class HistoricoConsulta(models.Model):
    """Modelo para armazenar o histórico de consultas realizadas pelos usuários."""

    TIPO_CONSULTA_CHOICES = [
        ("cpf", "Consulta de CPF"),
        ("cnpj", "Consulta de CNPJ"),
        ("endereco", "Consulta de Endereço"),
        ("cpf_alternativa", "Consulta de CPF por Chaves Alternativas"),
        ("cnpj_razao_social", "Consulta de CNPJ por Razão Social"),
        ("cep_rua_cidade", "Consulta de CEP por Chaves Alternativas"),
        ("cnpj_comercial", "Consulta Comercial de CNPJ"),
        ("comercial", "Consulta contato Comercial"),
        ("vida", "Consulta de segurados Vida"),
        ("incendio", "Consulta de segurados Incendio"),
        ("faturas", "Consulta de faturas"),
        ("estudo-incendio", "Estudo de Cotação Incendio"),
    ]

    ORIGEM_CONSULTA_CHOICES = [
        ("manual", "Manual"),
        ("planilha", "Planilha"),
    ]

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="historico_consultas",
        null=True,
        blank=True,
    )
    tipo_consulta = models.CharField(max_length=30, choices=TIPO_CONSULTA_CHOICES)

    parametro_consulta = models.TextField()

    origem = models.CharField(
        max_length=10,
        choices=ORIGEM_CONSULTA_CHOICES,
        default="manual",
        verbose_name=_("origem da consulta"),
    )
    data_consulta = models.DateTimeField(auto_now_add=True)
    resultado = models.JSONField(null=True, blank=True)  # Perfeito, já está JSONField

    lote_id = models.UUIDField(
        default=None,
        null=True,
        blank=True,
        help_text="ID único para agrupar consultas de um mesmo upload de planilha.",
    )

    class Meta:
        verbose_name = _("histórico de consulta")
        verbose_name_plural = _("históricos de consultas")
        ordering = ["-data_consulta"]

    def __str__(self):
        # Usar get_tipo_consulta_display() para nomes mais amigáveis no admin
        return f"{self.usuario.email if self.usuario else 'N/A'} - {self.get_tipo_consulta_display()} ({self.get_origem_display()}) - {self.data_consulta.strftime('%d/%m/%Y %H:%M')}"
