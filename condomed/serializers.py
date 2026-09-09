# condomed/serializers.py
from rest_framework import serializers

from . import services
from .exceptions import ConflitoAgendamento
from .models import (
    HORA_FIM_PADRAO,
    HORA_INICIO_PADRAO,
    UNIDADE_CHOICES,
    InscricaoCipa,
    InstrutorCipa,
    LocalCipa,
    TurmaCipa,
    gerar_codigo,
)
from .validators import cnpj_valido, cpf_valido, normalizar_cnpj, normalizar_cpf

# Frase única da duplicidade de CPF: sai igual desta validação e da tradução
# da constraint do banco em `views.salvar_inscricao`.
CPF_DUPLICADO = "Este CPF já está inscrito nesta turma."

LIMITE_ASSINATURA_BYTES = 500 * 1024


def certificado_resumo(certificado):
    """Dicionário do certificado para inscrição e lote; None quando não há."""
    if certificado is None:
        return None
    quem = certificado.emitido_por
    return {
        "id": certificado.id,
        "inscricao_id": certificado.inscricao_id,
        "numero": certificado.numero,
        "codigo_verificacao": str(certificado.codigo_verificacao),
        "emitido_em": certificado.emitido_em,
        "emitido_por_nome": (quem.nome_completo or quem.email) if quem else "",
    }


