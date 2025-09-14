# agenda/serializers.py
from rest_framework import serializers
from .models import Reserva


class ReservaSerializer(serializers.ModelSerializer):
    participantes = serializers.SerializerMethodField()

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
        ]  # O ID e o criador são definidos automaticamente

    def get_participantes(self, obj):
        return [p.strip() for p in obj.participantes.split(",") if p.strip()]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Opcional: Adicionar o nome do usuário que criou a reserva
        if instance.criado_por:
            representation["criado_por_nome"] = instance.criado_por.username
        return representation

    def create(self, validated_data):
        participantes_str = ",".join(validated_data.pop("participantes"))
        reserva = Reserva.objects.create(
            participantes=participantes_str, **validated_data
        )
        return reserva

    def update(self, instance, validated_data):
        # Lidar com a atualização dos participantes, se necessário
        if "participantes" in validated_data:
            participantes_str = ",".join(validated_data.pop("participantes"))
            instance.participantes = participantes_str

        return super().update(instance, validated_data)
