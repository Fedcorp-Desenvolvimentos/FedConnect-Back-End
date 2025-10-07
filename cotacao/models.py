from django.db import models
from users.models import Usuario


class CotacaoIncendio(models.Model):
    # Dados de entrada da cotação
    responsavel = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="estudos_incendio",
        default=1
    )
    incendio_conteudo = models.FloatField(verbose_name="Incêndio Conteúdo")
    perda_aluguel = models.FloatField(verbose_name="Perda de Aluguel")
    repasse_percentual = models.FloatField(verbose_name="Repasse Percentual")
    premio_proposto = models.FloatField(verbose_name="Prêmio Proposto")

    # Resultados do cálculo da cotação
    is_total = models.FloatField(verbose_name="IS Total")
    premio_liquido = models.FloatField(verbose_name="Prêmio Líquido")
    repasse = models.FloatField(verbose_name="Repasse (Taxa)")
    comissao_administradora = models.FloatField(
        verbose_name="Comissão da Administradora"
    )
    assistencia_basica = models.FloatField(verbose_name="Assistência Básica")
    taxa_seguradora = models.FloatField(verbose_name="Taxa da Seguradora")
    premio_liquido_seguradora = models.FloatField(
        verbose_name="Prêmio Líquido da Seguradora"
    )
    premio_bruto_seguradora = models.FloatField(
        verbose_name="Prêmio Bruto da Seguradora"
    )
    repasse_seguradora_bruto = models.FloatField(
        verbose_name="Repasse Seguradora Bruto"
    )
    imposto = models.FloatField(verbose_name="Imposto")
    repasse_liquido = models.FloatField(verbose_name="Repasse Líquido")
    entradas = models.FloatField(verbose_name="Entradas")
    saidas = models.FloatField(verbose_name="Saídas")
    resultado = models.FloatField(verbose_name="Resultado Final")
    percentual = models.FloatField(verbose_name="Percentual do Resultado")

    # Metadados da cotação
    data_cotacao = models.DateTimeField(
        auto_now_add=True, verbose_name="Data da Cotação"
    )

    # Se você tiver um modelo de usuário, pode adicionar uma chave estrangeira
    # user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Usuário", null=True, blank=True)

    def __str__(self):
        return f"Cotação de Incêndio - {self.data_cotacao.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name = "Cotação de Incêndio"
        verbose_name_plural = "Cotações de Incêndio"
        ordering = ["-data_cotacao"]
