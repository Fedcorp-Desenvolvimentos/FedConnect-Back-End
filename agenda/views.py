# agenda/views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Reserva
from .serializers import ReservaSerializer


class ReservaViewSet(viewsets.ModelViewSet):
    queryset = Reserva.objects.all()
    serializer_class = ReservaSerializer
    permission_classes = [
        IsAuthenticated
    ]  # Garante que apenas usuários logados possam interagir

    def perform_create(self, serializer):
        # Atribuir o usuário logado como criador da reserva
        serializer.save(criado_por=self.request.user)
