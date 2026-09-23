"""Validação dos parâmetros comuns da query string (design, "Parâmetros comuns").

Inválido → `ParametroInvalido`, que as views devolvem como 400
`{"sucesso": false, "erro": "..."}`. A janela de datas em si é resolvida em
`services/periodos.py`; aqui só se tipa e se limita.
"""
from decimal import Decimal

from rest_framework import serializers

from indicadores.models import Ramo, Seguradora
from indicadores.services.metas import REPLICAR_MAXIMO, competencia_de
from indicadores.services.periodos import JANELA_MAXIMA, JANELA_PADRAO, PERIODOS, Filtros, ParametroInvalido


class FiltrosSerializer(serializers.Serializer):
    periodo = serializers.ChoiceField(choices=PERIODOS, default="mes")
    data_referencia = serializers.DateField(required=False)
    data_ini = serializers.DateField(required=False, allow_null=True)
    data_fim = serializers.DateField(required=False, allow_null=True)
    # `?ramo=COND&ramo=FIAN`: ListField lê a lista inteira da QueryDict.
    ramo = serializers.ListField(child=serializers.CharField(max_length=10), required=False, default=list)
    seguradora = serializers.ListField(child=serializers.CharField(max_length=10), required=False, default=list)
    incluir_cancelados = serializers.BooleanField(required=False, default=False)
    todos_tipdoc = serializers.BooleanField(required=False, default=False)
    janela_dias = serializers.IntegerField(required=False, default=JANELA_PADRAO, min_value=0, max_value=JANELA_MAXIMA)

    @classmethod
    def validar(cls, query_params) -> Filtros:
        """QueryDict → `Filtros`; qualquer erro vira `ParametroInvalido` com a mensagem pronta."""
        serializer = cls(data=query_params)
        if not serializer.is_valid():
            campo, mensagens = next(iter(serializer.errors.items()))
            mensagem = mensagens[0] if isinstance(mensagens, list) else mensagens
            raise ParametroInvalido(f"{campo}: {mensagem}")
        dados = serializer.validated_data
        campos = {
            "periodo": dados["periodo"],
            "data_ini": dados.get("data_ini"),
            "data_fim": dados.get("data_fim"),
            "ramos": [r for r in dados.get("ramo", []) if r],
            "seguradoras": [s for s in dados.get("seguradora", []) if s],
            "incluir_cancelados": dados["incluir_cancelados"],
            "todos_tipdoc": dados["todos_tipdoc"],
            "janela_dias": dados["janela_dias"],
        }
        if dados.get("data_referencia"):
            campos["data_referencia"] = dados["data_referencia"]
        return Filtros(**campos)


class SerieParametrosSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=("dia", "mes"), default="mes")


class MetaMensalEntradaSerializer(serializers.Serializer):
    """Corpo de `POST indicadores/metas/` (RF-IEX-008). Seguradora e ramo têm de existir no espelho."""

    seguradora = serializers.PrimaryKeyRelatedField(
        queryset=Seguradora.objects.all(), error_messages={"does_not_exist": "seguradora desconhecida: {pk_value}."}
    )
    ramo = serializers.PrimaryKeyRelatedField(
        queryset=Ramo.objects.all(), error_messages={"does_not_exist": "ramo desconhecido: {pk_value}."}
    )
    competencia = serializers.RegexField(r"^\d{4}-(0[1-9]|1[0-2])$", error_messages={"invalid": "use o formato AAAA-MM."})
    valor_meta = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.01"),
        error_messages={"min_value": "valor_meta deve ser maior que zero."},
    )
    replicar_meses = serializers.IntegerField(required=False, default=0, min_value=0, max_value=REPLICAR_MAXIMO)

    def validate_competencia(self, valor):
        return competencia_de(valor)


class CompetenciaSerializer(serializers.Serializer):
    """`?competencia=AAAA-MM` de `GET indicadores/metas/`; padrão é o mês corrente em America/Sao_Paulo."""

    competencia = serializers.RegexField(
        r"^\d{4}-(0[1-9]|1[0-2])$", required=False, error_messages={"invalid": "use o formato AAAA-MM."}
    )

    def validate_competencia(self, valor):
        return competencia_de(valor)
