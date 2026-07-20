# fedhub/views/vistorias_view.py

import logging
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.http import HttpResponse

from fedhub.services.vistorias_service import VistoriasService

logger = logging.getLogger(__name__)


class ListarEstadosVistoria(APIView):
    """Lista estados das vistorias"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        service = VistoriasService()
        dados = service.listar_estados()

        if not dados:
            return Response(
                {"sucesso": False, "erro": "Erro ao listar estados"},
                status=400
            )

        return Response({
            "sucesso": True,
            "data": dados.get("data", []),
            "total": dados.get("total", 0)
        })


class ListarVistoriadores(APIView):
    """Lista vistoriadores ativos"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        service = VistoriasService()
        dados = service.listar_vistoriadores()

        if not dados:
            return Response(
                {"sucesso": False, "erro": "Erro ao listar vistoriadores"},
                status=400
            )

        return Response({
            "sucesso": True,
            "data": dados.get("data", []),
            "total": dados.get("total", 0)
        })


class ListarAdministradorasVistoria(APIView):
    """Lista administradoras (pessoas ativas)"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        service = VistoriasService()
        dados = service.listar_administradoras()

        if not dados:
            return Response(
                {"sucesso": False, "erro": "Erro ao listar administradoras"},
                status=400
            )

        return Response({
            "sucesso": True,
            "data": dados.get("data", []),
            "total": dados.get("total", 0)
        })


class ConsultarVistorias(APIView):
    """Consulta vistorias com filtros"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Parâmetros de filtro
        params = {
            "dt_inicio": request.query_params.get("dt_inicio"),
            "dt_fim": request.query_params.get("dt_fim"),
            "estado": request.query_params.get("estado"),
            "administradora": request.query_params.get("administradora"),
            "cod_vistoriador": request.query_params.get("cod_vistoriador"),
            "fatura": request.query_params.get("fatura"),
            "limit": request.query_params.get("limit", 5000),
            "offset": request.query_params.get("offset", 0),
        }

        service = VistoriasService()
        dados = service.consultar_vistorias(params)

        if not dados:
            return Response(
                {"sucesso": False, "erro": "Erro ao consultar vistorias"},
                status=400
            )

        return Response({
            "sucesso": True,
            "data": dados.get("data", []),
            "total": len(dados.get("data", [])),
            "total_registros": dados.get("total_registros", 0),
            "has_more": dados.get("has_more", False)
        })


class ExportarVistoriasExcel(APIView):
    """Exporta vistorias para Excel"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Parâmetros de filtro
        params = {
            "dt_inicio": request.query_params.get("dt_inicio"),
            "dt_fim": request.query_params.get("dt_fim"),
            "estado": request.query_params.get("estado"),
            "administradora": request.query_params.get("administradora"),
            "cod_vistoriador": request.query_params.get("cod_vistoriador"),
            "fatura": request.query_params.get("fatura"),
        }

        service = VistoriasService()
        resultado = service.exportar_excel(params)

        if not resultado or resultado.get("status") != "success":
            return Response(
                {"sucesso": False, "erro": "Erro ao exportar Excel"},
                status=400
            )

        # Retorna o arquivo como download
        response = HttpResponse(
            resultado.get("content"),
            content_type=resultado.get("content_type", "application/vnd.ms-excel")
        )
        response["Content-Disposition"] = f'attachment; filename="{resultado.get("filename")}"'
        response["X-Filename"] = resultado.get("filename")

        return response


class ExportarVistoriasPDF(APIView):
    """Exporta vistorias para PDF"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Parâmetros de filtro
        params = {
            "dt_inicio": request.query_params.get("dt_inicio"),
            "dt_fim": request.query_params.get("dt_fim"),
            "estado": request.query_params.get("estado"),
            "administradora": request.query_params.get("administradora"),
            "cod_vistoriador": request.query_params.get("cod_vistoriador"),
            "fatura": request.query_params.get("fatura"),
        }

        service = VistoriasService()
        resultado = service.exportar_pdf(params)

        if not resultado or resultado.get("status") != "success":
            return Response(
                {"sucesso": False, "erro": "Erro ao exportar PDF"},
                status=400
            )

        # Retorna o arquivo como download
        response = HttpResponse(
            resultado.get("content"),
            content_type=resultado.get("content_type", "application/pdf")
        )
        response["Content-Disposition"] = f'attachment; filename="{resultado.get("filename")}"'
        response["X-Filename"] = resultado.get("filename")

        return response
