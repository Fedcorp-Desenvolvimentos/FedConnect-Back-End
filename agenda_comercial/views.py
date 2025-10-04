# agenda_comercial/views.py

from rest_framework import generics
from .models import Agendamento
from .serializers import AgendamentoSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
import datetime


# View para listar todos os agendamentos e criar um novo (GET e POST)
class AgendamentoListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    serializer_class = AgendamentoSerializer

    def get_queryset(self):
        queryset = Agendamento.objects.all()
        mes = self.request.query_params.get("mes", None)
        ano = self.request.query_params.get("ano", None)

        if mes and ano:
            try:
                mes = int(mes)
                ano = int(ano)
                # Filtra os agendamentos pelo ano e mês da data_visita
                queryset = queryset.filter(data__year=ano, data__month=mes)
            except (ValueError, TypeError):
                # Se os parâmetros não forem números, retorna o queryset completo
                # ou um vazio, dependendo da sua regra de negócio
                pass

        return queryset.order_by("data")

    def perform_create(self, serializer):
        serializer.save(responsavel=self.request.user)

    # Adicione estas duas linhas


# View para buscar, atualizar e deletar um agendamento específico (GET, PUT, DELETE)
class AgendamentoRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    queryset = Agendamento.objects.all()
    serializer_class = AgendamentoSerializer
