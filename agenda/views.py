# agenda/views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Reserva
from .serializers import ReservaSerializer


class ReservaViewSet(viewsets.ModelViewSet):
    queryset = Reserva.objects.all().order_by('data', 'horario')
    serializer_class = ReservaSerializer
    permission_classes = [
        IsAuthenticated
    ]  # Garante que apenas usuários logados possam interagir

    def get_queryset(self):
        """
        Sobrescreve o queryset para filtrar por um período de datas.
        """
        queryset = super().get_queryset()
        data_inicio = self.request.query_params.get('data_inicio')
        data_fim = self.request.query_params.get('data_fim')

        if data_inicio and data_fim:
            queryset = queryset.filter(data__range=[data_inicio, data_fim])
        return queryset.order_by('data', 'horario')

    def perform_create(self, serializer):
        # Atribui o usuário logado como criador da reserva
        serializer.save(criado_por=self.request.user)