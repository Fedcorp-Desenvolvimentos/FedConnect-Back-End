# condomed/models.py
from datetime import time

from django.conf import settings
from django.db import models

# Locais onde a Condomed ministra o curso CIPA (PA-001, fechada em 2026-08-31).
AUDITORIO = "AUDITORIO"
SALA_REUNIAO = "SALA_REUNIAO"

LOCAIS_CIPA = {
    AUDITORIO: {
        "nome": "Auditório",
        "predio": "Prédio ao lado da matriz",
        "capacidade": 30,
    },
    SALA_REUNIAO: {
        "nome": "Sala de reunião",
        "predio": "Matriz",
        "capacidade": 10,
    },
}

LOCAL_CHOICES = [(codigo, dados["nome"]) for codigo, dados in LOCAIS_CIPA.items()]

# A turma ocupa o dia inteiro (RF-CIP-001).
HORA_INICIO_PADRAO = time(9, 0)
HORA_FIM_PADRAO = time(17, 30)
DURACAO_MINUTOS = 510


class TurmaCipa(models.Model):
    """Uma turma do curso CIPA: um local, um dia, 09:00–17:30."""

    STATUS_CHOICES = [
        ("agendada", "Agendada"),
        ("realizada", "Realizada"),
        ("cancelada", "Cancelada"),
    ]

    local = models.CharField(max_length=20, choices=LOCAL_CHOICES)
    data = models.DateField()
    hora_inicio = models.TimeField(default=HORA_INICIO_PADRAO)
    hora_fim = models.TimeField(default=HORA_FIM_PADRAO)

    # Cliente da turma: a administradora vem do Firebird (código + nome
    # desnormalizado); o condomínio é digitado — não há cadastro para ele.
    administradora_codigo = models.CharField(max_length=20)
    administradora_nome = models.CharField(max_length=150, blank=True)
    condominio_nome = models.CharField(max_length=150)

    observacao = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="agendada")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="turmas_cipa_criadas",
    )
    # Espelho na agenda atual quando o local é a sala de reunião (ADR-0001).
    reserva_sala = models.OneToOneField(
        "agenda.Reserva",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="turma_cipa",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["data", "hora_inicio"]
        indexes = [models.Index(fields=["local", "data"], name="condomed_local_data_idx")]
        verbose_name = "turma CIPA"
        verbose_name_plural = "turmas CIPA"

    def __str__(self):
        return f"CIPA {self.get_local_display()} em {self.data} — {self.condominio_nome}"

    @property
    def capacidade(self):
        return LOCAIS_CIPA[self.local]["capacidade"]

    @property
    def total_inscritos(self):
        return self.inscricoes.count()


class InscricaoCipa(models.Model):
    """Funcionário do condomínio inscrito em uma turma (não há cadastro; é digitado)."""

    turma = models.ForeignKey(TurmaCipa, on_delete=models.CASCADE, related_name="inscricoes")
    nome = models.CharField(max_length=150)
    cpf = models.CharField(max_length=11)
    funcao = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        unique_together = [("turma", "cpf")]
        verbose_name = "inscrição CIPA"
        verbose_name_plural = "inscrições CIPA"

    def __str__(self):
        return f"{self.nome} — turma {self.turma_id}"
