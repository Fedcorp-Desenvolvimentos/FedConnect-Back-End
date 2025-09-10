# meu_app_planilhas/serializers.py

from rest_framework import serializers

# Serializer para CNPJ (já existente, só para referência)
class ProcessamentoPlanilhaCnpjInputSerializer(serializers.Serializer):
    cnpjs = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(max_length=20, required=True)
        )
    )
    origem = serializers.CharField(max_length=50, default='manual', required=False)


# --- NOVO: Serializer para CPF ---
class ProcessamentoPlanilhaCpfInputSerializer(serializers.Serializer):
    cpfs = serializers.ListField( # Nome do campo deve ser 'cpfs'
        child=serializers.DictField(
            child=serializers.CharField(max_length=14, required=True) # CPF formatado/não formatado
        )
    )
    origem = serializers.CharField(max_length=50, default='manual', required=False)


# --- NOVO: Serializer para CEP ---
class ProcessamentoPlanilhaCepInputSerializer(serializers.Serializer):
    ceps = serializers.ListField( # Nome do campo deve ser 'ceps'
        child=serializers.DictField(
            child=serializers.CharField(max_length=10, required=True) # CEP formatado/não formatado
        )
    )
    origem = serializers.CharField(max_length=50, default='manual', required=False)