class CodigoField(serializers.SlugRelatedField):
    """Local/instrutor na API são o `codigo` (string estável), não o id.

    Mantém o contrato que o frontend já usa desde as listas fixas. Aceita `""`
    e `null` como "sem instrutor" e devolve `""` nesse caso, como antes.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("slug_field", "codigo")
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if data in ("", None):
            if self.allow_null:
                return None
            self.fail("required")
        return super().to_internal_value(data)

    def to_representation(self, obj):
        return "" if obj is None else super().to_representation(obj)


class LocalCipaSerializer(serializers.ModelSerializer):
    """Cadastro de locais (RF-CIP-007)."""

    unidade = serializers.SerializerMethodField(read_only=True)
    unidade_codigo = serializers.ChoiceField(
        choices=UNIDADE_CHOICES, source="unidade", required=False, default="RIO"
    )
    turmas = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = LocalCipa
        fields = [
            "id", "codigo", "nome", "predio", "capacidade", "unidade", "unidade_codigo",
            "compartilha_sala_reuniao", "ativo", "turmas", "criado_em",
        ]
        read_only_fields = ["id", "codigo", "criado_em"]

    def get_unidade(self, obj):
        return obj.unidade_dados

    def get_turmas(self, obj):
        return obj.turmas.count()

    def validate_nome(self, valor):
        nome = (valor or "").strip()
        if not nome:
            raise serializers.ValidationError("Informe o nome do local.")
        repetidos = LocalCipa.objects.filter(ativo=True, nome__iexact=nome)
        if self.instance:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise serializers.ValidationError("Já existe um local ativo com este nome.")
        return nome

    def validate_capacidade(self, valor):
        if valor < 1:
            raise serializers.ValidationError("A capacidade deve ser de pelo menos 1 lugar.")
        return valor

    def validate(self, attrs):
        marca = attrs.get(
            "compartilha_sala_reuniao",
            getattr(self.instance, "compartilha_sala_reuniao", False),
        )
        ativo = attrs.get("ativo", getattr(self.instance, "ativo", True))
        if marca and ativo and services.sala_compartilhada_em_uso(
            excluir_id=self.instance.pk if self.instance else None
        ):
            raise serializers.ValidationError(
                {"compartilha_sala_reuniao": "Só um local ativo pode ser a sala de reunião da agenda."}
            )
        return attrs

    def create(self, validated_data):
        validated_data["codigo"] = gerar_codigo(
            validated_data["nome"], set(LocalCipa.objects.values_list("codigo", flat=True))
        )
        return super().create(validated_data)


class BooleanComPadraoEmForm(serializers.BooleanField):
    """Boolean que, ausente num multipart, usa o `default` em vez de virar False.

    O DRF trata checkbox ausente em formulário como False; aqui o formulário é
    o upload da assinatura, e "não mandei `ativo`" tem de significar "não mexi".
    """

    default_empty_html = serializers.empty


class InstrutorCipaSerializer(serializers.ModelSerializer):
    """Cadastro de palestrantes (RF-CIP-006). A assinatura entra, mas não sai."""

    ativo = BooleanComPadraoEmForm(required=False, default=True)
    registro = serializers.CharField(read_only=True)
    tem_assinatura = serializers.BooleanField(read_only=True)
    assinatura = serializers.ImageField(write_only=True, required=False, allow_null=True)
    turmas = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = InstrutorCipa
        fields = [
            "id", "codigo", "nome", "titulo", "registro_mte", "registro_uf", "registro",
            "assinatura", "tem_assinatura", "ativo", "turmas", "criado_em",
        ]
        read_only_fields = ["id", "codigo", "criado_em"]
        extra_kwargs = {"titulo": {"required": False}}
        # O unique_together e validado em `validate`, com a mensagem no campo
        # `registro_mte`, em vez do texto genérico do validador automático.
        validators = []

    def get_turmas(self, obj):
        return obj.turmas.count()

    def validate_nome(self, valor):
        nome = (valor or "").strip()
        if not nome:
            raise serializers.ValidationError("Informe o nome do palestrante.")
        return nome

    def validate_registro_uf(self, valor):
        uf = (valor or "").strip().upper()
        if len(uf) != 2 or not uf.isalpha():
            raise serializers.ValidationError("UF com duas letras (ex.: RJ).")
        return uf

    def validate_registro_mte(self, valor):
        mte = (valor or "").strip()
        if not mte:
            raise serializers.ValidationError("Informe o número do registro MTE.")
        return mte

    def validate_assinatura(self, arquivo):
        if arquivo is None:
            return arquivo
        if arquivo.size > LIMITE_ASSINATURA_BYTES:
            raise serializers.ValidationError("A assinatura deve ter até 500 KB.")
        formato = (getattr(arquivo, "image", None) and arquivo.image.format) or ""
        if formato.upper() not in ("PNG", "JPEG"):
            raise serializers.ValidationError("A assinatura deve ser PNG ou JPEG.")
        return arquivo

    def validate(self, attrs):
        mte = attrs.get("registro_mte", getattr(self.instance, "registro_mte", None))
        uf = attrs.get("registro_uf", getattr(self.instance, "registro_uf", None))
        repetidos = InstrutorCipa.objects.filter(registro_mte=mte, registro_uf=uf)
        if self.instance:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise serializers.ValidationError(
                {"registro_mte": "Já existe um palestrante com este registro MTE nesta UF."}
            )
        return attrs

    def create(self, validated_data):
        validated_data["codigo"] = gerar_codigo(
            validated_data["nome"], set(InstrutorCipa.objects.values_list("codigo", flat=True))
        )
        return super().create(validated_data)


class InscricaoCipaSerializer(serializers.ModelSerializer):
    # Aceita CPF formatado; normalizado para 11 dígitos em validate_cpf.
    cpf = serializers.CharField(max_length=14)
    # Idem para o CNPJ (18 com máscara, 14 gravados). Declarado aqui porque o
    # max_length herdado do model barraria a máscara antes do normalizador.
    condominio_cnpj = serializers.CharField(
        max_length=18, required=False, allow_blank=True, default=""
    )
    # Presença só muda pela action `presenca/` (lote, com auditoria); aqui é leitura.
    presenca_registrada_por_nome = serializers.SerializerMethodField(read_only=True)
    # Certificado (RF-HIS-005): número e emissão, ou null; muda só pela action `certificados/`.
    certificado = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = InscricaoCipa
        fields = [
            "id",
            "turma",
            "nome",
            "cpf",
            "funcao",
            "email",
            "telefone",
            "administradora_codigo",
            "administradora_nome",
            "condominio_nome",
            "condominio_cnpj",
            "presenca",
            "presenca_registrada_em",
            "presenca_registrada_por_nome",
            "certificado",
            "criado_em",
        ]
        read_only_fields = [
            "id", "turma", "criado_em",
            "presenca", "presenca_registrada_em", "presenca_registrada_por_nome", "certificado",
        ]
        extra_kwargs = {
            # O vínculo é obrigatório (INV-CIP-004): sem ele não se sabe de
            # quem é o participante, que é a razão da inscrição existir.
            "administradora_codigo": {"required": True, "allow_blank": False},
            "condominio_nome": {"required": True, "allow_blank": False},
        }

    def get_presenca_registrada_por_nome(self, obj):
        quem = obj.presenca_registrada_por
        if quem is None:
            return ""
        return quem.nome_completo or quem.email

    def get_certificado(self, obj):
        return certificado_resumo(obj.certificado_ou_none)

    def validate_condominio_cnpj(self, valor):
        """Opcional; quando vem, tem de ser um CNPJ válido, gravado só com dígitos."""
        cnpj = normalizar_cnpj(valor)
        if not cnpj:
            return ""
        if not cnpj_valido(cnpj):
            raise serializers.ValidationError("CNPJ inválido.")
        return cnpj

    def validate_condominio_nome(self, valor):
        nome = (valor or "").strip()
        if not nome:
            raise serializers.ValidationError("Informe o condomínio do participante.")
        return nome

    def validate_cpf(self, valor):
        cpf = normalizar_cpf(valor)
        if not cpf_valido(cpf):
            raise serializers.ValidationError("CPF inválido.")
        return cpf

    def validate(self, attrs):
        turma = self.context.get("turma")
        if turma is None:
            return attrs

        cpf = attrs.get("cpf") or (self.instance.cpf if self.instance else None)
        duplicados = turma.inscricoes.filter(cpf=cpf)
        if self.instance:
            duplicados = duplicados.exclude(pk=self.instance.pk)
        if duplicados.exists():
            raise serializers.ValidationError({"cpf": CPF_DUPLICADO})

        # A capacidade do local é referência, não trava (ADR-0006): chega
        # funcionário extra de última hora e a turma recebe. Quem sinaliza o
        # excesso é a tela, a partir de `capacidade` e `total_inscritos`.
        return attrs


class TurmaCipaSerializer(serializers.ModelSerializer):
    # `local`/`instrutor` viajam como código (RNF-CIP-004): mesmo contrato das listas fixas.
    local = CodigoField(queryset=LocalCipa.objects.all())
    instrutor = CodigoField(
        queryset=InstrutorCipa.objects.all(), required=False, allow_null=True
    )
    local_nome = serializers.SerializerMethodField(read_only=True)
    capacidade = serializers.SerializerMethodField(read_only=True)
    total_inscritos = serializers.SerializerMethodField(read_only=True)
    acima_da_capacidade = serializers.SerializerMethodField(read_only=True)
    tem_espelho = serializers.SerializerMethodField(read_only=True)
    # Derivados dos inscritos (ADR-0004): a turma não tem cliente, mas a tela
    # precisa rotular, filtrar e buscar o mês sem baixar todos os inscritos.
    administradoras = serializers.SerializerMethodField(read_only=True)
    condominios = serializers.SerializerMethodField(read_only=True)
    instrutor_nome = serializers.SerializerMethodField(read_only=True)
    # A tela de certificados antecipa o bloqueio "instrutor sem assinatura" (RF-HIS-005).
    instrutor_tem_assinatura = serializers.SerializerMethodField(read_only=True)
    codigo = serializers.CharField(read_only=True)
    # Contagens de presença vêm do backend (regra do repo); a tela não reconta.
    presentes = serializers.SerializerMethodField(read_only=True)
    ausentes = serializers.SerializerMethodField(read_only=True)
    sem_registro = serializers.SerializerMethodField(read_only=True)
    certificados_emitidos = serializers.SerializerMethodField(read_only=True)
    aptos_sem_certificado = serializers.SerializerMethodField(read_only=True)
    presentes_sem_cnpj = serializers.SerializerMethodField(read_only=True)
    inscricoes = InscricaoCipaSerializer(many=True, read_only=True)

    class Meta:
        model = TurmaCipa
        fields = [
            "id",
            "codigo",
            "local",
            "local_nome",
            "data",
            "hora_inicio",
            "hora_fim",
            "instrutor",
            "instrutor_nome",
            "instrutor_tem_assinatura",
            "observacao",
            "status",
            "capacidade",
            "total_inscritos",
            "acima_da_capacidade",
            "administradoras",
            "condominios",
            "tem_espelho",
            "presentes",
            "ausentes",
            "sem_registro",
            "certificados_emitidos",
            "aptos_sem_certificado",
            "presentes_sem_cnpj",
            "inscricoes",
            "criado_em",
        ]
        read_only_fields = ["id", "criado_em", "reserva_sala"]

    def to_representation(self, instance):
        dados = super().to_representation(instance)
        # Sem instrutor a API sempre devolveu "" (não null); o frontend depende disso.
        if dados.get("instrutor") is None:
            dados["instrutor"] = ""
        return dados

    def get_local_nome(self, obj):
        return obj.local.nome

    def get_instrutor_nome(self, obj):
        return obj.instrutor.nome if obj.instrutor else ""

    def get_instrutor_tem_assinatura(self, obj):
        return obj.instrutor.tem_assinatura if obj.instrutor else None

    def get_capacidade(self, obj):
        return services.capacidade_do_local(obj.local)

    def get_total_inscritos(self, obj):
        return obj.inscricoes.count()

    def get_presentes(self, obj):
        return obj.contagem_presenca()["presentes"]

    def get_ausentes(self, obj):
        return obj.contagem_presenca()["ausentes"]

    def get_sem_registro(self, obj):
        return obj.contagem_presenca()["sem_registro"]

    def get_certificados_emitidos(self, obj):
        return obj.contagem_certificados()["certificados_emitidos"]

    def get_aptos_sem_certificado(self, obj):
        return obj.contagem_certificados()["aptos_sem_certificado"]

    def get_presentes_sem_cnpj(self, obj):
        return obj.contagem_certificados()["presentes_sem_cnpj"]

    def get_acima_da_capacidade(self, obj):
        """Quantos passam da capacidade do local; 0 quando está dentro.

        A capacidade é referência, não limite (ADR-0006) — este campo existe
        para a tela sinalizar sem recontar a regra.
        """
        excesso = obj.inscricoes.count() - services.capacidade_do_local(obj.local)
        return max(excesso, 0)

    def get_administradoras(self, obj):
        """Administradoras presentes na turma, sem repetição, ordenadas por nome."""
        vistas = {}
        for inscricao in obj.inscricoes.all():
            vistas.setdefault(
                inscricao.administradora_codigo,
                {
                    "codigo": inscricao.administradora_codigo,
                    "nome": inscricao.administradora_nome,
                },
            )
        return sorted(vistas.values(), key=lambda a: (a["nome"] or "", a["codigo"]))

    def get_condominios(self, obj):
        """Condomínios presentes na turma, sem repetição."""
        return sorted({i.condominio_nome for i in obj.inscricoes.all()})

    def get_tem_espelho(self, obj):
        """False sinaliza INV-CIP-002 violado (espelho apagado pela agenda atual)."""
        if not obj.local.compartilha_sala_reuniao or obj.status not in services.STATUS_ATIVOS:
            return None
        return obj.reserva_sala_id is not None

    def validate(self, attrs):
        instancia = self.instance
        local = attrs.get("local", getattr(instancia, "local", None))
        data = attrs.get("data", getattr(instancia, "data", None))
        hora_inicio = attrs.get("hora_inicio") or getattr(
            instancia, "hora_inicio", None
        ) or HORA_INICIO_PADRAO
        hora_fim = attrs.get("hora_fim") or getattr(
            instancia, "hora_fim", None
        ) or HORA_FIM_PADRAO
        status_turma = attrs.get("status", getattr(instancia, "status", "agendada"))

        # PA-013: com certificado emitido, a turma não pode virar cancelada.
        if instancia is not None and status_turma == "cancelada" and instancia.status != "cancelada":
            motivo = services.motivo_turma_intocavel(instancia)
            if motivo:
                raise serializers.ValidationError({"status": motivo})

        # Cadastro desativado não entra em turma nova nem em troca; turma antiga
        # que já apontava para ele continua válida (RF-CIP-006/007).
        if "local" in attrs and not attrs["local"].ativo and (
            instancia is None or attrs["local"].pk != instancia.local_id
        ):
            raise serializers.ValidationError({"local": "Este local está desativado."})
        instrutor = attrs.get("instrutor")
        if instrutor is not None and not instrutor.ativo and (
            instancia is None or instrutor.pk != instancia.instrutor_id
        ):
            raise serializers.ValidationError({"instrutor": "Este palestrante está desativado."})

        if status_turma not in services.STATUS_ATIVOS:
            return attrs

        if hora_inicio >= hora_fim:
            raise serializers.ValidationError(
                {"hora_fim": "O fim do curso deve ser depois do início."}
            )

        # RF-CIP-001: conflito com outra turma no mesmo local e dia.
        conflito = services.turma_conflitante(
            local, data, hora_inicio, hora_fim,
            excluir_id=instancia.pk if instancia else None,
        )
        if conflito:
            raise ConflitoAgendamento(
                "Já existe uma turma CIPA neste local e dia.",
                {
                    "tipo": "turma",
                    "id": conflito.id,
                    "data": str(conflito.data),
                    "hora_inicio": str(conflito.hora_inicio),
                    "hora_fim": str(conflito.hora_fim),
                    "local_nome": conflito.local.nome,
                    # A turma é identificada por local + ocupação (ADR-0004);
                    # texto pronto porque o corpo do 409 vira string no DRF.
                    "ocupacao": (
                        f"{conflito.inscricoes.count()}"
                        f"/{conflito.local.capacidade}"
                    ),
                },
            )

        # RF-CIP-002: na sala de reunião, conflito também com a agenda atual.
        if local is not None and local.compartilha_sala_reuniao:
            reserva = services.reserva_conflitante(
                data, hora_inicio, hora_fim,
                excluir_reserva_id=instancia.reserva_sala_id if instancia else None,
            )
            if reserva:
                raise ConflitoAgendamento(
                    "A sala de reunião já está reservada neste dia e horário.",
                    {
                        "tipo": "reserva",
                        "id": reserva.id,
                        "tema": reserva.tema,
                        "data": str(reserva.data),
                        "horario": reserva.horario,
                        "duracao": reserva.duracao,
                    },
                )
        return attrs


class PresencaItemSerializer(serializers.Serializer):
    inscricao_id = serializers.IntegerField()
    # Presente ou ausente — não existe presença parcial (PA-007).
    presente = serializers.BooleanField()


class PresencaLoteSerializer(serializers.Serializer):
    """Corpo de `POST cursos-cipa/{id}/presenca/` (RF-HIS-004)."""

    presencas = PresencaItemSerializer(many=True, allow_empty=False)

    def validate_presencas(self, itens):
        vistos = set()
        for indice, item in enumerate(itens):
            if item["inscricao_id"] in vistos:
                raise serializers.ValidationError(
                    {str(indice): {"inscricao_id": ["Inscrição repetida no lote."]}}
                )
            vistos.add(item["inscricao_id"])
        return itens


class ImportarTurmaSerializer(serializers.Serializer):
    """Turma + inscritos de uma vez, para a importação por planilha.

    Existe para a turma e a lista nascerem na mesma transação: criar a turma
    primeiro e a lista depois deixaria turma vazia no sistema se a segunda
    metade falhasse.

    A validação da turma é a do `TurmaCipaSerializer` (conflito de local/dia e
    de reserva da sala), e a de cada linha é a do `InscricaoCipaSerializer` —
    a importação não afrouxa nenhuma regra.
    """

    local = CodigoField(queryset=LocalCipa.objects.all())
    data = serializers.DateField()
    instrutor = CodigoField(
        queryset=InstrutorCipa.objects.all(), required=False, allow_null=True, default=None
    )
    observacao = serializers.CharField(required=False, allow_blank=True, default="")
    inscricoes = serializers.ListField(
        child=serializers.DictField(), allow_empty=False
    )

    def validate(self, attrs):
        inscricoes = attrs["inscricoes"]

        # Planilha maior que a capacidade do local entra (ADR-0006): a tela
        # avisa o excesso e o operador decide. Recusar deixaria de fora quem
        # chegou de última hora, que é justamente o caso real.

        # As mesmas regras de linha, mais a duplicidade dentro da própria
        # planilha — que o unique_together pegaria só no banco, sem dizer onde.
        erros = {}
        cpfs = {}
        limpas = []
        for indice, linha in enumerate(inscricoes):
            serializer = InscricaoCipaSerializer(data=linha)
            if not serializer.is_valid():
                erros[str(indice)] = serializer.errors
                continue

            cpf = serializer.validated_data["cpf"]
            if cpf in cpfs:
                erros[str(indice)] = {
                    "cpf": [f"CPF repetido na planilha (linha {cpfs[cpf] + 1})."]
                }
                continue
            cpfs[cpf] = indice
            limpas.append(serializer.validated_data)

        if erros:
            raise serializers.ValidationError({"inscricoes": erros})

        attrs["inscricoes"] = limpas
        return attrs

    def criar(self, usuario):
        """Grava turma, espelho e inscritos. Chamado dentro de atomic pela view."""
        dados = self.validated_data
        turma_serializer = TurmaCipaSerializer(
            data={
                # `CodigoField` já resolveu os registros; o serializer da turma
                # recebe o código de novo, como se viesse do frontend.
                "local": dados["local"].codigo,
                "data": dados["data"],
                "instrutor": dados["instrutor"].codigo if dados.get("instrutor") else "",
                "observacao": dados.get("observacao", ""),
            }
        )
        # Deixa o 409 de conflito subir como em qualquer criação de turma.
        turma_serializer.is_valid(raise_exception=True)
        turma = turma_serializer.save(criado_por=usuario)
        services.sincronizar_espelho(turma, usuario)

        InscricaoCipa.objects.bulk_create([
            InscricaoCipa(turma=turma, **linha) for linha in dados["inscricoes"]
        ])
        return turma


class TurmaResumoSerializer(TurmaCipaSerializer):
    """Turma sem a lista de inscritos, para o histórico paginado.

    O histórico pode listar centenas de turmas; carregar os inscritos de cada
    uma só para mostrar contagens seria pagar por dados que a tela não usa. As
    contagens e as listas derivadas (`administradoras`, `condominios`) ficam.
    """

    class Meta(TurmaCipaSerializer.Meta):
        fields = [
            campo for campo in TurmaCipaSerializer.Meta.fields if campo != "inscricoes"
        ]


class InscricaoComTurmaSerializer(InscricaoCipaSerializer):
    """Inscrição com o resumo da turma, para a consulta de participantes.

    A consulta responde "onde esta pessoa esteve": cada linha é uma inscrição,
    e a turma vem junto para a tela não fazer uma requisição por linha.
    """

    turma = serializers.SerializerMethodField(read_only=True)

    class Meta(InscricaoCipaSerializer.Meta):
        fields = InscricaoCipaSerializer.Meta.fields

    def get_turma(self, obj):
        turma = obj.turma
        return {
            "id": turma.id,
            "codigo": turma.codigo,
            "data": turma.data,
            "local": turma.local.codigo,
            "local_nome": turma.local.nome,
            "status": turma.status,
        }
