# condomed/views.py
import openpyxl
from django.db import transaction
from django.http import HttpResponse
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.permissions import IsCondomedOrAdmin

from . import services
from .models import LOCAIS_CIPA, InscricaoCipa, TurmaCipa
from .serializers import (
    ImportarTurmaSerializer,
    InscricaoCipaSerializer,
    TurmaCipaSerializer,
)
from .validators import cpf_valido, normalizar_cpf

# Colunas da planilha modelo, na ordem. O cabeçalho é o contrato com a tela:
# o parser do frontend casa por este texto, então mudar aqui é mudar lá.
COLUNAS_MODELO = [
    ("administradora", 28, "Delforte Administração"),
    ("condominio", 28, "Residencial Aurora"),
    ("nome", 30, "Maria Aparecida da Silva"),
    ("cpf", 16, "529.982.247-25"),
    ("funcao", 20, "Zeladora"),
    ("email", 26, "maria@exemplo.com.br"),
    ("telefone", 18, "11999998888"),
]


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

    @action(detail=False, methods=["get"], url_path="planilha-modelo")
    def planilha_modelo(self, request):
        """Planilha modelo dos inscritos, com uma linha de exemplo.

        Local e data são escolhidos na tela, não na planilha: uma planilha é
        uma turma, e data errada em célula é erro caro de achar.
        """
        workbook = openpyxl.Workbook()
        aba = workbook.active
        aba.title = "Inscritos"

        for indice, (cabecalho, largura, exemplo) in enumerate(COLUNAS_MODELO, 1):
            celula = aba.cell(row=1, column=indice, value=cabecalho)
            celula.font = Font(bold=True, color="FFFFFF")
            celula.fill = PatternFill("solid", start_color="0F3D5D")
            celula.alignment = Alignment(horizontal="center")
            aba.column_dimensions[get_column_letter(indice)].width = largura
            aba.cell(row=2, column=indice, value=exemplo)

        aba.freeze_panes = "A2"
        # O CPF fica como texto: formatado como número, o Excel come o zero à
        # esquerda e a linha volta inválida.
        for linha in range(2, 200):
            aba.cell(row=linha, column=4).number_format = "@"

        resposta = HttpResponse(
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        )
        resposta["Content-Disposition"] = (
            'attachment; filename="modelo-inscritos-cipa.xlsx"'
        )
        workbook.save(resposta)
        return resposta

    @action(detail=False, methods=["post"], url_path="importar")
    def importar(self, request):
        """Cria a turma com os inscritos da planilha, tudo na mesma transação.

        Ou nasce completa, ou não nasce: turma vazia por falha na segunda
        metade seria pior que erro nenhum. A tela já valida linha a linha e só
        envia o que passou, então aqui o payload é tudo-ou-nada.
        """
        serializer = ImportarTurmaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            turma = serializer.criar(request.user)

        return Response(
            TurmaCipaSerializer(turma).data, status=status.HTTP_201_CREATED
        )

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

        # Sem `select_for_update`: ele existia só para a capacidade não ser
        # estourada em corrida (INV-CIP-003), e a capacidade deixou de ser
        # limite (ADR-0006). A unicidade de CPF por turma segue garantida pelo
        # `unique_together` no banco.
        turma = self.get_object()
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
