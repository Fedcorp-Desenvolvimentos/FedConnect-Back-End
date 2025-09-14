# agenda/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone


class Reserva(models.Model):
    tema = models.CharField(max_length=100)
    # A lista de participantes pode ser um campo de texto, ou uma relação ManyToMany
    # Para simplicidade, vamos usar um campo de texto por enquanto.
    participantes = models.TextField()
    data = models.DateField()
    horario = models.CharField(max_length=5)  # Ex: "10:00"
    duracao = models.IntegerField()  # Em minutos
    # Adicionamos um campo para rastrear quem fez a reserva
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservas_criadas",  # Recommended for clarity
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reserva de {self.criado_por.username} em {self.data} às {self.horario}"
