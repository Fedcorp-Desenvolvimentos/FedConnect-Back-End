from rest_framework import serializers
from .models import QuestionarioProcesso

CAMEL_TO_SNAKE = {
    "responsavelEntrevista": "responsavel_entrevista",
    "data": "data_entrevista",
    "principaisProcessos": "principais_processos",
    "atividadesFrequencia": "atividades_frequencia",
    "informacoesConsultadas": "informacoes_consultadas",
    "sistemasUtilizados": "sistemas_utilizados",
    "multiplasFontes": "multiplas_fontes",
    "atividadesManuaisRetrabalho": "atividades_manuais_retrabalho",
    "errosPerdaTempo": "erros_perda_tempo",
    "dependenciaOutroSetor": "dependencia_outro_setor",
    "relatoriosIndicadores": "relatorios_indicadores",
    "melhoriasImpacto": "melhorias_impacto",
    "consideracoesFinais": "consideracoes_finais",
}


class QuestionarioProcessoSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionarioProcesso
        fields = [
            "id",
            "setor",
            "responsavel_entrevista",
            "participantes",
            "data_entrevista",
            "principais_processos",
            "atividades_frequencia",
            "informacoes_consultadas",
            "sistemas_utilizados",
            "multiplas_fontes",
            "atividades_manuais_retrabalho",
            "erros_perda_tempo",
            "dependencia_outro_setor",
            "relatorios_indicadores",
            "melhorias_impacto",
            "consideracoes_finais",
            "criado_por",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = [
            "id",
            "criado_por",
            "criado_em",
            "atualizado_em",
        ]

    def to_internal_value(self, data):
        mutable = data.copy() if hasattr(data, "copy") else dict(data)
        for camel, snake in CAMEL_TO_SNAKE.items():
            if camel in mutable and snake not in mutable:
                mutable[snake] = mutable.pop(camel)
        return super().to_internal_value(mutable)
