# condomed/models.py
from datetime import time

from django.conf import settings
from django.db import models

# Unidade da Condomed que emite os documentos da turma. Vem do local, não é
# digitada: os dois modelos de certificado em uso traziam São Paulo na frente
# e Rio no verso — defeito do modelo, confirmado pelo dono em 2026-09-04.
UNIDADE_RIO = {
    "nome": "CondoMed Rio",
    "endereco": "Rua da Alfândega, 108, 7º andar, Centro/RJ",
    "telefone": "(21) 2516-6001",
    "email": "condocorp@grupofedcorp.com.br",
    "cidade": "Rio de Janeiro",
}

# Locais onde a Condomed ministra o curso CIPA (PA-001, fechada em 2026-08-31).
AUDITORIO = "AUDITORIO"
SALA_REUNIAO = "SALA_REUNIAO"

LOCAIS_CIPA = {
    AUDITORIO: {
        "nome": "Auditório",
        "predio": "Prédio ao lado da matriz",
        "capacidade": 30,
        "unidade": UNIDADE_RIO,
    },
    SALA_REUNIAO: {
        "nome": "Sala de reunião",
        "predio": "Matriz",
        "capacidade": 10,
        "unidade": UNIDADE_RIO,
    },
}

LOCAL_CHOICES = [(codigo, dados["nome"]) for codigo, dados in LOCAIS_CIPA.items()]

# Instrutores que assinam o certificado. Fixos no código por decisão do dono
# (2026-09-04): sem cadastro editável, não há como cadastrar errado. Um
# instrutor novo é uma entrada aqui e uma imagem em `condomed/assets/`.
INSTRUTORES_CIPA = {
    "FELIPE": {
        "nome": "Felipe Barboza de Oliveira",
        "titulo": "Técnico em Segurança no Trabalho",
        "registro_mte": "0060169",
        "registro_uf": "RJ",
        "assinatura": "assinatura-felipe.png",
    },
    "VINICIUS": {
        "nome": "Vinicius dos Santos Pinto",
        "titulo": "Técnico em Segurança no Trabalho",
        "registro_mte": "0056876",
        "registro_uf": "RJ",
        "assinatura": "assinatura-vinicius.jpeg",
    },
}

INSTRUTOR_CHOICES = [(codigo, dados["nome"]) for codigo, dados in INSTRUTORES_CIPA.items()]

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

    # A turma não tem cliente: administradora e condomínio são de cada
    # inscrito, porque um mesmo dia recebe funcionários de várias
    # administradoras e vários condomínios (ADR-0004).
    # Quem ministra e assina o certificado. Opcional na criação — a turma pode
    # ser marcada antes de se saber quem vai dar o curso — e obrigatório para
    # emitir certificado (fase D).
    instrutor = models.CharField(max_length=20, choices=INSTRUTOR_CHOICES, blank=True)

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
        return f"CIPA {self.get_local_display()} em {self.data}"

    @property
    def capacidade(self):
        return LOCAIS_CIPA[self.local]["capacidade"]

    @property
    def total_inscritos(self):
        return self.inscricoes.count()


class InscricaoCipa(models.Model):
    """Participante de uma turma, com o próprio vínculo (não há cadastro; é digitado)."""

    turma = models.ForeignKey(TurmaCipa, on_delete=models.CASCADE, related_name="inscricoes")
    nome = models.CharField(max_length=150)
    cpf = models.CharField(max_length=11)
    funcao = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)

    # De quem é este participante (ADR-0004): a administradora vem do Firebird
    # (código + nome desnormalizado) e o condomínio é digitado — não há
    # cadastro de condomínios.
    administradora_codigo = models.CharField(max_length=20)
    administradora_nome = models.CharField(max_length=150, blank=True)
    condominio_nome = models.CharField(max_length=150)
    # O certificado cita o condomínio com CNPJ. Opcional para inscrever (o
    # extra de última hora entra sem ele) e obrigatório para emitir o
    # certificado — decisão do dono em 2026-09-04. 14 dígitos, sem máscara.
    condominio_cnpj = models.CharField(max_length=14, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["condominio_nome", "nome"]
        unique_together = [("turma", "cpf")]
        indexes = [
            models.Index(
                fields=["administradora_codigo"], name="condomed_insc_adm_idx"
            )
        ]
        verbose_name = "inscrição CIPA"
        verbose_name_plural = "inscrições CIPA"

    def __str__(self):
        return f"{self.nome} ({self.condominio_nome}) — turma {self.turma_id}"
