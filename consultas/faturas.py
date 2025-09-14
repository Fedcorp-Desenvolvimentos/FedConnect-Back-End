# Seu novo arquivo: faturas.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
import requests
import json
from urllib.parse import urlencode 
from .serializers import ConsultaRequestSerializer, HistoricoConsultaSerializer # Você precisará de um novo serializer
from .models import HistoricoConsulta
from django.conf import settings

# A URL base do seu FastAPI já está definida em settings
FASTAPI_BASE_URL = settings.WEBHOOK_URL

class RealizarConsultaFaturasView(APIView):
    """
    View para realizar consultas de faturas através de um backend FastAPI.
    Autentica o usuário, formata os parâmetros e salva o histórico da consulta.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # A validação dos dados de entrada
        serializer = ConsultaRequestSerializer(data=request.data)
        if serializer.is_valid():
            parametro_consulta_raw = serializer.validated_data["parametro_consulta"]
            origem = serializer.validated_data.get('origem', 'manual')
            lote_id = serializer.validated_data.get('lote_id', None)

            try:
                # O front-end envia um JSON como string, então precisamos converter para dict
                parametro_consulta_dict = json.loads(parametro_consulta_raw)
                print(f"DEBUG: parametro_consulta_dict (após json.loads): {parametro_consulta_dict}")
            except json.JSONDecodeError as e:
                return Response(
                    {"detail": f"Erro ao decodificar parametro_consulta: {e}. Certifique-se de que é um JSON válido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # O URL do FastAPI para faturas
            fastapi_base_endpoint = f"{FASTAPI_BASE_URL}faturas/"
            
            # Constrói a query string com os parâmetros do dicionário
            cleaned_fastapi_query_params = {
                key: value for key, value in parametro_consulta_dict.items()
                if value is not None and value != "" 
            }
            query_string = urlencode(cleaned_fastapi_query_params)
            
            fastapi_url = f"{fastapi_base_endpoint}?{query_string}"

            print(f"DEBUG: Chamando FastAPI URL (GET): {fastapi_url}")

            try:
                # Faz a requisição GET para a API FastAPI
                response = requests.get(fastapi_url)
                response.raise_for_status()
                resultado_api = response.json()

                # Salva o histórico da consulta
                historico = HistoricoConsulta.objects.create(
                    usuario=request.user,
                    tipo_consulta="faturas", # O tipo de consulta agora é "faturas"
                    parametro_consulta=json.dumps(parametro_consulta_dict),
                    resultado=resultado_api, 
                    origem=origem,
                    lote_id=lote_id
                )
                historico_serializer = HistoricoConsultaSerializer(historico)

                return Response(
                    {
                        "mensagem": "Consulta de faturas realizada com sucesso.",
                        "resultado_api": resultado_api,
                        "historico_salvo": historico_serializer.data,
                        "origem": origem
                    },
                    status=status.HTTP_200_OK,
                )

            except requests.exceptions.RequestException as e:
                print(f"Erro de comunicação com a API de faturas (FastAPI GET): {e}")
                error_message_from_fastapi = f"Erro de comunicação com a API de faturas: {str(e)}"
                if e.response is not None:
                    try:
                        error_details = e.response.json()
                        error_message_from_fastapi = error_details.get("detail", error_message_from_fastapi)
                    except json.JSONDecodeError:
                        error_message_from_fastapi = f"Erro de comunicação com a API de faturas. Resposta não JSON: {e.response.text}"
                
                return Response(
                    {"detail": error_message_from_fastapi},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE, 
                )
            except Exception as e:
                print(f"Erro inesperado na RealizarConsultaFaturasView: {e}")
                return Response(
                    {"detail": f"Erro interno ao processar consulta de faturas: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)