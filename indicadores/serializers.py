"""Validação dos parâmetros comuns da query string (design, "Parâmetros comuns").

Inválido → `ParametroInvalido`, que as views devolvem como 400
`{"sucesso": false, "erro": "..."}`. A janela de datas em si é resolvida em
`services/periodos.py`; aqui só se tipa e se limita.
"""
from rest_framework import serializers

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
