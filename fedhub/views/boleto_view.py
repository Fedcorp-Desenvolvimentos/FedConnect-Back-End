import asyncio
import logging
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
import requests
import json

from consultas.cache.cidade_cache import buscar_cidades_autocomplete_sync
from consultas.services.analytics_service import AnalyticsService
from consultas.services.fedhub_service import FedhubService
from consultas.utils.renderers import BinaryRenderer
from .serializers import ConsultaRequestSerializer, HistoricoConsultaSerializer
from .models import HistoricoConsulta
from .integrations import ConsultaCEP, ConsultaCPF, ConsultaCNPJ
from django.contrib.auth import get_user_model
from rest_framework.pagination import PageNumberPagination

import pandas as pd
from io import BytesIO
from django.http import HttpResponse
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

from rest_framework.parsers import MultiPartParser, FormParser

from django.utils.dateparse import parse_date
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

class BuscarFaturasComissoesView(APIView):
    """
    Busca faturas para emissão de recibos de comissões
    GET /comissoes/faturas/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            service = FedhubService()
            params = {
                "favorecido": request.query_params.get("favorecido"),
                "fatura": request.query_params.get("fatura"),
                "vencimento_inicial": request.query_params.get("vencimento_inicial"),
                "vencimento_final": request.query_params.get("vencimento_final"),
                "status": request.query_params.get("status"),
                "tipo": request.query_params.get("tipo"),
                "co_estipulante": request.query_params.get("co_estipulante"),
                "apolice": request.query_params.get("apolice"),
                "comercial": request.query_params.get("comercial"),
                "recibo": request.query_params.get("recibo"),
                "vigencia_inicial": request.query_params.get("vigencia_inicial"),
                "vigencia_final": request.query_params.get("vigencia_final"),
                "limit": request.query_params.get("limit", 100),
                "offset": request.query_params.get("offset", 0),
            }
            dados = service.buscar_faturas_comissoes(params)
            if not dados:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar faturas de comissão"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(dados, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Erro em BuscarFaturasComissoesView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class BuscarComissoesPorFaturaView(APIView):
    """
    Busca comissões individuais de uma fatura
    GET /comissoes/faturas/{numero_fatura}/comissoes/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, numero_fatura, *args, **kwargs):
        try:
            service = FedhubService()
            dados = service.buscar_comissoes_por_fatura(numero_fatura)
            if not dados:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar comissões"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(dados, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Erro em BuscarComissoesPorFaturaView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class EmitirVoucherView(APIView):
    """
    Emite voucher/recibo de comissão
    POST /comissoes/emitir/
    Payload: {fatura, parcela, tipo_fat, tipo_documento}
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            fatura = request.data.get("fatura")
            parcela = request.data.get("parcela", 1)
            tipo_fat = request.data.get("tipo_fat", "F")
            tipo_documento = request.data.get("tipo_documento", "recibo")

            if not fatura:
                return Response(
                    {"sucesso": False, "erro": "Número da fatura é obrigatório"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            service = FedhubService()
            payload = {
                "fatura": fatura,
                "parcela": parcela,
                "tipo_fat": tipo_fat,
            }
            resultado = service.emitir_voucher(payload)

            if not resultado or resultado.get("status") != "success":
                return Response(
                    {
                        "sucesso": False,
                        "erro": resultado.get("detail", "Erro ao emitir documento") if resultado else "Erro de comunicação",
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            return Response(
                {
                    "sucesso": True,
                    "data": {
                        "id": resultado.get("numero_guia"),
                        "numero": resultado.get("numero_guia"),
                        "emitidoEm": resultado.get("data_emissao"),
                        "fatura": fatura,
                        "tipoDocumento": tipo_documento,
                    },
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Erro em EmitirVoucherView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class BuscarPessoasView(APIView):
    """
    Busca pessoas (favorecidos)
    GET /pessoas/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            service = FedhubService()
            limit = request.query_params.get("limit")
            params = {
                "status": request.query_params.get("status", "A"),
                "limit": limit if limit else 7000,
                "offset": request.query_params.get("offset", 0),
            }
            dados = service.buscar_pessoas(params)
            if not dados:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar pessoas"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(dados, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Erro em BuscarPessoasView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class RealizarConsultaView(APIView):

    authentication_classes = [JWTAuthentication]

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Instancia o serializer com os dados da requisição.
        # O ConsultaRequestSerializer é responsável por validar e processar
        # os dados de entrada, incluindo a conversão de JSON strings para dicionários Python
        # para tipos de consulta como 'cpf_alternativa', 'cnpj_razao_social' e 'cep_rua_cidade'.
        serializer = ConsultaRequestSerializer(data=request.data)

        # Valida os dados da requisição. Se houver erros, retorna 400 Bad Request.
        if serializer.is_valid():
            # Extrai os dados validados do serializer.
            tipo_consulta = serializer.validated_data["tipo_consulta"]
            # 'parametro_consulta_processed' será uma string (CPF, CNPJ, CEP)
            # ou um dicionário Python (para consultas alternativas com JSON).
            parametro_consulta_processed = serializer.validated_data[
                "parametro_consulta"
            ]

            # Campos opcionais com valores padrão.
            origem = serializer.validated_data.get("origem", "manual")
            lote_id = serializer.validated_data.get("lote_id", None)

            resultado_api = (
                None  # Variável para armazenar o resultado retornado pela API externa.
            )
            parametro_consulta_para_historico = ""  # Variável para o valor a ser salvo no campo `parametro_consulta` do modelo HistoricoConsulta.

            try:
                # Lógica condicional para chamar a função de integração correta
                # baseada no 'tipo_consulta' e processar o 'parametro_consulta_processed'.

                if tipo_consulta == "endereco":  # Consulta de CEP simples (BrasilAPI)
                    parametro_consulta_para_historico = (
                        parametro_consulta_processed  # Já é o CEP limpo
                    )
                    resultado_api = ConsultaCEP.consultar(parametro_consulta_processed)

                elif tipo_consulta == "cpf":  # Consulta de CPF simples (BigDataCorp)
                    parametro_consulta_para_historico = (
                        parametro_consulta_processed  # Já é o CPF limpo
                    )
                    resultado_api = ConsultaCPF.consultar(parametro_consulta_processed)

                elif tipo_consulta == "cnpj":  # Consulta de CNPJ simples (BrasilAPI)
                    parametro_consulta_para_historico = (
                        parametro_consulta_processed  # Já é o CNPJ limpo
                    )
                    resultado_api = ConsultaCNPJ.consultar(parametro_consulta_processed)

                elif (
                    tipo_consulta == "cpf_alternativa"
                ):  # Consulta de CPF por chaves alternativas (BigDataCorp)
                    # Para salvar no histórico, o dicionário precisa ser convertido de volta para JSON string.
                    parametro_consulta_para_historico = json.dumps(
                        parametro_consulta_processed
                    )
                    # Passa o dicionário Python para a função de integração.
                    resultado_api = ConsultaCPF.consultar_cpf_alternativa(
                        parametro_consulta_processed
                    )

                elif (
                    tipo_consulta == "cnpj_razao_social"
                ):  # Consulta de CNPJ por Razão Social/Nome (BigDataCorp)
                    # Para salvar no histórico, o dicionário precisa ser convertido de volta para JSON string.
                    parametro_consulta_para_historico = json.dumps(
                        parametro_consulta_processed
                    )
                    # Passa o dicionário Python para a função de integração.
                    resultado_api = ConsultaCNPJ.consultar_por_razao_social_bigdatacorp(
                        parametro_consulta_processed
                    )

                elif (
                    tipo_consulta == "cep_rua_cidade"
                ):  # Consulta de CEP por Rua e Cidade (ViaCEP)
                    # Para salvar no histórico, o dicionário precisa ser convertido de volta para JSON string.
                    parametro_consulta_para_historico = json.dumps(
                        parametro_consulta_processed
                    )
                    # Passa o dicionário Python (contendo 'estado', 'cidade', 'logradouro') para a função de integração.
                    resultado_api = ConsultaCEP.consultar_por_rua_e_cidade(
                        parametro_consulta_processed
                    )

                else:
                    # Caso um 'tipo_consulta' inválido passe pela validação (o que não deveria ocorrer com ChoiceField)
                    return Response(
                        {"detail": "Tipo de consulta inválido."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Salva o histórico da consulta no banco de dados.
                historico = HistoricoConsulta.objects.create(
                    usuario=request.user,  # O usuário logado que realizou a consulta.
                    tipo_consulta=tipo_consulta,
                    parametro_consulta=parametro_consulta_para_historico,  # O valor (string ou JSON string) a ser salvo.
                    resultado=resultado_api,  # O resultado JSON completo da API externa.
                    origem=origem,
                    lote_id=lote_id,
                )

                # Serializa o objeto de histórico salvo para a resposta da API.
                historico_serializer = HistoricoConsultaSerializer(historico)

                # Retorna uma resposta de sucesso com os detalhes da consulta e o histórico salvo.
                return Response(
                    {
                        "mensagem": "Consulta realizada com sucesso.",
                        "resultado_api": resultado_api,
                        "historico_salvo": historico_serializer.data,
                        "origem": origem,  # Inclui a origem na resposta
                    },
                    status=status.HTTP_200_OK,
                )

            except ValueError as e:
                # Captura erros de validação de negócio ou erros específicos da camada de integração.
                # Ex: "CEP não encontrado.", "CPF inválido."
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except requests.exceptions.RequestException as e:
                # Captura erros de comunicação com APIs externas (problemas de rede, timeouts, etc.).
                return Response(
                    {"detail": f"Erro de comunicação com a API externa: {str(e)}"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,  # Service Unavailable indica que o serviço externo está indisponível
                )
            except Exception as e:
                # Captura qualquer outro erro inesperado que possa ocorrer.
                # É crucial logar esses erros para depuração em produção.
                print(f"Erro inesperado na RealizarConsultaView: {e}")
                return Response(
                    {"detail": f"Erro interno ao processar consulta: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,  # Internal Server Error para erros não previstos.
                )

        # Se o serializer não for válido (erros de validação de entrada).
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# --- View para Listar o Histórico de Consultas ---
class StandardResultsPagination(PageNumberPagination):
    page_size = 10  # Deve ser o mesmo que intensPorPagina no frontend
    page_size_query_param = "page_size"
    max_page_size = 100
class HistoricoConsultaListView(generics.ListAPIView):

    serializer_class = HistoricoConsultaSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):

        user = self.request.user
        if user.is_authenticated:
            # Admins podem ver todo o histórico.
            if hasattr(user, "nivel_acesso") and user.nivel_acesso == "admin":
                return HistoricoConsulta.objects.all().order_by("-data_consulta")
            else:
                # Usuários comuns veem apenas seu próprio histórico.
                return HistoricoConsulta.objects.filter(usuario=user).order_by(
                    "-data_consulta"
                )
        return (
            HistoricoConsulta.objects.none()
        )  # Retorna queryset vazia se não autenticado.

# --- View para Detalhes de uma Consulta Específica no Histórico ---
class HistoricoConsultaDetailView(generics.RetrieveAPIView):
    queryset = HistoricoConsulta.objects.all()
    serializer_class = HistoricoConsultaSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self):
        queryset = self.get_queryset()
        # Tenta obter o objeto pelo PK (ID) fornecido na URL.
        obj = generics.get_object_or_404(queryset, pk=self.kwargs["pk"])

        user = self.request.user
        # Admins podem ver qualquer consulta.
        if hasattr(user, "nivel_acesso") and user.nivel_acesso == "admin":
            return obj
        # Usuários comuns só podem ver suas próprias consultas.
        elif obj.usuario == user:
            return obj
        else:
            # Se o usuário não tem permissão para acessar a consulta.
            self.permission_denied(
                self.request,
                message="Você não tem permissão para acessar esta consulta.",
            )
class BuscarTodasEmpresas(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            service = FedhubService()
            dados = asyncio.run(service.buscar_todas_empresas())
            
            # logger.info(
            #     "DADOS DA REQUISIÇÃO:\n%s",
            #     json.dumps(dados, indent=2, ensure_ascii=False)
            # )
            
            if not dados:
                return Response({
                    "status": "not_found",
                    "message": "Empresa não encontrada",
                    "timestamp": datetime.now().isoformat()
                }, status=status.HTTP_404_NOT_FOUND)
                            
            return Response({
                "status": "success",
                "total_returned": len(dados),
                "data": dados,
                "timestamp": datetime.now().isoformat()
            })

            
        except Exception as e:
            logger.error(f"Erro ao buscar empresas: {str(e)}")
            return Response({"detail": str(e)}, status=500)
                
# --- View para Listar o Histórico de Consultas de um Usuário Específico (Geralmente para Admins) ---
class HistoricoConsultaUserListView(generics.ListAPIView):
    serializer_class = HistoricoConsultaSerializer
    authentication_classes = [JWTAuthentication, JWTAuthentication]
    permission_classes = [
        IsAuthenticated
    ]  # Adicionado IsOwnerOrAdmin para restringir acesso

    def get_queryset(self):
        # Apenas admins devem ter acesso a esta view para buscar histórico de outros usuários.
        # A permissão 'IsOwnerOrAdmin' deve lidar com isso.

        user_id = self.kwargs["user_id"]  # Obtém o ID do usuário da URL.
        User = get_user_model()  # Obtém o modelo de usuário customizado.

        try:
            target_user = User.objects.get(
                pk=user_id
            )  # Tenta encontrar o usuário pelo ID.
        except User.DoesNotExist:
            return (
                HistoricoConsulta.objects.none()
            )  # Retorna vazio se o usuário não existir.

        # Retorna o histórico de consultas para o usuário alvo.
        return HistoricoConsulta.objects.filter(usuario=target_user).order_by(
            "-data_consulta"
        )

# Buscar Fatura por Numero da Fatura
class BuscarFaturaPorNumero(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, numero_fatura: str, *args, **kwargs):
        service = FedhubService()
        dados = service.buscar_fatura_por_numero(numero_fatura)

        if not dados:
            return Response(
                {"sucesso": False, "erro": "Fatura não encontrada"},
                status=404
            )

        return Response({
            "sucesso": True,
            "data": dados
        })

# Buscar Fatura por parametros - QUERY APENAS NA TABELA 'FATURAS'
class BuscarFaturaDinamicamente(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        service = FedhubService()
        
        logger.info(f"Parâmetros da requisição: {request.query_params}")

        filtros = {
            "fatura": request.query_params.get("fatura"),
            "apolice": request.query_params.get("apolice"),
            "administradora": request.query_params.get("administradora"),
            "seguradora": request.query_params.get("seguradora"),
            "status": request.query_params.get("status"),
            "ramo": request.query_params.get("ramo"),
            "data_ini": request.query_params.get("data_ini"),
            "data_fim": request.query_params.get("data_fim"),
            "valor_min": request.query_params.get("valor_min"),
            "valor_max": request.query_params.get("valor_max"),
            "limit": request.query_params.get("limit", 100),
            "offset": request.query_params.get("offset", 0),
        }

        # Remover filtros vazios
        filtros_limpos = {k: v for k, v in filtros.items() if v not in [None, "", "null"]}
        logger.info(f"Filtros limpos: {filtros_limpos}")

        try:
            dados = service.buscar_fatura_dinamicamente(filtros_limpos)
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
class BuscarFaturasDinamicamentePaginadas(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        service = FedhubService()
        
        logger.info(f"Parâmetros da requisição faturas dinâmicas paginadas: {request.query_params}")

        # Coletar todos os parâmetros da rota paginada
        filtros = {
            "fatura": request.query_params.get("fatura"),
            "apolice": request.query_params.get("apolice"),
            "administradora": request.query_params.get("administradora"),
            "seguradora": request.query_params.get("seguradora"),
            "status": request.query_params.get("status"),
            "ramo": request.query_params.get("ramo"),
            "data_ini": request.query_params.get("data_ini"),
            "data_fim": request.query_params.get("data_fim"),
            "valor_min": request.query_params.get("valor_min"),
            "valor_max": request.query_params.get("valor_max"),
            "pagina": request.query_params.get("pagina", 1),
            "por_pagina": request.query_params.get("por_pagina", 50),
        }

        # Remover filtros vazios
        filtros_limpos = {k: v for k, v in filtros.items() if v not in [None, "", "null"]}
        
        # Converter tipos numéricos
        try:
            if filtros_limpos.get('fatura'):
                filtros_limpos['fatura'] = int(filtros_limpos['fatura'])
            if filtros_limpos.get('pagina'):
                filtros_limpos['pagina'] = int(filtros_limpos['pagina'])
            if filtros_limpos.get('por_pagina'):
                filtros_limpos['por_pagina'] = int(filtros_limpos['por_pagina'])
            if filtros_limpos.get('valor_min'):
                filtros_limpos['valor_min'] = float(filtros_limpos['valor_min'])
            if filtros_limpos.get('valor_max'):
                filtros_limpos['valor_max'] = float(filtros_limpos['valor_max'])
        except ValueError as e:
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro na conversão de parâmetros numéricos: {str(e)}"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(f"Filtros limpos para faturas dinâmicas paginadas: {filtros_limpos}")

        try:
            # Chamar serviço paginado
            dados = service.buscar_faturas_dinamicamente_paginadas(filtros_limpos)
            
            if not dados or dados.get("status") != "success":
                return Response(
                    {
                        "sucesso": False,
                        "erro": dados.get("message", "Nenhum resultado encontrado"),
                        "resultado": []
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            # Extrair dados da resposta
            data_list = dados.get("data", [])
            total_registros = dados.get("total_registros", 0)
            pagina_atual = dados.get("pagina_atual", 1)
            por_pagina = dados.get("por_pagina", 50)
            total_paginas = dados.get("total_paginas", 1)

            return Response(
                {
                    "sucesso": True,
                    "resultado": {
                        "data": data_list,
                        "pagination": {
                            "current_page": pagina_atual,
                            "page_size": por_pagina,
                            "total_records": total_registros,
                            "total_pages": total_paginas,
                            "has_next": pagina_atual < total_paginas,
                            "has_previous": pagina_atual > 1,
                            "next_page": pagina_atual + 1 if pagina_atual < total_paginas else None,
                            "previous_page": pagina_atual - 1 if pagina_atual > 1 else None
                        },
                        "filters": dados.get("filters", {}),
                        "total_registros": total_registros
                    }
                },
                status=status.HTTP_200_OK
            )

        except requests.RequestException as e:
            logger.error(f"Erro de comunicação ao buscar faturas dinâmicas paginadas: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro de comunicação com o serviço de faturas: {str(e)}",
                    "resultado": []
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar faturas dinâmicas paginadas: {str(e)}")
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
        service = FedhubService()
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
        
        service = FedhubService()
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
        service = FedhubService()
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

# *******************************************#
#********** Consultas Firebird ********#
# *******************************************# 
class BuscarFaturasComBoletos(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        service = FedhubService()
        
        logger.info(f"Parâmetros da requisição de faturas com boletos: {request.query_params}")

        # Coletar todos os parâmetros possíveis
        filtros = {
            "fatura": request.query_params.get("fatura"),
            "apolice": request.query_params.get("apolice"),
            "administradora": request.query_params.get("administradora"),
            "status": request.query_params.get("status"),
            "data_ini": request.query_params.get("data_ini"),
            "data_fim": request.query_params.get("data_fim"),
            
            "page": request.query_params.get("page", 1),
            "page_size": request.query_params.get("page_size", 10),
            
            "limit": request.query_params.get("limit", 500),
            "offset": request.query_params.get("offset", 0),
        }

        # Remover filtros vazios
        filtros_limpos = {k: v for k, v in filtros.items() if v not in [None, "", "null"]}
        logger.info(f"Filtros limpos para faturas com boletos: {filtros_limpos}")

        try:
            # Calcular offset baseado na página (para compatibilidade)
            page = int(filtros_limpos.get('page', 1))
            page_size = int(filtros_limpos.get('page_size', 10))
            offset = (page - 1) * page_size
            
            # Atualizar filtros com offset calculado
            filtros_limpos['limit'] = page_size
            filtros_limpos['offset'] = offset
            
            # Remover parâmetros de paginação do serviço (se não for compatível)
            filtros_para_servico = filtros_limpos.copy()
            
            dados = service.buscar_faturas_com_boletos(filtros_para_servico)
            logger.info(f"Dados retornados do serviço de faturas com boletos: {dados}")

            if dados.get("status") != "success":
                return Response(
                    {
                        "sucesso": False,
                        "erro": dados.get("message", "Erro ao buscar faturas"),
                        "resultado": []
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
            # Extrair dados importantes
            data_list = dados.get("data", [])
            total_registros = dados.get("total_registros", 0)
            
            # Calcular informações de paginação
            total_pages = max(1, (total_registros + page_size - 1) // page_size) 
            current_page = page

            return Response(
                {
                    "sucesso": True,
                    "resultado": {
                        "data": data_list,
                        "pagination": {
                            "current_page": current_page,
                            "page_size": page_size,
                            "total_records": total_registros,
                            "total_pages": total_pages,
                            "has_next": current_page < total_pages,
                            "has_previous": current_page > 1,
                            "next_page": current_page + 1 if current_page < total_pages else None,
                            "previous_page": current_page - 1 if current_page > 1 else None,
                            "offset": offset,
                            "limit": page_size
                        },
                        "filters": dados.get("filters", {}),
                        "total_registros": total_registros  
                    }
                },
                status=status.HTTP_200_OK
            )

        except requests.RequestException as e:
            logger.error(f"Erro de comunicação ao buscar faturas com boletos: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro de comunicação com o serviço de faturas: {str(e)}",
                    "resultado": []
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar faturas com boletos: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro interno ao processar consulta: {str(e)}",
                    "resultado": []
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )      
class BuscarFaturamento(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        service = FedhubService()
        
        logger.info(f"Parâmetros da requisição de faturamento: {request.query_params}")

        # Coletar todos os parâmetros possíveis
        filtros = {
            "fatura": request.query_params.get("fatura"),
            "apolice": request.query_params.get("apolice"),
            "administradora": request.query_params.get("administradora"),
            "status": request.query_params.get("status"),
            "data_ini": request.query_params.get("data_ini"),
            "data_fim": request.query_params.get("data_fim"),
            "page": request.query_params.get("page", 1),
            "page_size": request.query_params.get("page_size", 10),
        }

        # Remover filtros vazios
        filtros_limpos = {k: v for k, v in filtros.items() if v not in [None, "", "null"]}
        logger.info(f"Filtros limpos para faturamento: {filtros_limpos}")

        try:
            # Chamar o serviço que consulta o FedHub
            dados = service.buscar_faturamento(filtros_limpos)
            
            # logger.info(
            # "Dados retornados do serviço de faturamento:\n%s",
            # json.dumps(
            #         dados.json() if hasattr(dados, "json") else dados,
            #         indent=4,
            #         ensure_ascii=False,
            #         default=str
            #     )
            # )
            
            if not dados:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Erro ao consultar serviço de faturas",
                        "resultado": {
                            "data": [],
                            "pagination": {
                                "current_page": int(filtros_limpos.get('page', 1)),
                                "page_size": int(filtros_limpos.get('page_size', 10)),
                                "total_records": 0,
                                "total_pages": 1,
                                "has_next": False,
                                "has_previous": False
                            }
                        }
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            if dados.get("status") != "success":
                return Response(
                    {
                        "sucesso": False,
                        "erro": dados.get("message", "Erro ao buscar faturas"),
                        "resultado": {
                            "data": [],
                            "pagination": {
                                "current_page": int(filtros_limpos.get('page', 1)),
                                "page_size": int(filtros_limpos.get('page_size', 10)),
                                "total_records": 0,
                                "total_pages": 1,
                                "has_next": False,
                                "has_previous": False
                            }
                        }
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Extrair dados da resposta do FedHub
            data_list = dados.get("data", [])
            total_registros = dados.get("total_registros", 0)
            pagina_atual = dados.get("pagina_atual", int(filtros_limpos.get('page', 1)))
            total_paginas = dados.get("total_paginas", 1)
            tem_proxima = dados.get("tem_proxima", False)
            tem_anterior = dados.get("tem_anterior", False)
            
            # Log para debug
            logger.info(f"Retornando {len(data_list)} registros de {total_registros} total")

            # IMPORTANTE: O frontend espera a estrutura com "resultado.data"
            return Response(
                {
                    "sucesso": True,
                    "resultado": {
                        "data": data_list,
                        "pagination": {
                            "current_page": pagina_atual,
                            "page_size": int(filtros_limpos.get('page_size', 10)),
                            "total_records": total_registros,
                            "total_pages": total_paginas,
                            "has_next": tem_proxima,
                            "has_previous": tem_anterior
                        }
                    }
                },
                status=status.HTTP_200_OK
            )

        except requests.RequestException as e:
            logger.error(f"Erro de comunicação ao buscar faturamento: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro de comunicação com o serviço de faturas: {str(e)}",
                    "resultado": {
                        "data": [],
                        "pagination": {
                            "current_page": int(filtros_limpos.get('page', 1)),
                            "page_size": int(filtros_limpos.get('page_size', 10)),
                            "total_records": 0,
                            "total_pages": 1,
                            "has_next": False,
                            "has_previous": False
                        }
                    }
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar faturamento: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro interno ao processar consulta: {str(e)}",
                    "resultado": {
                        "data": [],
                        "pagination": {
                            "current_page": int(filtros_limpos.get('page', 1)),
                            "page_size": int(filtros_limpos.get('page_size', 10)),
                            "total_records": 0,
                            "total_pages": 1,
                            "has_next": False,
                            "has_previous": False
                        }
                    }
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )         
class BuscarCorretores(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, codigo, *args, **kwargs):
        try:
            service = FedhubService()

            corretor = service.buscar_corretor_por_codigo(codigo)
            
            logger.info(f"Corretor encontrado: {corretor}")

            if not corretor:
                return Response(
                    {"status": "error", "message": "Corretor não encontrado."},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                {
                    "status": "success",
                    "data": corretor
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Erro ao buscar corretor: {str(e)}")
            return Response(
                {"status": "error", "message": "Erro interno ao buscar corretor."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class BuscarNFSEPorBoleto(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, documento, *args, **kwargs):
        try:
            service = FedhubService()

            nota_id = service.buscar_nfse_por_boleto(documento)
            
            logger.info(f"NFSE encontrada: {nota_id}")

            if not nota_id:
                return Response(
                    {"status": "error", "message": "NFSE não encontrada."},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                {
                    "status": "success",
                    "data": nota_id
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Erro ao buscar nota: {str(e)}")
            return Response(
                {"status": "error", "message": "Erro interno ao buscar nota."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )                     

class BuscarFaturasComBoletosESegurados(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        service = FedhubService()
        
        logger.info(f"Parâmetros da requisição de faturas com boletos: {request.query_params}")

        # Coletar todos os parâmetros possíveis
        filtros = {
            "fatura": request.query_params.get("fatura"),
            "apolice": request.query_params.get("apolice"),
            "administradora": request.query_params.get("administradora"),
            "status": request.query_params.get("status"),
            "data_ini": request.query_params.get("data_ini"),
            "data_fim": request.query_params.get("data_fim"),
            
            "page": request.query_params.get("page", 1),
            "page_size": request.query_params.get("page_size", 10),
            
            "limit": request.query_params.get("limit", 500),
            "offset": request.query_params.get("offset", 0),
        }

        # Remover filtros vazios
        filtros_limpos = {k: v for k, v in filtros.items() if v not in [None, "", "null"]}
        logger.info(f"Filtros limpos para faturas com boletos: {filtros_limpos}")

        try:
            # Calcular offset baseado na página (para compatibilidade)
            page = int(filtros_limpos.get('page', 1))
            page_size = int(filtros_limpos.get('page_size', 10))
            offset = (page - 1) * page_size
            
            # Atualizar filtros com offset calculado
            filtros_limpos['limit'] = page_size
            filtros_limpos['offset'] = offset
            
            # Remover parâmetros de paginação do serviço (se não for compatível)
            filtros_para_servico = filtros_limpos.copy()
            
            dados = service.buscar_faturas_com_boletos(filtros_para_servico)
            logger.info(f"Dados retornados do serviço de faturas com boletos: {dados}")

            if dados.get("status") != "success":
                return Response(
                    {
                        "sucesso": False,
                        "erro": dados.get("message", "Erro ao buscar faturas"),
                        "resultado": []
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
            # Extrair dados importantes
            data_list = dados.get("data", [])
            total_registros = dados.get("total_registros", 0)
            
            # Calcular informações de paginação
            total_pages = max(1, (total_registros + page_size - 1) // page_size) 
            current_page = page

            return Response(
                {
                    "sucesso": True,
                    "resultado": {
                        "data": data_list,
                        "pagination": {
                            "current_page": current_page,
                            "page_size": page_size,
                            "total_records": total_registros,
                            "total_pages": total_pages,
                            "has_next": current_page < total_pages,
                            "has_previous": current_page > 1,
                            "next_page": current_page + 1 if current_page < total_pages else None,
                            "previous_page": current_page - 1 if current_page > 1 else None,
                            "offset": offset,
                            "limit": page_size
                        },
                        "filters": dados.get("filters", {}),
                        "total_registros": total_registros  
                    }
                },
                status=status.HTTP_200_OK
            )

        except requests.RequestException as e:
            logger.error(f"Erro de comunicação ao buscar faturas com boletos: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro de comunicação com o serviço de faturas: {str(e)}",
                    "resultado": []
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar faturas com boletos: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro interno ao processar consulta: {str(e)}",
                    "resultado": []
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )            
class BuscarFaturasComBoletosPaginadas(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        service = FedhubService()
        
        logger.info(f"Parâmetros da requisição faturas com boletos paginadas: {request.query_params}")

        # Coletar parâmetros específicos da rota paginada
        filtros = {
            "fatura": request.query_params.get("fatura"),
            "apolice": request.query_params.get("apolice"),
            "administradora": request.query_params.get("administradora"),
            "status": request.query_params.get("status"),
            "data_ini": request.query_params.get("data_ini"),
            "data_fim": request.query_params.get("data_fim"),
            "pagina": request.query_params.get("pagina", 1),
            "por_pagina": request.query_params.get("por_pagina", 50),
        }

        # Remover filtros vazios
        filtros_limpos = {k: v for k, v in filtros.items() if v not in [None, "", "null"]}
        
        # Converter tipos numéricos
        try:
            if filtros_limpos.get('fatura'):
                filtros_limpos['fatura'] = int(filtros_limpos['fatura'])
            if filtros_limpos.get('pagina'):
                filtros_limpos['pagina'] = int(filtros_limpos['pagina'])
            if filtros_limpos.get('por_pagina'):
                filtros_limpos['por_pagina'] = int(filtros_limpos['por_pagina'])
        except ValueError as e:
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro na conversão de parâmetros numéricos: {str(e)}"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(f"Filtros limpos para faturas com boletos paginadas: {filtros_limpos}")

        try:
            # Chamar serviço paginado específico para boletos
            dados = service.buscar_faturas_com_boletos_paginadas(filtros_limpos)
            
            if not dados or dados.get("status") != "success":
                return Response(
                    {
                        "sucesso": False,
                        "erro": dados.get("message", "Nenhum resultado encontrado"),
                        "resultado": []
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            # Extrair dados da resposta
            data_list = dados.get("data", [])
            total_registros = dados.get("total_registros", 0)
            pagina_atual = dados.get("pagina_atual", 1)
            por_pagina = dados.get("por_pagina", 50)
            total_paginas = dados.get("total_paginas", 1)

            return Response(
                {
                    "sucesso": True,
                    "resultado": {
                        "data": data_list,
                        "pagination": {
                            "current_page": pagina_atual,
                            "page_size": por_pagina,
                            "total_records": total_registros,
                            "total_pages": total_paginas,
                            "has_next": pagina_atual < total_paginas,
                            "has_previous": pagina_atual > 1,
                            "next_page": pagina_atual + 1 if pagina_atual < total_paginas else None,
                            "previous_page": pagina_atual - 1 if pagina_atual > 1 else None
                        },
                        "filters": dados.get("filters", {}),
                        "total_registros": total_registros
                    }
                },
                status=status.HTTP_200_OK
            )

        except requests.RequestException as e:
            logger.error(f"Erro de comunicação ao buscar faturas com boletos paginadas: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro de comunicação com o serviço de faturas: {str(e)}",
                    "resultado": []
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar faturas com boletos paginadas: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro interno ao processar consulta: {str(e)}",
                    "resultado": []
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# *******************************************# 
# *******************************************# 
# *******************************************# 
class TratamentoDeErroView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        Roda a procedure de tratamento de erros no FastAPI
        POST /faturamento/tratamento-de-erros/rodar-procedure/
        """
        try:
            service = FedhubService()
            
            # Chama o FastAPI para rodar a procedure
            # Usando método síncrono ou assíncrono conforme necessário
            resultado = service.rodar_procedure_tratamento_erro()
            
            if resultado and resultado.get("status") == "success":
                return Response(
                    {
                        "sucesso": True,
                        "mensagem": "Procedure de tratamento de erros executada com sucesso",
                        "resultado": resultado.get("data", {})
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "sucesso": False,
                        "erro": resultado.get("message", "Erro ao executar procedure") if resultado else "Erro desconhecido"
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            logger.error(f"Erro ao rodar procedure de tratamento de erros: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro interno: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class ConverterBoletoCSVView(APIView):
    """
    Converte boletos de uma fatura para CSV
    GET /faturamento/formato-arquivos/converter-boleto-csv?fatura=169777
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            # Log da requisição completa
            logger.info(f"=== CONVERTER BOLETO CSV ===")
            logger.info(f"Método: {request.method}")
            logger.info(f"Path: {request.path}")
            logger.info(f"Query params: {request.query_params}")
            logger.info(f"Headers: {dict(request.headers)}")
            
            # Pega o número da fatura da query string
            fatura = request.query_params.get("fatura")
            
            if not fatura:
                logger.error("Parâmetro 'fatura' não informado")
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Parâmetro 'fatura' é obrigatório"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Valida se é número
            try:
                fatura = int(fatura)
            except ValueError:
                logger.error(f"Parâmetro 'fatura' inválido: {fatura}")
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Parâmetro 'fatura' deve ser um número válido"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Convertendo boletos da fatura {fatura} para CSV")
            
            # Chama o serviço
            service = FedhubService()
            resultado = service.converter_boleto_csv(fatura)
            
            logger.info(f"Resultado do serviço: {resultado}")
            
            # Verifica se houve erro
            if not resultado:
                logger.error("Erro ao comunicar com o serviço de conversão")
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Erro ao comunicar com o serviço de conversão"
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            # Se a fatura não foi encontrada
            if resultado.get("status") == "not_found":
                logger.warning(f"Fatura {fatura} não encontrada")
                return Response(
                    {
                        "sucesso": False,
                        "erro": resultado.get("message", "Fatura não encontrada"),
                        "fatura": fatura
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Se o CSV foi gerado com sucesso
            if resultado.get("status") == "success" and resultado.get("csv_content"):
                logger.info(f"CSV gerado com sucesso para fatura {fatura}")
                logger.info(f"Tamanho do CSV: {len(resultado['csv_content'])} bytes")
                
                # Cria resposta HTTP com o CSV
                response = HttpResponse(
                    resultado["csv_content"],
                    content_type="text/csv; charset=utf-8"
                )
                response['Content-Disposition'] = f'attachment; filename="{resultado["filename"]}"'
                response['Access-Control-Expose-Headers'] = 'Content-Disposition'
                response['Content-Length'] = len(resultado["csv_content"])
                
                return response
            
            # Se não tem CSV, retorna erro
            logger.error(f"Nenhum boleto encontrado para fatura {fatura}")
            return Response(
                {
                    "sucesso": False,
                    "erro": "Nenhum boleto encontrado para esta fatura",
                    "fatura": fatura
                },
                status=status.HTTP_404_NOT_FOUND
            )
            
        except Exception as e:
            logger.error(f"Erro ao converter boleto para CSV: {str(e)}", exc_info=True)
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro interno: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# *******************************************# 
# ************* SEGUNDA VIA BOLETO *****************# 
# *******************************************# 
class DadosSegundaViaBoletoView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            logger.info(f"=== SEGUNDA VIA BOLETO ===")
            
            # ⚠️ IMPORTANTE: Extrair fatura corretamente
            # Sua URL é: /faturamento/dados-segunda-via-boleto/162028/
            # O parâmetro está na URL, não no query_params!
            
            # Opção 1: Se for path parameter (recomendado)
            fatura = kwargs.get('fatura')  # Pega da URL
            
            # Opção 2: Se for query string
            # fatura = request.query_params.get("fatura")
            
            if not fatura:
                logger.error("Fatura não informada")
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Parâmetro 'fatura' é obrigatório"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Buscando dados para fatura: {fatura}")
            
            service = FedhubService()
            dados = service.processar_dados_segunda_via_boleto(fatura)
            
            if not dados:
                logger.error(f"Erro ao gerar segunda via do boleto para fatura {fatura}")
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Erro ao gerar segunda via do boleto"
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return Response(
                {
                    "sucesso": True,
                    "dados": dados
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Erro ao gerar segunda via do boleto: {str(e)}", exc_info=True)
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro interno: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            

class EmissaoSegundaViaBoletoView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        fatura = kwargs.get('fatura')
        boletos = request.data

        if not fatura:
            return Response(
                {"sucesso": False, "erro": "Parâmetro 'fatura' é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            service = FedhubService()
            resultado = service.emitir_segunda_via_boleto(fatura, boletos)

            if not resultado or resultado.get("status") != "success":
                return Response(
                    {"sucesso": False, "erro": "Erro ao emitir segunda via do boleto"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            response = HttpResponse(
                resultado["content"],
                content_type="application/pdf"
            )
            response['Content-Disposition'] = f'attachment; filename="{resultado["filename"]}"'
            response['Access-Control-Expose-Headers'] = 'Content-Disposition'
            return response

        except Exception as e:
            logger.error(f"Erro ao emitir segunda via: {str(e)}", exc_info=True)
            return Response(
                {"sucesso": False, "erro": f"Erro interno: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




            
            
