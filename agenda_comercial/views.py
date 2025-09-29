# agenda_comercial/views.py

from rest_framework import generics
from .models import Agendamento
from .serializers import AgendamentoSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

## Or JWTAuthentication

# View para listar todos os agendamentos e criar um novo (GET e POST)
class AgendamentoListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    queryset = Agendamento.objects.all()
    serializer_class = AgendamentoSerializer
    def perform_create(self, serializer):
        serializer.save(responsavel=self.request.user)
    
    # Adicione estas duas linhas

# View para buscar, atualizar e deletar um agendamento específico (GET, PUT, DELETE)
class AgendamentoRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    queryset = Agendamento.objects.all()
    serializer_class = AgendamentoSerializer
 
 