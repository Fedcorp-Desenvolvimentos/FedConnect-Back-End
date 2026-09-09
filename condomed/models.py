# condomed/models.py
import uuid
from datetime import time
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils.text import slugify

ASSETS = Path(__file__).resolve().parent / "assets"

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

# Unidades emissoras conhecidas. Uma unidade nova é deploy (fora do escopo de
# `curso-cipa-cadastros`); o local escolhe uma delas.
UNIDADES = {"RIO": UNIDADE_RIO}
UNIDADE_CHOICES = [(codigo, dados["nome"]) for codigo, dados in UNIDADES.items()]

# Códigos dos dois locais originais (PA-001). Desde `curso-cipa-cadastros`
# (2026-09-08, PA-010) os locais são registros editáveis (`LocalCipa`); estes
# dicionários são a SEMENTE da migração 0005 e continuam sendo o que os testes
# citam. Não são mais lidos em tempo de execução.
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

# Instrutores originais (PA-008, Q3). Também só semente da migração 0005: desde
# PA-010 o cadastro é editável (`InstrutorCipa`), com a assinatura no storage.
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


def gerar_codigo(nome, existentes):
    """Código estável a partir do nome (ex.: "Sala 2" → SALA_2), único entre `existentes`.

    O código é a chave que o frontend e a API usam (`local`/`instrutor` na
    turma), então não muda depois de criado — renomear o local não renomeia o
    código, e é isso que mantém as turmas antigas apontando certo.
    """
    base = slugify(nome).replace("-", "_").upper()[:30] or "ITEM"
    codigo, n = base, 2
    while codigo in existentes:
        codigo, n = f"{base}_{n}", n + 1
    return codigo


class LocalCipa(models.Model):
    """Local onde a Condomed ministra o curso (RF-CIP-007). Editável desde PA-010."""

    codigo = models.CharField(max_length=40, unique=True)
    nome = models.CharField(max_length=80)
    predio = models.CharField(max_length=120, blank=True)
    capacidade = models.PositiveIntegerField()
    unidade = models.CharField(max_length=10, choices=UNIDADE_CHOICES, default="RIO")
    # No máximo um local ativo com esta marca: é a sala que a agenda atual
    # conhece (ADR-0001). Turma nele é espelhada em `agenda.Reserva`.
    compartilha_sala_reuniao = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "local CIPA"
        verbose_name_plural = "locais CIPA"

    def __str__(self):
        return self.nome

    @property
    def unidade_dados(self):
        return UNIDADES.get(self.unidade, UNIDADE_RIO)


