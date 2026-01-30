import logging
from consultas.services.firebird_service import FirebirdService
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication # Apenas JWTCookieAuthentication
import requests
import json
from urllib.parse import urlencode 
from .serializers import ConsultaRequestSerializer, HistoricoConsultaSerializer
from .models import HistoricoConsulta
from django.conf import settings

FASTAPI_BASE_URL = settings.WEBHOOK_URL

logger = logging.getLogger(__name__)

class RealizarConsultaSeguradosView(APIView):
    """
    View para realizar consultas de segurados (Vida e Incêndio)
    através de um backend FastAPI.
    Autentica o usuário, formata os parâmetros e salva o histórico da consulta.
    Inclui paginação.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ConsultaRequestSerializer(data=request.data)

        if serializer.is_valid():
            tipo_consulta = serializer.validated_data["tipo_consulta"]
            
            # --- MUDANÇA AQUI: Converter a string JSON para um dicionário Python ---
            parametro_consulta_raw_json_string = serializer.validated_data["parametro_consulta"]
            try:
                # O problema era que parametro_consulta era uma string JSON, não um dict
                parametro_consulta_dict_from_frontend = json.loads(parametro_consulta_raw_json_string)
                print(f"DEBUG: parametro_consulta_dict_from_frontend (após json.loads): {parametro_consulta_dict_from_frontend}")
            except json.JSONDecodeError as e:
                return Response(
                    {"detail": f"Erro ao decodificar parametro_consulta: {e}. Certifique-se de que é um JSON válido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # --- FIM DA MUDANÇA ---

            origem = serializer.validated_data.get('origem', 'manual')
            lote_id = serializer.validated_data.get('lote_id', None)

            resultado_api = None
            
            # Este já está correto, pois 'parametro_consulta_dict_from_frontend' agora é um dict
            # e será serializado para string JSON para o histórico
            parametro_consulta_para_historico = json.dumps(parametro_consulta_dict_from_frontend)

            if tipo_consulta not in ["vida", "incendio"]:
                return Response(
                    {"detail": "Tipo de consulta não suportado por esta view. Use 'vida' ou 'incendio'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                page = serializer.validated_data.get('page', 1)
                page_size = serializer.validated_data.get('page_size', 50)

                # --- Agora, 'parametro_consulta_dict_from_frontend' é definitivamente um dicionário ---
                fastapi_query_params_to_send = {
                    **parametro_consulta_dict_from_frontend, # Isso agora funciona!
                    "page": page,
                    "page_size": page_size,
                }

                cleaned_fastapi_query_params = {
                    key: value for key, value in fastapi_query_params_to_send.items()
                    if value is not None and value != "" 
                }

                query_string = urlencode(cleaned_fastapi_query_params)
                
                fastapi_base_endpoint = ""
                if tipo_consulta == "vida":
                    fastapi_base_endpoint = f"{FASTAPI_BASE_URL}vida/" 
                elif tipo_consulta == "incendio":
                    fastapi_base_endpoint = f"{FASTAPI_BASE_URL}incendio/"

                fastapi_url = f"{fastapi_base_endpoint}?{query_string}"

                print(f"DEBUG: Chamando FastAPI URL (GET): {fastapi_url}") 

                response = requests.get(fastapi_url)
                response.raise_for_status() 
                resultado_api = response.json()

                historico = HistoricoConsulta.objects.create(
                    usuario=request.user,
                    tipo_consulta=tipo_consulta,
                    parametro_consulta=parametro_consulta_para_historico,
                    resultado=resultado_api, 
                    origem=origem,
                    lote_id=lote_id
                )

                historico_serializer = HistoricoConsultaSerializer(historico)

                return Response(
                    {
                        "mensagem": "Consulta realizada com sucesso.",
                        "resultado_api": resultado_api,
                        "historico_salvo": historico_serializer.data,
                        "origem": origem
                    },
                    status=status.HTTP_200_OK,
                )

            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except requests.exceptions.RequestException as e:
                print(f"Erro de comunicação com a API de segurados (FastAPI GET): {e}")
                
                error_message_from_fastapi = f"Erro de comunicação com a API de segurados: {str(e)}"
                if e.response is not None:
                    try:
                        error_details = e.response.json()
                        error_message_from_fastapi = error_details.get("detail", error_message_from_fastapi)
                    except json.JSONDecodeError:
                        error_message_from_fastapi = f"Erro de comunicação com a API de segurados. Resposta não JSON: {e.response.text}"
                
                return Response(
                    {"detail": error_message_from_fastapi},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE, 
                )
            except Exception as e:
                print(f"Erro inesperado na RealizarConsultaSeguradosView: {e}")
                return Response(
                    {"detail": f"Erro interno ao processar consulta: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
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
        service = FirebirdService()
        
        logger.info(f"Parâmetros da requisição: {request.query_params}")

        filtros = {
            "fatura": request.query_params.get("fatura"),
        }

        # Remover filtros vazios
        filtros_limpos = {k: v for k, v in filtros.items() if v not in [None, "", "null"]}
        logger.info(f"Filtros limpos: {filtros_limpos}")

        try:
            dados = service.buscar_seguradoras(filtros_limpos)
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