"""Endpoints dos indicadores executivos (spec indicadores-executivos, RF-IEX-002..007).

Seis leituras, uma por seção do painel, com os mesmos parâmetros de filtro.
Qualquer autenticado lê (RNF-IEX-001, decisão do dono em PA-018); se a
decisão mudar, a classe entra em `users/permissions.py` e troca-se uma linha
em `_IndicadorBase`. Nada aqui passa pelo FedHub: o dado é o espelho local.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from indicadores.serializers import FiltrosSerializer, SerieParametrosSerializer
from indicadores.services import agregacao, nao_fechadas
from indicadores.services.periodos import ParametroInvalido

PARAMETROS_COMUNS = [
    OpenApiParameter("periodo", OpenApiTypes.STR, description="hoje · semana · mes · ano · faixa (padrão mes)"),
    OpenApiParameter("data_referencia", OpenApiTypes.DATE, description="AAAA-MM-DD; padrão hoje em America/Sao_Paulo"),
    OpenApiParameter("data_ini", OpenApiTypes.DATE, description="Só com periodo=faixa"),
    OpenApiParameter("data_fim", OpenApiTypes.DATE, description="Só com periodo=faixa; invertidos são trocados"),
    OpenApiParameter("ramo", OpenApiTypes.STR, many=True, description="Repetível: ?ramo=COND&ramo=FIAN"),
    OpenApiParameter("seguradora", OpenApiTypes.STR, many=True, description="Repetível"),
    OpenApiParameter("incluir_cancelados", OpenApiTypes.BOOL, description="Padrão false"),
    OpenApiParameter("todos_tipdoc", OpenApiTypes.BOOL, description="Padrão false (só tipdoc A)"),
    OpenApiParameter("janela_dias", OpenApiTypes.INT, description="0..180, padrão 30 (não fechadas)"),
]


class _IndicadorBase(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def filtros(self, request):
        """`(Filtros, None)` ou `(None, Response 400)`."""
        try:
            return FiltrosSerializer.validar(request.query_params), None
        except ParametroInvalido as erro:
            return None, Response({"sucesso": False, "erro": str(erro)}, status=status.HTTP_400_BAD_REQUEST)


class DominiosView(_IndicadorBase):
    """`GET indicadores/dominios/` — ramos, seguradoras e metadados da carga (RF-IEX-002)."""

    @extend_schema(parameters=PARAMETROS_COMUNS, responses={200: OpenApiTypes.OBJECT}, tags=["indicadores"])
    def get(self, request, *args, **kwargs):
        filtros, erro = self.filtros(request)
        if erro:
            return erro
        return Response({"sucesso": True, **agregacao.dominios(filtros)})


class ResumoView(_IndicadorBase):
    """`GET indicadores/resumo/` — os cartões do período, o anterior e hoje/semana/mês/ano (RF-IEX-003)."""

    @extend_schema(parameters=PARAMETROS_COMUNS, responses={200: OpenApiTypes.OBJECT}, tags=["indicadores"])
    def get(self, request, *args, **kwargs):
        filtros, erro = self.filtros(request)
        if erro:
            return erro
        return Response({"sucesso": True, **agregacao.resumo(filtros)})


class PorSeguradoraView(_IndicadorBase):
    """`GET indicadores/por-seguradora/` — uma linha por seguradora e o total (RF-IEX-004)."""

    @extend_schema(parameters=PARAMETROS_COMUNS, responses={200: OpenApiTypes.OBJECT}, tags=["indicadores"])
    def get(self, request, *args, **kwargs):
        filtros, erro = self.filtros(request)
        if erro:
            return erro
        return Response({"sucesso": True, **agregacao.por_seguradora(filtros)})


class SerieView(_IndicadorBase):
    """`GET indicadores/serie/?tipo=dia|mes` — 30 dias até a referência ou 12 meses do ano (RF-IEX-005)."""

    @extend_schema(
        parameters=PARAMETROS_COMUNS + [OpenApiParameter("tipo", OpenApiTypes.STR, description="dia · mes (padrão mes)")],
        responses={200: OpenApiTypes.OBJECT},
        tags=["indicadores"],
    )
    def get(self, request, *args, **kwargs):
        filtros, erro = self.filtros(request)
        if erro:
            return erro
        tipo = SerieParametrosSerializer(data=request.query_params)
        if not tipo.is_valid():
            return Response({"sucesso": False, "erro": "tipo deve ser dia ou mes."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"sucesso": True, **agregacao.serie(filtros, tipo.validated_data["tipo"])})


class NaoFechadasView(_IndicadorBase):
    """`GET indicadores/nao-fechadas/` — apólices que vencem no mês da referência (RF-IEX-006)."""

    @extend_schema(parameters=PARAMETROS_COMUNS, responses={200: OpenApiTypes.OBJECT}, tags=["indicadores"])
    def get(self, request, *args, **kwargs):
        filtros, erro = self.filtros(request)
        if erro:
            return erro
        return Response({"sucesso": True, **nao_fechadas.calcular(filtros).resposta()})


class ComposicaoView(_IndicadorBase):
    """`GET indicadores/composicao/` — quais objetos compõem cada cartão (RF-IEX-007)."""

    @extend_schema(parameters=PARAMETROS_COMUNS, responses={200: OpenApiTypes.OBJECT}, tags=["indicadores"])
    def get(self, request, *args, **kwargs):
        filtros, erro = self.filtros(request)
        if erro:
            return erro
        return Response({"sucesso": True, **agregacao.composicao(filtros)})