class InstrutorCipa(models.Model):
    """Palestrante que ministra e assina o certificado (RF-CIP-006). Editável desde PA-010."""

    TITULO_PADRAO = "Técnico em Segurança no Trabalho"

    codigo = models.CharField(max_length=40, unique=True)
    nome = models.CharField(max_length=150)
    titulo = models.CharField(max_length=100, default=TITULO_PADRAO)
    registro_mte = models.CharField(max_length=20)
    registro_uf = models.CharField(max_length=2)
    # Só no storage (S3 em produção — RNF-CIP-005); a API nunca expõe a URL.
    assinatura = models.ImageField(upload_to="condomed/assinaturas/", blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        unique_together = [("registro_mte", "registro_uf")]
        verbose_name = "instrutor CIPA"
        verbose_name_plural = "instrutores CIPA"

    def __str__(self):
        return self.nome

    @property
    def registro(self):
        return f"MTE/{self.registro_uf} {self.registro_mte}"

    @property
    def tem_assinatura(self):
        return bool(self.assinatura)

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

    local = models.ForeignKey(LocalCipa, on_delete=models.PROTECT, related_name="turmas")
    data = models.DateField()
    hora_inicio = models.TimeField(default=HORA_INICIO_PADRAO)
    hora_fim = models.TimeField(default=HORA_FIM_PADRAO)

    # A turma não tem cliente: administradora e condomínio são de cada
    # inscrito, porque um mesmo dia recebe funcionários de várias
    # administradoras e vários condomínios (ADR-0004).
    # Quem ministra e assina o certificado. Opcional na criação — a turma pode
    # ser marcada antes de se saber quem vai dar o curso — e obrigatório para
    # emitir certificado (fase D).
    instrutor = models.ForeignKey(
        InstrutorCipa, on_delete=models.SET_NULL, null=True, blank=True, related_name="turmas"
    )

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

    @property
    def codigo(self):
        """Identificador legível da turma: ano do curso + id, ex. CIPA-2026-0004.

        Derivado, não armazenado: não há o que digitar nem o que conflitar. A
        turma não tem nome (ADR-0004); o código é o que se cita por telefone,
        no PDF e na URL da tela.
        """
        return f"CIPA-{self.data.year}-{self.pk:04d}" if self.pk else ""

    def __str__(self):
        return f"{self.codigo} · {self.local.nome} em {self.data}"

    @property
    def capacidade(self):
        return self.local.capacidade

    @property
    def total_inscritos(self):
        return self.inscricoes.count()

    def contagem_presenca(self):
        """Presentes, ausentes e sem registro — contados uma vez, do prefetch."""
        presentes = ausentes = sem_registro = 0
        for inscricao in self.inscricoes.all():
            if inscricao.presenca is True:
                presentes += 1
            elif inscricao.presenca is False:
                ausentes += 1
            else:
                sem_registro += 1
        return {"presentes": presentes, "ausentes": ausentes, "sem_registro": sem_registro}

    def contagem_certificados(self):
        """Emitidos, presentes aptos sem certificado e presentes sem CNPJ (RF-HIS-005)."""
        emitidos = aptos = sem_cnpj = 0
        for inscricao in self.inscricoes.all():
            if inscricao.certificado_ou_none is not None:
                emitidos += 1
            elif inscricao.presenca is True:
                if inscricao.condominio_cnpj:
                    aptos += 1
                else:
                    sem_cnpj += 1
        return {
            "certificados_emitidos": emitidos,
            "aptos_sem_certificado": aptos,
            "presentes_sem_cnpj": sem_cnpj,
        }

    @property
    def tem_certificado(self):
        return any(i.certificado_ou_none is not None for i in self.inscricoes.all())


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

    # Presença (RF-HIS-004, PA-007): três estados — None = não registrada,
    # True presente, False ausente. "Não marcado" é diferente de "faltou": só
    # quem tem True recebe certificado; a omissão não vira documento.
    presenca = models.BooleanField(null=True, blank=True)
    presenca_registrada_em = models.DateTimeField(null=True, blank=True)
    presenca_registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="presencas_cipa_registradas",
    )

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

    @property
    def certificado_ou_none(self):
        """O certificado desta inscrição, ou None — sem levantar exceção do OneToOne."""
        try:
            return self.certificado
        except ObjectDoesNotExist:
            return None


class ContadorCertificado(models.Model):
    """Último sequencial emitido no ano: a linha é travada (`select_for_update`)
    na emissão para dois lotes simultâneos não repetirem número (RF-HIS-005)."""

    ano = models.PositiveIntegerField(unique=True)
    ultimo = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.ano}: {self.ultimo}"


class CertificadoCipa(models.Model):
    """Um certificado por inscrição presente (RF-HIS-005, RNF-HIS-003).

    Registro imutável: número e código não mudam, e nada aqui é apagado —
    turma e inscrição com certificado não se excluem nem se cancelam (PA-013).
    O PDF é derivado do registro a cada download (ADR-0007).
    """

    inscricao = models.OneToOneField(
        InscricaoCipa, on_delete=models.PROTECT, related_name="certificado"
    )
    # CIPA-AAAA-000000: ano da turma + sequencial por ano (PA-008).
    numero = models.CharField(max_length=20, unique=True)
    codigo_verificacao = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    emitido_em = models.DateTimeField(auto_now_add=True)
    emitido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="certificados_cipa_emitidos",
    )

    class Meta:
        ordering = ["numero"]
        verbose_name = "certificado CIPA"
        verbose_name_plural = "certificados CIPA"

    def __str__(self):
        return f"{self.numero} — {self.inscricao.nome}"

    @property
    def turma(self):
        return self.inscricao.turma
