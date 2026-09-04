# condomed/views.py
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.permissions import IsCondomedOrAdmin

from . import services
from .models import LOCAIS_CIPA, InscricaoCipa, TurmaCipa
from .serializers import InscricaoCipaSerializer, TurmaCipaSerializer
from .validators import cpf_valido, normalizar_cpf


class TurmaCipaViewSet(viewsets.ModelViewSet):
    """Turmas do curso CIPA (RF-CIP-001..004). Acesso: condomed + admin."""

    serializer_class = TurmaCipaSerializer
    permission_classes = [IsCondomedOrAdmin]
    # O calendário pede o mês inteiro de uma vez; sem paginação a resposta é uma lista.
    pagination_class = None
    queryset = TurmaCipa.objects.select_related("reserva_sala").prefetch_related(
        "inscricoes"
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        local = params.get("local")
        mes = params.get("mes")
        ano = params.get("ano")

        if local:
            queryset = queryset.filter(local=local)
        if ano:
            queryset = queryset.filter(data__year=ano)
        if mes:
            queryset = queryset.filter(data__month=mes)
        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        # Turma + Reserva espelho na mesma transação (RNF-CIP-002).
        turma = serializer.save(criado_por=self.request.user)
        services.sincronizar_espelho(turma, self.request.user)

    @transaction.atomic
    def perform_update(self, serializer):
        turma = serializer.save()
        services.sincronizar_espelho(turma, self.request.user)

    @transaction.atomic
    def perform_destroy(self, instance):
        services.remover_espelho(instance)
        instance.delete()

    @action(detail=False, methods=["get"], url_path="locais")
    def locais(self, request):
        """Locais e capacidades para montar as abas do frontend."""
        return Response([
            {"codigo": codigo, **dados} for codigo, dados in LOCAIS_CIPA.items()
        ])

    @action(detail=False, methods=["get"], url_path="verificar-cpf")
    def verificar_cpf(self, request):
        """Onde mais este CPF já está inscrito.

        Duplicidade na mesma turma é barrada no serializer; entre turmas é
        permitida, e a tela usa esta consulta para avisar antes de gravar.
        `excluir_turma` tira da resposta a turma que está sendo preenchida.
        """
        cpf = normalizar_cpf(request.query_params.get("cpf", ""))
        if not cpf_valido(cpf):
            return Response(
                {"detail": "CPF inválido."}, status=status.HTTP_400_BAD_REQUEST
            )

        inscricoes = (
            InscricaoCipa.objects.filter(cpf=cpf)
            .select_related("turma")
            .order_by("-turma__data")
        )
        excluir = request.query_params.get("excluir_turma")
        if excluir:
            inscricoes = inscricoes.exclude(turma_id=excluir)

        return Response([
            {
                "inscricao_id": inscricao.id,
                "turma_id": inscricao.turma_id,
                "nome": inscricao.nome,
                "data": inscricao.turma.data,
                "local": inscricao.turma.local,
                "local_nome": LOCAIS_CIPA.get(inscricao.turma.local, {}).get(
                    "nome", inscricao.turma.local
                ),
                # O vínculo é da inscrição (ADR-0004): é o que distingue
                # "repetiu a pessoa" de "a mesma pessoa vem por dois condomínios".
                "administradora_codigo": inscricao.administradora_codigo,
                "administradora_nome": inscricao.administradora_nome,
                "condominio_nome": inscricao.condominio_nome,
                "status": inscricao.turma.status,
            }
            for inscricao in inscricoes
        ])

    @action(detail=True, methods=["get", "post"], url_path="inscricoes")
    def inscricoes(self, request, pk=None):
        if request.method == "GET":
            turma = self.get_object()
            serializer = InscricaoCipaSerializer(
                turma.inscricoes.all(), many=True
            )
            return Response(serializer.data)

        # POST — trava a turma para não estourar a capacidade em corrida (INV-CIP-003).
        with transaction.atomic():
            turma = services.travar_turma(self.get_object().pk)
            serializer = InscricaoCipaSerializer(
                data=request.data, context={"turma": turma, "request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(turma=turma)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"inscricoes/(?P<inscricao_id>\d+)",
    )
    def inscricao_detalhe(self, request, pk=None, inscricao_id=None):
        turma = self.get_object()
        inscricao = turma.inscricoes.filter(pk=inscricao_id).first()
        if inscricao is None:
            return Response(
                {"detail": "Inscrição não encontrada nesta turma."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "DELETE":
            inscricao.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = InscricaoCipaSerializer(
            inscricao, data=request.data, partial=True, context={"turma": turma}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
