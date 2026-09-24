"""Endpoints dos indicadores executivos (spec indicadores-executivos, RF-IEX-002..008).

Seis leituras, uma por seção do painel, com os mesmos parâmetros de filtro,
mais o cadastro de metas mensais (RF-IEX-008). Só `admin` e `ti` leem **e
cadastram metas** (RNF-IEX-001; PA-036 revisada em 2026-09-23 — antes, qualquer
autenticado, por PA-018 e PA-023). A regra vive em `users.permissions.IsAdminOrTi`
e é aplicada numa linha em `_IndicadorBase`. Nada aqui passa pelo FedHub: o dado
é o espelho local.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
import requests

from django.utils import timezone

from indicadores.serializers import (
    CompetenciaSerializer,
    FiltrosSerializer,
    MetaMensalEntradaSerializer,
    SerieParametrosSerializer,
)
from indicadores.services import agregacao, fedhub_lake, metas, nao_fechadas, painel_tv
from indicadores.services.periodos import ParametroInvalido
from users.permissions import IsAdminOrTi

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
    permission_classes = [IsAdminOrTi]

    def filtros(self, request):
        """`(Filtros, None)` ou `(None, Response 400)`."""
        try:
            return FiltrosSerializer.validar(request.query_params), None
        except ParametroInvalido as erro:
            return None, Response({"sucesso": False, "erro": str(erro)}, status=status.HTTP_400_BAD_REQUEST)


def _lake_fora(erro: fedhub_lake.LakeIndisponivel) -> Response:
    """FedHub ou lake fora: 503 com o erro que o FedHub nomeou (RF-IEX-010)."""
    return Response(
        {"sucesso": False, "erro": erro.erro, "detalhe": erro.detalhe}, status=status.HTTP_503_SERVICE_UNAVAILABLE
    )


def _erro_400(serializer) -> Response:
    """Primeiro erro do serializer no formato `{"sucesso": false, "erro": "campo: mensagem"}`."""
    campo, mensagens = next(iter(serializer.errors.items()))
    mensagem = mensagens[0] if isinstance(mensagens, list) else mensagens
    return Response({"sucesso": False, "erro": f"{campo}: {mensagem}"}, status=status.HTTP_400_BAD_REQUEST)


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


class MetasView(_IndicadorBase):
    """`GET/POST indicadores/metas/` — metas mensais por seguradora × ramo (RF-IEX-008, PA-023)."""

    @extend_schema(
        parameters=[OpenApiParameter("competencia", OpenApiTypes.STR, description="AAAA-MM; padrão mês corrente")],
        responses={200: OpenApiTypes.OBJECT},
        tags=["indicadores"],
    )
    def get(self, request, *args, **kwargs):
        parametros = CompetenciaSerializer(data=request.query_params)
        if not parametros.is_valid():
            return _erro_400(parametros)
        competencia = parametros.validated_data.get("competencia") or timezone.localdate().replace(day=1)
        try:
            return Response({"sucesso": True, **metas.listar(competencia)})
        except fedhub_lake.LakeIndisponivel as erro:
            return _lake_fora(erro)

    @extend_schema(request=MetaMensalEntradaSerializer, responses={201: OpenApiTypes.OBJECT}, tags=["indicadores"])
    def post(self, request, *args, **kwargs):
        entrada = MetaMensalEntradaSerializer(data=request.data)
        if not entrada.is_valid():
            return _erro_400(entrada)
        dados = entrada.validated_data
        try:
            gravadas = metas.gravar(
                seguradora=dados["seguradora"].sigla,
                ramo=dados["ramo"].abreviatura,
                competencia=dados["competencia"],
                valor_meta=dados["valor_meta"],
                usuario=request.user,
                replicar_meses=dados["replicar_meses"],
            )
        except metas.ReferenciaDesconhecida as erro:
            return Response({"sucesso": False, "erro": str(erro)}, status=status.HTTP_400_BAD_REQUEST)
        except fedhub_lake.LakeIndisponivel as erro:
            return _lake_fora(erro)
        return Response({"sucesso": True, "metas": gravadas}, status=status.HTTP_201_CREATED)


class MetaDetalheView(_IndicadorBase):
    """`PUT`/`DELETE indicadores/metas/<id>/` — edita ou remove uma meta (RF-IEX-008)."""

    @extend_schema(
        request=MetaMensalEntradaSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        tags=["indicadores"],
    )
    def put(self, request, id, *args, **kwargs):
        """Edita esta meta (inclusive seguradora, ramo e mês) sem criar outra; `replicar_meses` é ignorado."""
        entrada = MetaMensalEntradaSerializer(data=request.data)
        if not entrada.is_valid():
            return _erro_400(entrada)
        dados = entrada.validated_data
        try:
            meta = metas.atualizar(
                meta_id=id,
                seguradora=dados["seguradora"].sigla,
                ramo=dados["ramo"].abreviatura,
                competencia=dados["competencia"],
                valor_meta=dados["valor_meta"],
                usuario=request.user,
            )
        except metas.MetaNaoEncontrada as erro:
            return Response({"sucesso": False, "erro": str(erro)}, status=status.HTTP_404_NOT_FOUND)
        except (metas.MetaDuplicada, metas.ReferenciaDesconhecida) as erro:
            return Response({"sucesso": False, "erro": str(erro)}, status=status.HTTP_400_BAD_REQUEST)
        except fedhub_lake.LakeIndisponivel as erro:
            return _lake_fora(erro)
        return Response({"sucesso": True, "metas": [meta]})

    @extend_schema(responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT}, tags=["indicadores"])
    def delete(self, request, id, *args, **kwargs):
        try:
            metas.apagar(id)
        except metas.MetaNaoEncontrada as erro:
            return Response({"sucesso": False, "erro": str(erro)}, status=status.HTTP_404_NOT_FOUND)
        except fedhub_lake.LakeIndisponivel as erro:
            return _lake_fora(erro)
        return Response({"sucesso": True})


class PainelTvView(_IndicadorBase):
    """Painel de TV: mês corrente × mesmo mês do ano anterior, por seguradora × ramo,
    com meta — lido pelo FedHub no Data Lake CORP e repassado sem recálculo.
    Não usa o espelho local: o lake é o dono desse número (ADR-0018 do pacote do lake)."""

    @extend_schema(
        summary="Painel de TV (lake via FedHub)",
        description="Linhas de `vw_painel_tv` do lake, repassadas. 503 com `erro` nomeado quando o FedHub ou o lake não respondem.",
        responses={200: OpenApiTypes.OBJECT, 503: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        try:
            linhas = painel_tv.linhas()
        except painel_tv.LakeIndisponivel as erro:
            return Response(
                {"sucesso": False, "erro": erro.erro, "detalhe": erro.detalhe},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except requests.RequestException as erro:
            return Response(
                {"sucesso": False, "erro": "fedhub_indisponivel", "detalhe": str(erro)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"sucesso": True, "gerado_em": timezone.now().isoformat(), "linhas": linhas})
