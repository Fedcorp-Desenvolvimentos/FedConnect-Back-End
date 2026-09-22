"""Espelho normalizado da CORP para os indicadores executivos (spec indicadores-executivos).

O FedConnect não tem acesso vivo à CORP: o dado chega por carga (snapshot na
v1, lake na fase 2) e fica aqui, indexado, para os endpoints agregarem com o
ORM (ADR-0009). Os nomes de campo são os da CORP (`nosnum`, `datemi`, `inivig`,
`fimvig`, `pretot`, `val_c`), sem tradução, para a tela, o glossário e o lake
falarem a mesma língua (RNF-IEX-002).

`Producao.renovacao` é a única coluna derivada: calculada na carga, uma vez,
pela regra do gestor (cadeia `nosnum_ren` ou apólice anterior do mesmo
CPF/CNPJ). O espelho é somente leitura: divergência com a origem se resolve
recarregando, nunca editando a cópia.
"""
from django.db import models


class CargaCorp(models.Model):
    """Registro de cada carga: de onde veio, de quando é, quanto entrou, o que foi rejeitado."""

    ORIGEM_SNAPSHOT = "snapshot"
    ORIGEM_LAKE = "lake"
    ORIGENS = ((ORIGEM_SNAPSHOT, "Snapshot (arquivo)"), (ORIGEM_LAKE, "Lake"))

    origem = models.CharField(max_length=10, choices=ORIGENS, default=ORIGEM_SNAPSHOT)
    arquivo = models.CharField("caminho ou identificação da fonte", max_length=255, blank=True)
    gerado_em = models.CharField("`gerado_em` do snapshot, como veio", max_length=30, blank=True)
    extraido_em = models.DateField("data da extração na CORP", null=True, blank=True)
    iniciada_em = models.DateTimeField(auto_now_add=True)
    concluida_em = models.DateTimeField(null=True, blank=True)
    # Carga que quebrou no contrato fica registrada como falha, com o motivo.
    sucesso = models.BooleanField(default=False)
    erro = models.TextField(blank=True)
    contagens = models.JSONField(default=dict, blank=True)
    rejeitos = models.JSONField(default=dict, blank=True)
    duracao_ms = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "carga da CORP"
        verbose_name_plural = "cargas da CORP"
        ordering = ("-iniciada_em",)

    def __str__(self):
        return f"carga {self.pk} ({self.origem}, extração {self.extraido_em})"


class Cliente(models.Model):
    codigo = models.IntegerField(primary_key=True)
    cpf_cnpj = models.CharField(max_length=20, blank=True)
    pessoa = models.CharField("F física / J jurídica", max_length=1, blank=True)
    nome = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "cliente CORP"
        verbose_name_plural = "clientes CORP"

    def __str__(self):
        return f"{self.codigo} · {self.nome}"


class Ramo(models.Model):
    abreviatura = models.CharField(max_length=10, primary_key=True)
    nome = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "ramo"
        verbose_name_plural = "ramos"

    def __str__(self):
        return self.abreviatura


class Seguradora(models.Model):
    sigla = models.CharField(max_length=10, primary_key=True)
    nome = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "seguradora"
        verbose_name_plural = "seguradoras"

    def __str__(self):
        return self.sigla


class Producao(models.Model):
    """Um documento de produção da CORP (`/producao`). Chave natural `nosnum` (PA-020)."""

    nosnum = models.IntegerField(primary_key=True)
    codfil = models.IntegerField("filial — ausente no snapshot (PA-020)", null=True, blank=True)
    tipdoc = models.CharField("A apólice; X, C, R, I, M, F sem legenda (PA-020)", max_length=2)
    seguradora = models.ForeignKey(
        Seguradora, null=True, blank=True, on_delete=models.SET_NULL, related_name="producoes"
    )
    ramo = models.ForeignKey(Ramo, null=True, blank=True, on_delete=models.SET_NULL, related_name="producoes")
    cliente = models.ForeignKey(Cliente, null=True, blank=True, on_delete=models.SET_NULL, related_name="producoes")
    cliente_nome = models.CharField("nome como veio na produção", max_length=200, blank=True)
    inivig = models.DateField("início de vigência", null=True, blank=True)
    fimvig = models.DateField("fim de vigência", null=True, blank=True)
    datemi = models.DateField("data de emissão — corte de todos os períodos", null=True, blank=True)
    datemi_bruta = models.CharField("texto original quando `datemi` veio inválida", max_length=20, blank=True)
    nosnum_ren = models.IntegerField("apólice que esta renova (cadeia da CORP)", null=True, blank=True)
    cancelado = models.BooleanField(default=False)
    renovacao_situacao = models.IntegerField(
        "1 vigente, 2 renovada, 3 não renovada, 5 sem legenda, 6 cancelada, -1 sem informação",
        null=True,
        blank=True,
    )
    sin_situacao = models.IntegerField("situação de sinistro", null=True, blank=True)
    # Derivado na carga (ADR-0009): `nosnum_ren > 0` ou apólice anterior do mesmo CPF/CNPJ.
    renovacao = models.BooleanField(default=False)
    carga = models.ForeignKey(CargaCorp, null=True, blank=True, on_delete=models.SET_NULL, related_name="producoes")

    class Meta:
        verbose_name = "produção"
        verbose_name_plural = "produções"
        indexes = [
            models.Index(fields=("datemi",), name="iex_producao_datemi"),
            models.Index(fields=("fimvig",), name="iex_producao_fimvig"),
            models.Index(fields=("seguradora", "datemi"), name="iex_producao_seg_datemi"),
            models.Index(fields=("cliente", "inivig"), name="iex_producao_cli_inivig"),
            models.Index(fields=("nosnum_ren",), name="iex_producao_nosnum_ren"),
        ]

    def __str__(self):
        return f"{self.tipdoc} {self.nosnum}"


class Documento(models.Model):
    """Valores do detalhe `/documento`. Só existe para os documentos enriquecidos (PA-019)."""

    FONTE_DOCUMENTO = "D"
    FONTE_RENOVACAO = "R"
    FONTES = ((FONTE_DOCUMENTO, "detalhe do documento"), (FONTE_RENOVACAO, "feed de renovações"))

    producao = models.OneToOneField(
        Producao, primary_key=True, on_delete=models.CASCADE, related_name="documento"
    )
    pretot = models.DecimalField("prêmio total", max_digits=14, decimal_places=2, null=True, blank=True)
    val_c = models.DecimalField("comissão", max_digits=14, decimal_places=2, null=True, blank=True)
    preliq = models.DecimalField("prêmio líquido", max_digits=14, decimal_places=2, null=True, blank=True)
    fonte = models.CharField(max_length=1, choices=FONTES, blank=True)

    class Meta:
        verbose_name = "documento (valores)"
        verbose_name_plural = "documentos (valores)"

    def __str__(self):
        return f"valores de {self.producao_id}"


class DocumentoNegocio(models.Model):
    """Negócio de origem (`acompanhamento.negocio`) ligado ao documento."""

    producao = models.OneToOneField(
        Producao, primary_key=True, on_delete=models.CASCADE, related_name="documentonegocio"
    )
    codigo_negocio = models.CharField(max_length=30, blank=True)
    datinc_negocio = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "negócio de origem"
        verbose_name_plural = "negócios de origem"

    def __str__(self):
        return f"negócio {self.codigo_negocio} de {self.producao_id}"
