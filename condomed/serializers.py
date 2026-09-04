# condomed/serializers.py
from rest_framework import serializers

from . import services
from .exceptions import ConflitoAgendamento
from .models import (
    HORA_FIM_PADRAO,
    HORA_INICIO_PADRAO,
    LOCAIS_CIPA,
    LOCAL_CHOICES,
    SALA_REUNIAO,
    InscricaoCipa,
    TurmaCipa,
)
from .validators import cpf_valido, normalizar_cpf


class InscricaoCipaSerializer(serializers.ModelSerializer):
    # Aceita CPF formatado; normalizado para 11 dígitos em validate_cpf.
    cpf = serializers.CharField(max_length=14)

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
            "criado_em",
        ]
        read_only_fields = ["id", "turma", "criado_em"]
        extra_kwargs = {
            # O vínculo é obrigatório (INV-CIP-004): sem ele não se sabe de
            # quem é o participante, que é a razão da inscrição existir.
            "administradora_codigo": {"required": True, "allow_blank": False},
            "condominio_nome": {"required": True, "allow_blank": False},
        }

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
            raise serializers.ValidationError(
                {"cpf": "Este CPF já está inscrito nesta turma."}
            )

        # Capacidade (INV-CIP-003) — a view segura a turma com select_for_update.
        if self.instance is None:
            capacidade = services.capacidade_do_local(turma.local)
            if turma.inscricoes.count() >= capacidade:
                raise serializers.ValidationError(
                    f"Turma lotada: o local comporta {capacidade} participantes."
                )
        return attrs


class TurmaCipaSerializer(serializers.ModelSerializer):
    local_nome = serializers.SerializerMethodField(read_only=True)
    capacidade = serializers.SerializerMethodField(read_only=True)
    total_inscritos = serializers.SerializerMethodField(read_only=True)
    tem_espelho = serializers.SerializerMethodField(read_only=True)
    # Derivados dos inscritos (ADR-0004): a turma não tem cliente, mas a tela
    # precisa rotular, filtrar e buscar o mês sem baixar todos os inscritos.
    administradoras = serializers.SerializerMethodField(read_only=True)
    condominios = serializers.SerializerMethodField(read_only=True)
    inscricoes = InscricaoCipaSerializer(many=True, read_only=True)

    class Meta:
        model = TurmaCipa
        fields = [
            "id",
            "local",
            "local_nome",
            "data",
            "hora_inicio",
            "hora_fim",
            "observacao",
            "status",
            "capacidade",
            "total_inscritos",
            "administradoras",
            "condominios",
            "tem_espelho",
            "inscricoes",
            "criado_em",
        ]
        read_only_fields = ["id", "criado_em", "reserva_sala"]

    def get_local_nome(self, obj):
        return LOCAIS_CIPA.get(obj.local, {}).get("nome", obj.local)

    def get_capacidade(self, obj):
        return services.capacidade_do_local(obj.local)

    def get_total_inscritos(self, obj):
        return obj.inscricoes.count()

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
        if obj.local != SALA_REUNIAO or obj.status not in services.STATUS_ATIVOS:
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
                    "local_nome": LOCAIS_CIPA.get(conflito.local, {}).get(
                        "nome", conflito.local
                    ),
                    # A turma é identificada por local + ocupação (ADR-0004);
                    # texto pronto porque o corpo do 409 vira string no DRF.
                    "ocupacao": (
                        f"{conflito.inscricoes.count()}"
                        f"/{services.capacidade_do_local(conflito.local)}"
                    ),
                },
            )

        # RF-CIP-002: na sala de reunião, conflito também com a agenda atual.
        if local == SALA_REUNIAO:
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


class ImportarTurmaSerializer(serializers.Serializer):
    """Turma + inscritos de uma vez, para a importação por planilha.

    Existe para a turma e a lista nascerem na mesma transação: criar a turma
    primeiro e a lista depois deixaria turma vazia no sistema se a segunda
    metade falhasse.

    A validação da turma é a do `TurmaCipaSerializer` (conflito de local/dia e
    de reserva da sala), e a de cada linha é a do `InscricaoCipaSerializer` —
    a importação não afrouxa nenhuma regra.
    """

    local = serializers.ChoiceField(choices=LOCAL_CHOICES)
    data = serializers.DateField()
    observacao = serializers.CharField(required=False, allow_blank=True, default="")
    inscricoes = serializers.ListField(
        child=serializers.DictField(), allow_empty=False
    )

    def validate(self, attrs):
        local = attrs["local"]
        inscricoes = attrs["inscricoes"]

        capacidade = services.capacidade_do_local(local)
        if len(inscricoes) > capacidade:
            raise serializers.ValidationError({
                "inscricoes": (
                    f"A planilha tem {len(inscricoes)} pessoas e o local comporta "
                    f"{capacidade}. Nada foi importado."
                )
            })

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
                "local": dados["local"],
                "data": dados["data"],
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
