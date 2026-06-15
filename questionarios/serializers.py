# questionarios/serializers.py
from rest_framework import serializers
from .models import QuestionarioProcesso

CAMEL_TO_SNAKE = {
    "responsavelEntrevista": "responsavel_entrevista",
    "data": "data_entrevista",
    "subarea": "subarea",
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
    # Campo opcional para receber userId do frontend (apenas para validação)
    userId = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = QuestionarioProcesso
        fields = [
            "id",
            "setor",
            "subarea",
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
            "userId",  # campo auxiliar - apenas para validação
        ]
        read_only_fields = [
            "id",
            "criado_por",
            "criado_em",
            "atualizado_em",
        ]

    def to_internal_value(self, data):
        mutable = data.copy() if hasattr(data, "copy") else dict(data)
        
        # Remove userId antes da conversão para não causar problemas
        user_id = mutable.pop('userId', None)
        
        for camel, snake in CAMEL_TO_SNAKE.items():
            if camel in mutable and snake not in mutable:
                mutable[snake] = mutable.pop(camel)
        
        # Guarda o userId no contexto da validação
        self._validation_user_id = user_id
        
        return super().to_internal_value(mutable)
    
    def to_representation(self, instance):
        """Converte snake_case para camelCase na resposta"""
        data = super().to_representation(instance)
        if 'data_entrevista' in data:
            data['data'] = data.pop('data_entrevista')
        for snake, camel in CAMEL_TO_SNAKE.items():
            if snake in data:
                data[camel] = data.pop(snake)
        return data
    
    def validate(self, attrs):
        """Validação personalizada para evitar duplicatas"""
        request = self.context.get('request')
        
        # Pega o userId do contexto ou do request
        user_id = getattr(self, '_validation_user_id', None)
        
        if not user_id and request and request.user:
            user_id = request.user.id
        
        if user_id:
            # Verifica se já existe um questionário para este usuário
            # Ignora se for edição (quando tem id)
            instance = getattr(self, 'instance', None)
            
            if not instance:  # Somente para criação
                if QuestionarioProcesso.objects.filter(criado_por_id=user_id).exists():
                    raise serializers.ValidationError(
                        "Você já enviou um questionário. Cada usuário pode enviar apenas um questionário."
                    )
        
        return attrs
    
    def create(self, validated_data):
        # Remove qualquer campo que não pertença ao modelo
        # (garantia extra)
        validated_data.pop('userId', None)
        return super().create(validated_data)