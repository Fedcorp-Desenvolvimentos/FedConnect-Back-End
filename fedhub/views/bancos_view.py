import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from fedhub.services.bancos_service import BancosService
logger = logging.getLogger(__name__)

class BuscarBancosView(APIView):
    """
    Busca bancos
    GET /bancos/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            service = BancosService()
            
            limit = request.query_params.get("limit", 100)
            offset = request.query_params.get("offset", 0)
            search = request.query_params.get("search", "").strip()
            
            params = {
                "limit": int(limit),
                "offset": int(offset),
            }
            
            if search:
                params["search"] = search
            
            dados = service.buscar_bancos(params)
            
            if not dados:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar bancos"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            
            return Response(dados, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Erro em BuscarBancosView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class BuscarBancoPorCodigoView(APIView):
    """
    Busca banco por código
    GET /bancos/{codigo}/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, codigo, *args, **kwargs):
        try:
            service = BancosService()
            dados = service.buscar_banco_por_codigo(codigo)
            
            if not dados:
                return Response(
                    {"sucesso": False, "erro": "Banco não encontrado"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            return Response(
                {
                    "sucesso": True,
                    "data": dados,
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Erro em BuscarBancoPorCodigoView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class BuscarBancoPorNomeView(APIView):
    """
    Busca banco por nome
    GET /bancos/nome/{nome}/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, nome, *args, **kwargs):
        try:
            service = BancosService()
            dados = service.buscar_banco_por_nome(nome)
            
            if not dados:
                return Response(
                    {"sucesso": False, "erro": "Nenhum banco encontrado"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            return Response(
                {
                    "sucesso": True,
                    "data": dados,
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Erro em BuscarBancoPorNomeView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )