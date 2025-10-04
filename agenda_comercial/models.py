# agenda_comercial/models.py

from django.db import models
from bigcorp import settings


class Agendamento(models.Model):
    empresa = models.CharField(max_length=200)
    data = models.DateField()
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agendamentos"
    )
    status = models.CharField(max_length=20, default="Pendente")
    hora = models.TimeField(null=True, blank=True)
    obs = models.TextField(null=True, blank=True)
    motivo_cancelamento = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Agendamento com {self.empresa} em {self.data}"
