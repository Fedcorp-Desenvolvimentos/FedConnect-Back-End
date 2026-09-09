# condomed/views.py
import openpyxl
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsCondomedOrAdmin

from . import documentos, services
from .models import CertificadoCipa, InscricaoCipa, InstrutorCipa, LocalCipa, TurmaCipa
from .serializers import (
    CPF_DUPLICADO,
    certificado_resumo,
    ImportarTurmaSerializer,
    InscricaoCipaSerializer,
    InscricaoComTurmaSerializer,
    InstrutorCipaSerializer,
    LocalCipaSerializer,
    PresencaLoteSerializer,
    TurmaCipaSerializer,
    TurmaResumoSerializer,
)
from .validators import cpf_valido, normalizar_cpf


class PaginacaoHistorico(PageNumberPagination):
    """Paginação das consultas de histórico (RF-HIS-001, RF-HIS-002).

    O calendário continua sem paginação (pede o mês inteiro); só as listas
    abertas por período paginam. 25 por página cabe numa tela sem rolagem
    infinita; `page_size` deixa a tela pedir mais quando fizer sentido.
    """

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100

# Colunas da planilha modelo, na ordem. O cabeçalho é o contrato com a tela:
# o parser do frontend casa por este texto, então mudar aqui é mudar lá.
def salvar_inscricao(serializer, **kwargs):
    """Grava a inscrição traduzindo a constraint de CPF duplicado em 400.

    O `unique_together (turma, cpf)` é a garantia final da regra — a validação
    do serializer não cobre duas requisições simultâneas com o mesmo CPF, que
    passam as duas pela checagem e só se encontram no banco. Sem esta
    tradução, a segunda viraria 500.

    É a única constraint de unicidade da tabela, então IntegrityError aqui só
    pode ser ela. O `atomic` isola a falha: no PostgreSQL, a transação fica
    inutilizável depois de um IntegrityError.
    """
    try:
        with transaction.atomic():
            return serializer.save(**kwargs)
    except IntegrityError as erro:
        raise ValidationError({"cpf": CPF_DUPLICADO}) from erro


