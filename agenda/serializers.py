# agenda/serializers.py
from rest_framework import serializers
from .models import Reserva


class ReservaSerializer(serializers.ModelSerializer):
    # O DRF irá automaticamente lidar com a leitura e escrita do campo
    # como uma string de texto, que é o que seu modelo espera.
    # O frontend agora envia uma string, e o serializer aceitará isso.
    # Não precisa de SerializerMethodField nem de métodos create/update customizados.

    class Meta:
        model = Reserva
        fields = [
            "id",
            "tema",
            "participantes",
            "data",
            "horario",
            "duracao",
            "criado_por",
        ]
        read_only_fields = [
            "id",
            "criado_por",
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # Transforma a string de participantes de volta em um array para o frontend
        # Isso garante que a API continue retornando os dados como uma lista
        if instance.participantes:
            representation["participantes"] = [
                p.strip() for p in instance.participantes.split(",")
            ]
        else:
            representation["participantes"] = []

        # Adiciona o nome do usuário que criou a reserva
        if instance.criado_por:
            representation["criado_por_nome"] = instance.criado_por.username

        return representation
