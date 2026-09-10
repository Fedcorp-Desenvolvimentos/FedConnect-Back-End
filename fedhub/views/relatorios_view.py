"""Relatório de faturas pendentes (spec relatorio-faturas-pendentes, RF-FAT-001..003).

Três rotas com os mesmos filtros: dados para a tela, planilha e PDF. A regra
do que é pendente é do FedHub; aqui só se repassa e se formata.
"""
import logging

from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from consultas.utils.renderers import BinaryRenderer
from users.permissions import IsFinanceiroOuFaturamentoOuAdmin

from fedhub import relatorios_documentos as documentos
from fedhub.services.relatorios_service import (
    FedHubDemorou,
    FedHubIndisponivel,
    FedHubRecusou,
    RelatoriosFedhubService,
    filtrar_parametros,
)

logger = logging.getLogger(__name__)


class _BaseFaturasPendentes(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsFinanceiroOuFaturamentoOuAdmin]

    def buscar(self, request):
        """Resposta do FedHub ou uma `Response` de erro pronta (502/504/400)."""
        filtros = filtrar_parametros(request.query_params)
        try:
            return RelatoriosFedhubService().faturas_pendentes(filtros), None
        except FedHubDemorou:
            return None, Response(
                {"sucesso": False, "erro": "O FedHub demorou para responder. Tente novamente em instantes."},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except FedHubIndisponivel:
            return None, Response(
                {"sucesso": False, "erro": "FedHub indisponível no momento."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except FedHubRecusou as erro:
            # 400 do FedHub (filtro inválido) volta como 400; o resto vira 502.
            codigo = status.HTTP_400_BAD_REQUEST if erro.status_code == 400 else status.HTTP_502_BAD_GATEWAY
            return None, Response({"sucesso": False, "erro": erro.detalhe}, status=codigo)


class FaturasPendentesView(_BaseFaturasPendentes):
    """`GET faturas/pendentes/` — linhas e totais do FedHub, sem recontar (RF-FAT-001)."""

    def get(self, request, *args, **kwargs):
        dados, erro = self.buscar(request)
        if erro:
            return erro
        return Response({"sucesso": True, **dados})


def _resposta_arquivo(conteudo: bytes, content_type: str, nome: str) -> HttpResponse:
    resposta = HttpResponse(conteudo, content_type=content_type)
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    # O frontend lê o nome do arquivo deste header; sem expor, o CORS o esconde.
    resposta["Access-Control-Expose-Headers"] = "Content-Disposition"
    return resposta


class FaturasPendentesExcelView(_BaseFaturasPendentes):
    """`GET faturas/pendentes/exportar-excel/` — uma linha por documento (RF-FAT-002)."""

    renderer_classes = [BinaryRenderer]

    def get(self, request, *args, **kwargs):
        dados, erro = self.buscar(request)
        if erro:
            return erro
        # Relatório vazio é resultado: planilha só com cabeçalho e totais zerados.
        return _resposta_arquivo(
            documentos.gerar_planilha(dados),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            documentos.nome_arquivo("xlsx", dados.get("referencia", "")),
        )


class FaturasPendentesPDFView(_BaseFaturasPendentes):
    """`GET faturas/pendentes/exportar-pdf/` — layout do legado (RF-FAT-003)."""

    renderer_classes = [BinaryRenderer]

    def get(self, request, *args, **kwargs):
        dados, erro = self.buscar(request)
        if erro:
            return erro
        return _resposta_arquivo(
            documentos.gerar_pdf(dados),
            "application/pdf",
            documentos.nome_arquivo("pdf", dados.get("referencia", "")),
        )