COLUNAS_MODELO = [
    ("administradora", 28, "Delforte Administração"),
    ("condominio", 28, "Residencial Aurora"),
    ("cnpj_condominio", 20, "01.998.690/0001-82"),
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
    queryset = TurmaCipa.objects.select_related(
        "reserva_sala", "local", "instrutor"
    ).prefetch_related("inscricoes", "inscricoes__certificado", "inscricoes__certificado__emitido_por")

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        local = params.get("local")
        mes = params.get("mes")
        ano = params.get("ano")

        if local:
            queryset = queryset.filter(local__codigo=local)
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
        motivo = services.motivo_turma_intocavel(instance)
        if motivo:
            raise ValidationError({"detail": motivo})  # PA-013 → 400
        services.remover_espelho(instance)
        instance.delete()

    @action(detail=False, methods=["get"], url_path="historico")
    def historico(self, request):
        """Turmas por período, paginadas, com filtros que o calendário não tem.

        Rota separada de `GET cursos-cipa/` de propósito: o calendário depende
        daquela devolver o mês inteiro como lista, sem envelope de paginação.
        """
        params = request.query_params
        queryset = (
            TurmaCipa.objects.select_related("reserva_sala")
            .prefetch_related("inscricoes")
            .order_by("-data", "local")
        )

        if params.get("data_inicio"):
            queryset = queryset.filter(data__gte=params["data_inicio"])
        if params.get("data_fim"):
            queryset = queryset.filter(data__lte=params["data_fim"])
        if params.get("local"):
            queryset = queryset.filter(local__codigo=params["local"])
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        # Vínculo é do inscrito (ADR-0004): filtrar turma por administradora ou
        # condomínio é "turmas que têm gente de lá".
        if params.get("administradora"):
            queryset = queryset.filter(
                inscricoes__administradora_codigo=params["administradora"]
            )
        if params.get("condominio"):
            queryset = queryset.filter(
                inscricoes__condominio_nome__icontains=params["condominio"]
            )
        if params.get("busca"):
            termo = params["busca"].strip()
            queryset = queryset.filter(
                Q(inscricoes__nome__icontains=termo)
                | Q(inscricoes__cpf=normalizar_cpf(termo))
                | Q(inscricoes__condominio_nome__icontains=termo)
                | Q(inscricoes__administradora_nome__icontains=termo)
                | Q(observacao__icontains=termo)
            )
        queryset = queryset.distinct()

        paginador = PaginacaoHistorico()
        pagina = paginador.paginate_queryset(queryset, request, view=self)
        return paginador.get_paginated_response(
            TurmaResumoSerializer(pagina, many=True).data
        )

    @action(detail=False, methods=["get"], url_path="participantes")
    def participantes(self, request):
        """Inscrições em todas as turmas: onde cada pessoa esteve.

        Generaliza o `verificar-cpf`, que segue existindo para a tela de
        inscrição. Uma linha por inscrição — a mesma pessoa em três turmas são
        três linhas, porque presença e certificado (fases seguintes) são por
        inscrição.
        """
        params = request.query_params
        queryset = InscricaoCipa.objects.select_related("turma").order_by(
            "-turma__data", "condominio_nome", "nome"
        )

        if params.get("cpf"):
            queryset = queryset.filter(cpf=normalizar_cpf(params["cpf"]))
        if params.get("administradora"):
            queryset = queryset.filter(administradora_codigo=params["administradora"])
        if params.get("condominio"):
            queryset = queryset.filter(condominio_nome__icontains=params["condominio"])
        if params.get("data_inicio"):
            queryset = queryset.filter(turma__data__gte=params["data_inicio"])
        if params.get("data_fim"):
            queryset = queryset.filter(turma__data__lte=params["data_fim"])
        if params.get("busca"):
            termo = params["busca"].strip()
            digitos = normalizar_cpf(termo)
            filtro = (
                Q(nome__icontains=termo)
                | Q(condominio_nome__icontains=termo)
                | Q(administradora_nome__icontains=termo)
            )
            # Só compara CPF quando o termo tem dígitos: "Maria" não é CPF.
            if digitos:
                filtro |= Q(cpf__startswith=digitos)
            queryset = queryset.filter(filtro)

        paginador = PaginacaoHistorico()
        pagina = paginador.paginate_queryset(queryset, request, view=self)
        return paginador.get_paginated_response(
            InscricaoComTurmaSerializer(pagina, many=True).data
        )

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
        # CPF e CNPJ ficam como texto: formatados como número, o Excel come o
        # zero à esquerda e a linha volta inválida.
        colunas_texto = [
            indice
            for indice, (cabecalho, _, _) in enumerate(COLUNAS_MODELO, 1)
            if cabecalho in ("cpf", "cnpj_condominio")
        ]
        for linha in range(2, 200):
            for coluna in colunas_texto:
                aba.cell(row=linha, column=coluna).number_format = "@"

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
            .select_related("turma", "turma__local")
            .order_by("-turma__data")
        )
        excluir = request.query_params.get("excluir_turma")
        if excluir:
            inscricoes = inscricoes.exclude(turma_id=excluir)

        return Response([
            {
                "inscricao_id": inscricao.id,
                "turma_id": inscricao.turma_id,
                "turma_codigo": inscricao.turma.codigo,
                "nome": inscricao.nome,
                "data": inscricao.turma.data,
                "local": inscricao.turma.local.codigo,
                "local_nome": inscricao.turma.local.nome,
                # O vínculo é da inscrição (ADR-0004): é o que distingue
                # "repetiu a pessoa" de "a mesma pessoa vem por dois condomínios".
                "administradora_codigo": inscricao.administradora_codigo,
                "administradora_nome": inscricao.administradora_nome,
                "condominio_nome": inscricao.condominio_nome,
                "status": inscricao.turma.status,
            }
            for inscricao in inscricoes
        ])

    @action(detail=True, methods=["get"], url_path="lista-presenca")
    def lista_presenca(self, request, pk=None):
        """PDF da lista de presença para assinatura no dia (RF-HIS-003).

        Sempre disponível, inclusive antes do curso — é para levar impressa.
        Gerada do registro a cada download; nada é armazenado.
        """
        turma = self.get_object()
        pdf = documentos.gerar_lista_presenca(turma, usuario=request.user)
        resposta = HttpResponse(pdf, content_type="application/pdf")
        resposta["Content-Disposition"] = (
            f'attachment; filename="{documentos.nome_arquivo_lista_presenca(turma)}"'
        )
        # O frontend lê o nome do arquivo deste header; sem expor, o CORS o esconde.
        resposta["Access-Control-Expose-Headers"] = "Content-Disposition"
        return resposta

    @action(detail=True, methods=["post"], url_path="presenca")
    def presenca(self, request, pk=None):
        """Registra presença em lote (RF-HIS-004): `{presencas: [{inscricao_id, presente}]}`.

        Ou grava todas, ou nenhuma. Recusa turma cancelada e turma cuja data
        ainda não chegou (PA-009). A primeira gravação deixa a turma
        `realizada`; regravar é permitido a qualquer tempo (PA-007), sempre
        com quem e quando. Devolve a turma completa, já com as contagens.
        """
        turma = self.get_object()
        impedimento = services.validar_turma_para_presenca(turma)
        if impedimento:
            return Response({"detail": impedimento}, status=status.HTTP_400_BAD_REQUEST)

        lote = PresencaLoteSerializer(data=request.data)
        lote.is_valid(raise_exception=True)
        erros = services.registrar_presenca(
            turma, lote.validated_data["presencas"], request.user
        )
        if erros:
            return Response({"presencas": erros}, status=status.HTTP_400_BAD_REQUEST)

        turma = self.get_queryset().get(pk=turma.pk)  # recarrega com o prefetch
        return Response(TurmaCipaSerializer(turma).data)

    @action(detail=True, methods=["post"], url_path="certificados")
    def certificados(self, request, pk=None):
        """Emite certificados para os presentes aptos da turma (RF-HIS-005).

        Recusa o lote inteiro (400) por turma cancelada, sem presença, sem
        instrutor ou instrutor sem assinatura. Presente sem CNPJ fica em
        `impedidos`; o resto sai. Idempotente. Devolve o lote e a turma.
        """
        turma = self.get_object()
        impedimento = services.validar_turma_para_certificado(turma)
        if impedimento:
            return Response({"detail": impedimento}, status=status.HTTP_400_BAD_REQUEST)

        lote = services.emitir_certificados(turma, request.user)
        turma = self.get_queryset().get(pk=turma.pk)
        return Response({
            "emitidos": [certificado_resumo(c) for c in lote["emitidos"]],
            "ja_existentes": [certificado_resumo(c) for c in lote["ja_existentes"]],
            "impedidos": lote["impedidos"],
            "turma": TurmaCipaSerializer(turma).data,
        })

    @action(detail=True, methods=["get"], url_path="certificados/pdf")
    def certificados_pdf(self, request, pk=None):
        """Todos os certificados emitidos da turma num PDF, duas páginas cada (RF-HIS-006)."""
        turma = self.get_object()
        certificados = list(
            CertificadoCipa.objects.filter(inscricao__turma=turma)
            .select_related("inscricao", "inscricao__turma", "inscricao__turma__local", "inscricao__turma__instrutor")
            .order_by("numero")
        )
        if not certificados:
            return Response(
                {"detail": "Esta turma ainda não tem certificado emitido."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return resposta_pdf(
            documentos.gerar_certificados(certificados, usuario=request.user),
            f"certificados-{turma.codigo}.pdf",
        )

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
        # limite (ADR-0006). A unicidade de CPF por turma segue no
        # `unique_together`, e `salvar_inscricao` traduz a constraint em 400.
        turma = self.get_object()
        serializer = InscricaoCipaSerializer(
            data=request.data, context={"turma": turma, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        salvar_inscricao(serializer, turma=turma)
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
            if inscricao.certificado_ou_none is not None:
                return Response(
                    {"detail": "Este participante tem certificado emitido e não pode ser removido da turma."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            inscricao.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = InscricaoCipaSerializer(
            inscricao, data=request.data, partial=True, context={"turma": turma}
        )
        serializer.is_valid(raise_exception=True)
        salvar_inscricao(serializer)
        return Response(serializer.data)


class CadastroCipaViewSet(viewsets.ModelViewSet):
    """Base dos cadastros da Condomed (RF-CIP-006/007): condomed e admin editam.

    Lista só os ativos, salvo `?todos=1`. `DELETE` só sem turma vinculada —
    com turma, a resposta é 400 e o caminho é desativar (PA-010): o histórico
    e os certificados já emitidos citam o registro.
    """

    permission_classes = [IsCondomedOrAdmin]
    pagination_class = None
    nome_do_registro = "registro"

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get("todos") not in ("1", "true"):
            queryset = queryset.filter(ativo=True)
        return queryset

    def get_object(self):
        # Editar/desativar um inativo precisa achá-lo mesmo sem ?todos=1.
        obj = self.queryset.model.objects.filter(pk=self.kwargs["pk"]).first()
        if obj is None:
            from django.http import Http404

            raise Http404
        self.check_object_permissions(self.request, obj)
        return obj

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.turmas.exists():
            return Response(
                {
                    "detail": (
                        f"Este {self.nome_do_registro} tem turmas vinculadas e não pode ser "
                        "excluído. Desative-o: ele sai das opções e continua no histórico."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LocalCipaViewSet(CadastroCipaViewSet):
    """`cursos-cipa/locais/` — locais do curso, com capacidade e unidade emissora."""

    queryset = LocalCipa.objects.all()
    serializer_class = LocalCipaSerializer
    nome_do_registro = "local"


class InstrutorCipaViewSet(CadastroCipaViewSet):
    """`cursos-cipa/instrutores/` — palestrantes; assinatura por multipart, nunca exposta."""

    queryset = InstrutorCipa.objects.all()
    serializer_class = InstrutorCipaSerializer
    nome_do_registro = "palestrante"


def resposta_pdf(conteudo, nome_arquivo):
    """PDF para download com o nome exposto ao CORS (o frontend lê o header)."""
    resposta = HttpResponse(conteudo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
    resposta["Access-Control-Expose-Headers"] = "Content-Disposition"
    return resposta


class CertificadoPdfView(APIView):
    """`GET certificados/<numero>/pdf/` — reemissão de um certificado (RF-HIS-006).

    Mesmo número, conteúdo regenerado do registro na hora (ADR-0007).
    """

    permission_classes = [IsCondomedOrAdmin]

    def get(self, request, numero):
        certificado = (
            CertificadoCipa.objects.select_related(
                "inscricao", "inscricao__turma", "inscricao__turma__local", "inscricao__turma__instrutor"
            )
            .filter(numero=numero)
            .first()
        )
        if certificado is None:
            return Response({"detail": "Certificado não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return resposta_pdf(
            documentos.gerar_certificados([certificado], usuario=request.user),
            f"certificado-{certificado.numero}.pdf",
        )
