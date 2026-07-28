import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication # Apenas JWTCookieAuthentication
import requests
from urllib.parse import urlencode 
from django.conf import settings

from fedhub.services.administradoras_service import AdministradorasService

FASTAPI_BASE_URL = settings.WEBHOOK_URL

logger = logging.getLogger(__name__)
     
class buscarAdms(APIView):
    """
    View para buscar administradoras para autocomplete na API FastAPI.
    """

    def get(self, request, *args, **kwargs):
        # Extrai os parâmetros da requisição GET
        administradora = request.query_params.get('administradora', None)
        page_size = request.query_params.get('page_size', 5) # Valor padrão 5

        # Se nenhum termo de busca foi fornecido, retorna uma lista vazia
        if not administradora:
            return Response([], status=status.HTTP_200_OK)

        try:
            # Constrói os parâmetros para a requisição da API FastAPI
            fastapi_query_params = {
                "administradora": administradora,
                "page_size": page_size
            }
            
            
            fastapi_url = f"{FASTAPI_BASE_URL}/administradoras/?{urlencode(fastapi_query_params)}"

            # Faz a requisição GET para a API FastAPI
            response = requests.get(fastapi_url)

            # Lança uma exceção para códigos de status HTTP de erro (4xx ou 5xx)
            response.raise_for_status()

            # Retorna a resposta JSON da API FastAPI
            return Response(response.json(), status=status.HTTP_200_OK)

        except requests.exceptions.RequestException as e:
            # Lida com erros de comunicação com a API (ex: API offline, erro de rede)
            print(f"Erro de comunicação com a API FastAPI (buscarAdms): {e}")
            return Response(
                {"detail": f"Erro de comunicação com o servidor de busca de administradoras: {str(e)}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            # Lida com qualquer outro erro inesperado
            print(f"Erro inesperado na view buscarAdms: {e}")
            return Response(
                {"detail": "Ocorreu um erro interno ao buscar as administradoras."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
            
class BuscaPorAdms(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        service = AdministradorasService()
        
        logger.info(f"Parâmetros da requisição: {request.query_params}")

        filtros = {
            "administradora": request.query_params.get("administradora"),
        }

        # Remover filtros vazios
        filtros_limpos = {k: v for k, v in filtros.items() if v not in [None, "", "null"]}
        logger.info(f"Filtros limpos: {filtros_limpos}")

        try:
            dados = service.buscar_administradoras()
            logger.info(f"Dados retornados do Firebird: {dados}")

            if not dados:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Nenhuma fatura encontrada com os filtros informados",
                        "resultado": []
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            # Verificar estrutura dos dados retornados
            if isinstance(dados, dict):
                # Se for um dicionário, verificar se tem estrutura específica
                if "status" in dados and dados["status"] == "success":
                    resultado = dados.get("data", [])
                    
                    # Garantir que seja uma lista
                    if not isinstance(resultado, list):
                        resultado = [resultado] if resultado else []
                        
                    return Response(
                        {
                            "sucesso": True,
                            "resultado": {
                                "data": resultado,
                                "total": len(resultado)
                            }
                        },
                        status=status.HTTP_200_OK
                    )
                else:
                    # Retornar lista vazia
                    return Response(
                        {
                            "sucesso": True,
                            "resultado": {
                                "data": [],
                                "total": 0
                            }
                        },
                        status=status.HTTP_200_OK
                    )
            elif isinstance(dados, list):
                # Já é uma lista
                return Response(
                    {
                        "sucesso": True,
                        "resultado": {
                            "data": dados,
                            "total": len(dados)
                        }
                    },
                    status=status.HTTP_200_OK
                )
            else:
                # Converter qualquer outro tipo para lista
                return Response(
                    {
                        "sucesso": True,
                        "resultado": {
                            "data": [dados] if dados else [],
                            "total": 1 if dados else 0
                        }
                    },
                    status=status.HTTP_200_OK
                )

        except Exception as e:
            logger.error(f"Erro ao buscar fatura dinamicamente: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro interno ao processar consulta: {str(e)}",
                    "resultado": []
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class BuscarAdministradoras(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs): 
        service = AdministradorasService()
        dados = service.buscar_administradoras()
        
        # logger.info(f"Dados retornados do serviço de administradoras: {dados}")

        if not dados:
            return Response(
                {"sucesso": False, "erro": "Nenhuma administradora encontrada"},
                status=404
            )

        return Response({
            "sucesso": True,
            "data": dados
        })      

class BuscarAdministradorasPorNome(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, nome: str, *args, **kwargs):
        
        service = AdministradorasService()
        dados = service.buscar_administradora_por_nome(nome)

        if not dados:
            return Response(
                {"sucesso": False, "erro": "Administradora não encontrada"},
                status=404
            )

        return Response({
            "sucesso": True,
            "data": dados
        })

class BuscarAdministradorasPorCodigo(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, codigo: str, *args, **kwargs):
        service = AdministradorasService()
        dados = service.buscar_administradora_por_codigo(codigo)

        if not dados:
            return Response(
                {"sucesso": False, "erro": "Administradora não encontrada"},
                status=404
            )

        return Response({
            "sucesso": True,
            "data": dados
        })