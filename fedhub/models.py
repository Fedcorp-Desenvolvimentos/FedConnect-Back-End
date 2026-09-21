"""Registro do que entrou em cada voucher/recibo de comissão (spec consulta-espelho-voucher).

O Firebird só guarda o número do voucher em `COMISSAO.VOUCHER`, um campo por
lançamento. Numa comissão recorrente com lançamento geral, o mesmo lançamento
vira dezenas de parcelas na consulta, e todas herdam o número — inclusive as
que não estavam no PDF (não pagas na emissão, ou pagas depois). O voucher
20131244 saiu com 169 linhas e a consulta mostrava 186 (PA-016).

Estes modelos são a memória da emissão: quais parcelas, de quais faturas, com
que valor, entraram naquele documento. A consulta por voucher devolve
exatamente isso (ADR-0008).
"""
from django.conf import settings
from django.db import models


class VoucherEmitido(models.Model):
    TIPO_VOUCHER = "voucher"
    TIPO_RECIBO = "recibo"
    TIPOS = ((TIPO_VOUCHER, "Voucher"), (TIPO_RECIBO, "Recibo"))

    numero = models.CharField("número do documento", max_length=20, unique=True)
    tipo_documento = models.CharField(max_length=10, choices=TIPOS, default=TIPO_VOUCHER)
    favorecido = models.CharField("código do favorecido, sem zeros à esquerda", max_length=20, blank=True)
    favorecido_nome = models.CharField(max_length=150, blank=True)
    empresa_pagadora_nome = models.CharField(max_length=150, blank=True)
    empresa_pagadora_cnpj = models.CharField(max_length=20, blank=True)
    total_bruto = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_retencoes = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_liquido = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    emitido_em = models.DateTimeField(auto_now_add=True)
    emitido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="vouchers_emitidos"
    )
    cancelado_em = models.DateTimeField(null=True, blank=True)
    reconstituido = models.BooleanField(
        "registro inferido das parcelas baixadas, não gravado na emissão",
        default=False,
    )

    class Meta:
        verbose_name = "voucher emitido"
        verbose_name_plural = "vouchers emitidos"
        ordering = ("-emitido_em",)

    def __str__(self):
        return f"{self.get_tipo_documento_display()} {self.numero}"


class VoucherEmitidoItem(models.Model):
    """Uma parcela do documento. A chave natural é a mesma que identifica a linha na consulta do FedHub."""

    voucher = models.ForeignKey(VoucherEmitido, on_delete=models.CASCADE, related_name="itens")
    fatura = models.CharField(max_length=20)
    tipo_fat = models.CharField(max_length=5, blank=True)
    favor = models.CharField("favorecido sem zeros à esquerda", max_length=20, blank=True)
    tipo = models.CharField("COMISSAO.TIPO (BENEFICIO, CONDOCORP, PEAGA)", max_length=20, blank=True)
    parcela = models.CharField("parcela do boleto, como o PDF imprime", max_length=10, blank=True)
    parcela_comissao = models.CharField("COM.parcela, chave do carimbo no Firebird", max_length=10, blank=True)
    documento = models.CharField("número do boleto", max_length=20, blank=True)
    valor = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        verbose_name = "item do voucher"
        verbose_name_plural = "itens do voucher"
        constraints = [
            models.UniqueConstraint(
                fields=("voucher", "fatura", "favor", "tipo", "parcela", "documento"),
                name="voucher_item_unico",
            )
        ]
        indexes = [models.Index(fields=("fatura", "documento"), name="voucher_item_fatura_doc")]

    def __str__(self):
        return f"{self.voucher.numero} · fatura {self.fatura} parcela {self.parcela}"
