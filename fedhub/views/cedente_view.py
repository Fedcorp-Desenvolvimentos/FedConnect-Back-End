import asyncio
import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

logger = logging.getLogger(__name__)

class BuscarCedentesView(APIView):
    """
    Busca todos os cedentes via FastAPI
    GET /cedentes/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            from fedhub.services.cedente_service import CedenteService
            service = CedenteService()
            
            # Busca todos os cedentes no FastAPI
            resultado = service.buscar_todos_cedentes()
            
            if not resultado:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Erro ao buscar cedentes"
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            # Verifica se o resultado tem a estrutura esperada
            if resultado.get("status") != "success":
                return Response(
                    {
                        "sucesso": False,
                        "erro": resultado.get("message", "Erro ao buscar cedentes")
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Retorna os dados dos cedentes
            return Response(
                {
                    "sucesso": True,
                    "data": resultado.get("data", []),
                    "total": resultado.get("total", 0)
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Erro ao buscar cedentes: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro interno: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class BuscarCedentePorNomeView(APIView):
    """
    Busca cedente por nome via FastAPI
    GET /cedentes/por-nome?nome=termo
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            nome = request.query_params.get("nome", "").strip()
            
            if not nome or len(nome) < 2:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Digite pelo menos 2 caracteres para buscar"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from fedhub.services.cedente_service import CedenteService
            service = CedenteService()
            
            resultado = service.buscar_cedente_por_nome(nome)
            
            if not resultado:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Erro ao buscar cedente"
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            if resultado.get("status") == "success":
                return Response(
                    {
                        "sucesso": True,
                        "data": resultado.get("data", []),
                        "total": resultado.get("total", 0)
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "sucesso": False,
                        "erro": resultado.get("message", "Erro ao buscar cedente")
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except Exception as e:
            logger.error(f"Erro ao buscar cedente por nome: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro interno: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )