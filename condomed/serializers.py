# condomed/serializers.py
from rest_framework import serializers

from . import services
from .exceptions import ConflitoAgendamento
from .models import (
    HORA_FIM_PADRAO,
    HORA_INICIO_PADRAO,
    LOCAIS_CIPA,
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
            "criado_em",
        ]
        read_only_fields = ["id", "turma", "criado_em"]

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
            "administradora_codigo",
            "administradora_nome",
            "condominio_nome",
            "observacao",
            "status",
            "capacidade",
            "total_inscritos",
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
                    "condominio_nome": conflito.condominio_nome,
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
