# agenda_comercial/serializers.py

from rest_framework import serializers
from .models import Agendamento
from users.serializers import UsuarioSerializer

class AgendamentoSerializer(serializers.ModelSerializer):
    responsavel = UsuarioSerializer(read_only=True)

    class Meta:
        model = Agendamento
        fields = ['id', 'empresa', 'data', 'responsavel', 'status', 'hora', 'obs']