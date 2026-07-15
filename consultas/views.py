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

class BuscarComissaoPorDataCorteView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


    def get(self, request, data_corte, *args, **kwargs):
        try:
            logger.info("========== DEBUG COMISSÕES ==========")
            logger.info(f"data_corte (path param): {data_corte}")
            logger.info(f"type(data_corte): {type(data_corte)}")

            logger.info("Query params RAW:")
            for k, v in request.query_params.lists():
                logger.info(f"  {k} = {v} | type={type(v)}")

            logger.info("Query params iterados (simples):")
            for key, value in request.query_params.items():
                logger.info(f"  {key} = {value} | type={type(value)}")

            params = {}

            logger.info("Montando params finais:")

            for key, value in request.query_params.items():
                if value not in [None, '', 'null']:
                    params[key] = value
                    logger.info(f"  ADICIONADO -> {key} = {value} (type={type(value)})")
                else:
                    logger.info(f"  IGNORADO -> {key} = {value}")

            logger.info(f"PARAMS FINAIS: {params}")
            logger.info("=====================================")
            
            service = FedhubService()
            dados = service.buscar_comissao_por_data_corte(data_corte, params)
            if not dados:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Não foi possível consultar comissões. Verifique a data informada."
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            
            if dados.get("status") == "error":
                return Response(
                    {
                        "sucesso": False,
                        "erro": dados.get("message", "Erro na consulta")
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            return Response(
                {
                    "sucesso": True,
                    "dados": dados,
                    "data_corte": data_corte,
                    "filtros_aplicados": params
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Erro em BuscarComissaoPorDataCorteView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class BuscarComissaoPorDataCorteV2View(APIView):
    """
    Busca comissões por data de corte - VERSÃO 100% CONSISTENTE
    GET /comissoes/por-data-v2/<str:data_corte>/
    
    Parâmetros (query string):
        - favorecido: Código do favorecido (com ou sem zeros)
        - fatura: Número da fatura
        - vencimento_inicial: Data inicial (YYYY-MM-DD)
        - vencimento_final: Data final (YYYY-MM-DD)
        - status: todas, baixadas, pendentes
        - tipo: Tipo de comissão (A, B, etc)
        - co_estipulante: Co-estipulante
        - apolice: Número da apólice
        - recibo: Número do recibo/voucher
        - limit: Limite de registros (default: 100)
        - offset: Offset para paginação (default: 0)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, data_corte, *args, **kwargs):
        try:
            # Coleta todos os parâmetros da query string
            params = {}
            for key, value in request.query_params.items():
                if value not in [None, '', 'null']:
                    params[key] = value
            
            service = FedhubService()
            dados = service.buscar_comissoes_v2(data_corte, params)
            
            if not dados:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Não foi possível consultar comissões. Verifique a data informada."
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            
            # A V2 já retorna no formato correto
            return Response(
                {
                    "sucesso": True,
                    "dados": {
                        "data": dados.get("data", []),
                        "total_registros": dados.get("total_registros", 0),
                    },
                    "data_corte": data_corte,
                    "filtros_aplicados": params,
                    "versao": "v2"
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Erro em BuscarComissaoPorDataCorteV2View: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class ConsultarComissaoView(APIView):
    """
    Consulta comissões com voucher emitido (consulta/histórico)
    GET /comissoes/consultar/
    
    Parâmetros (query string):
        - favorecido: Código do favorecido (com ou sem zeros)
        - fatura: Número da fatura
        - vencimento_inicial: Data inicial (YYYY-MM-DD)
        - vencimento_final: Data final (YYYY-MM-DD)
        - status: todas, baixadas, pendentes
        - tipo: Tipo de comissão (A, B, etc)
        - co_estipulante: Co-estipulante
        - apolice: Número da apólice
        - voucher: Número do voucher/recibo
        - produto: Descrição do produto
        - vigencia_inicial: Início da vigência (YYYY-MM-DD)
        - vigencia_final: Fim da vigência (YYYY-MM-DD)
        - limit: Limite de registros (default: 100)
        - offset: Offset para paginação (default: 0)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            params = {}
            for key, value in request.query_params.items():
                if value not in [None, '', 'null']:
                    params[key] = value
            
            service = FedhubService()
            dados = service.consultar_comissoes(params)
            
            if not dados:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Não foi possível consultar comissões."
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            
            if dados.get("status") == "error":
                return Response(
                    {
                        "sucesso": False,
                        "erro": dados.get("message", "Erro na consulta")
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            return Response(
                {
                    "sucesso": True,
                    "dados": {
                        "data": dados.get("data", []),
                        "total_registros": dados.get("total_registros", 0),
                    },
                    "filtros_aplicados": params,
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Erro em ConsultarComissaoView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class BuscarProdutosPorFavorecidoView(APIView):
    """
    Retorna lista de produtos distintos para um favorecido
    GET /comissoes/produtos-por-favorecido/?favorecido=...
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            favorecido = request.query_params.get('favorecido')
            if not favorecido:
                return Response(
                    {"sucesso": False, "erro": "Parâmetro 'favorecido' é obrigatório"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            service = FedhubService()
            dados = service.buscar_produtos_por_favorecido(favorecido)
            
            if not dados:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Erro ao buscar produtos"
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            
            return Response(
                {
                    "sucesso": True,
                    "produtos": dados.get("produtos", []),
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Erro em BuscarProdutosPorFavorecidoView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
             
class EmitirReciboComissaoView(APIView):
    """
    Emite recibo do corretor (agrupado por favorecido)
    POST /comissoes/emitir-recibo/
    
    Payload esperado:
    {
        "tipo_documento": "recibo_corretor",
        "data_corte": "2026-06-01",
        "data_emissao": "2026-07-03",
        "usuario": "nome_usuario",
        "comissoes": [...],
        "retencoes": [...],
        "resumo": {...}
    }
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            logger.info("========== EMITIR RECIBO DO CORRETOR ==========")
            dados = request.data
            
            # Valida dados básicos
            if not dados.get('comissoes'):
                return Response(
                    {"sucesso": False, "erro": "Nenhuma comissão selecionada"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Chama o serviço
            service = FedhubService()
            
            # Prepara o payload para o FastAPI
            payload = {
                "tipo_documento": dados.get("tipo_documento", "recibo_corretor"),
                "data_corte": dados.get("data_corte"),
                "data_emissao": dados.get("data_emissao", datetime.now().strftime("%Y-%m-%d")),
                "usuario": dados.get("usuario", request.user.email),
                "comissoes": dados.get("comissoes", []),
                "retencoes": dados.get("retencoes", []),
                "resumo": dados.get("resumo", {}),
            }
            
            # Chama o FastAPI para gerar o PDF
            resultado = service.emitir_recibo_comissao(payload)
            
            if not resultado:
                return Response(
                    {"sucesso": False, "erro": "Erro ao gerar recibo do corretor"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            # Se o FastAPI retornou o PDF em base64
            if resultado.get("pdf_base64"):
                return Response({
                    "sucesso": True,
                    "numero_documento": resultado.get("numero_documento"),
                    "nome_arquivo": resultado.get("nome_arquivo"),
                    "pdf_base64": resultado.get("pdf_base64"),
                    "mensagem": "Recibo do corretor gerado com sucesso"
                }, status=status.HTTP_200_OK)
            
            # Se retornou apenas dados (sem PDF)
            return Response({
                "sucesso": True,
                "dados": resultado,
                "mensagem": "Recibo do corretor gerado com sucesso"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Erro em EmitirReciboCorretorView: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class EmitirVoucherComissaoView(APIView):
    """
    Emite voucher de comissão
    POST /comissoes/emitir-voucher/
    
    Payload esperado:
    {
        "tipo_documento": "voucher",
        "data_corte": "2026-06-01",
        "data_emissao": "2026-06-23",
        "usuario": "nome_usuario",
        "comissoes": [...],
        "retencoes": [...],
        "resumo": {...}
    }
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            logger.info("========== EMITIR VOUCHER ==========")
            dados = request.data
            
            # Valida dados básicos
            if not dados.get('comissoes'):
                return Response(
                    {"sucesso": False, "erro": "Nenhuma comissão selecionada"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Chama o serviço
            service = FedhubService()
            
            # Prepara o payload para o FastAPI
            payload = {
                "tipo_documento": dados.get("tipo_documento", "voucher"),
                "data_corte": dados.get("data_corte"),
                "data_emissao": dados.get("data_emissao", datetime.now().strftime("%Y-%m-%d")),
                "usuario": dados.get("usuario", request.user.email),
                "comissoes": dados.get("comissoes", []),
                "retencoes": dados.get("retencoes", []),
                "resumo": dados.get("resumo", {}),
            }
            
            # Chama o FastAPI para gerar o PDF
            resultado = service.emitir_voucher_comissao(payload)
            
            if not resultado:
                return Response(
                    {"sucesso": False, "erro": "Erro ao gerar voucher"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            # Se o FastAPI retornou o PDF em base64
            if resultado.get("pdf_base64"):
                return Response({
                    "sucesso": True,
                    "numero_documento": resultado.get("numero_documento"),
                    "nome_arquivo": resultado.get("nome_arquivo"),
                    "pdf_base64": resultado.get("pdf_base64"),
                    "mensagem": "Voucher gerado com sucesso"
                }, status=status.HTTP_200_OK)
            
            # Se retornou apenas dados
            return Response({
                "sucesso": True,
                "dados": resultado,
                "mensagem": "Voucher gerado com sucesso"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Erro em EmitirVoucherComissaoView: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CancelarComissaoView(APIView):
    """
    Cancela uma ou mais comissões.
    POST /comissoes/cancelar/
    Payload esperado:
    {
        "comissoes": [
            {
                "fatura": 379807,
                "parcela": 1,
                "documento": "0001525504",
                "favorecido": "0000002098",
                "voucher": "20129486",
                "tipo": "BENEFICIO"
            }
        ]
    }
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            lista_comissoes = request.data.get("comissoes", [])

            if not lista_comissoes:
                return Response(
                    {"sucesso": False, "erro": "Nenhuma comissão fornecida para cancelamento."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info("========== CANCELAR COMISSÕES ==========")
            logger.info(f"Dados recebidos para cancelamento: {lista_comissoes}")
            logger.info("========================================")

            service = FedhubService()
            resultados = []
            comissoes_canceladas = 0

            for comissao in lista_comissoes:
                numero_comissao = comissao.get("voucher")
                parcela = comissao.get("parcela")
                documento = comissao.get("documento")
                favorecido = comissao.get("favorecido")
                tipo_comissao = comissao.get("tipo")
                voucher = comissao.get("voucher")
                fatura = comissao.get("fatura")
                motivo_cancelamento = comissao.get("motivo_cancelamento", "Cancelamento solicitado pelo usuário")

                # Valida dados obrigatórios
                if not all([numero_comissao, favorecido]):
                    logger.warning(f"Comissão ignorada devido a dados faltantes: {comissao}")
                    resultados.append({
                        "comissao": comissao,
                        "status": "erro",
                        "mensagem": "Dados obrigatórios (voucher, favorecido) faltando."
                    })
                    continue

                payload_fedhub = {
                    "numero_comissao": numero_comissao,
                    "parcela": parcela,
                    "documento": documento,
                    "favorecido": favorecido,
                    "tipo_comissao": tipo_comissao,
                    "voucher": voucher,
                    "fatura": fatura,
                    "motivo_cancelamento": motivo_cancelamento
                }

                logger.info(f"Cancelando comissão: {payload_fedhub}")

                resultado = service.cancelar_comissao(payload_fedhub)

                if resultado and resultado.get("status") == "success":
                    comissoes_canceladas += 1
                    resultados.append({
                        "comissao": comissao,
                        "status": "sucesso",
                        "mensagem": resultado.get("message", "Cancelada com sucesso")
                    })
                else:
                    resultados.append({
                        "comissao": comissao,
                        "status": "erro",
                        "mensagem": resultado.get("message", "Erro ao cancelar comissão") if resultado else "Erro desconhecido"
                    })

            return Response(
                {
                    "sucesso": True,
                    "mensagem": f"{comissoes_canceladas} comissão(ões) cancelada(s) com sucesso.",
                    "total_processadas": len(lista_comissoes),
                    "total_canceladas": comissoes_canceladas,
                    "resultados": resultados
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Erro em CancelarComissaoView: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class BuscarPessoasView(APIView):
    """
    Busca pessoas (favorecidos)
    GET /pessoas/
    POST /pessoas/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            service = FedhubService()
            limit = request.query_params.get("limit")
            search = request.query_params.get("search", "").strip()
            nome = request.query_params.get("nome", "").strip()
            cnpj = request.query_params.get("cnpj", "").strip()
            codigo = request.query_params.get("codigo", "").strip()

            params = {
                "status": request.query_params.get("status", "A"),
                "limit": limit if limit else 7000,
                "offset": request.query_params.get("offset", 0),
            }
            if search:
                params["search"] = search
            if nome:
                params["nome"] = nome
            if cnpj:
                params["cnpj"] = cnpj
            if codigo:
                params["codigo"] = codigo

            dados = service.buscar_pessoas(params)
            if not dados:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar pessoas"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            data = dados.get("data") if isinstance(dados, dict) else dados
            total = dados.get("total", len(data)) if isinstance(dados, dict) else len(data) if isinstance(data, list) else 0

            if search or nome or cnpj or codigo:
                data = self._filter_locally(data, search, nome, cnpj, codigo)
                total = len(data)

            return Response({
                "data": data,
                "total": total,
                "status": "success",
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Erro em BuscarPessoasView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _filter_locally(self, data, search, nome, cnpj, codigo):
        if not isinstance(data, list):
            return data

        filtered = data
        term = search or nome
        if term:
            term_lower = term.lower()
            filtered = [
                p for p in filtered
                if term_lower in (p.get("nome") or p.get("NOME") or "").lower()
                or term_lower in (p.get("cpf_cnpj") or p.get("CPF_CNPJ") or "").lower()
                or term_lower in str(p.get("codigo") or p.get("PESSOA") or "").lower()
            ]
        if cnpj:
            cnpj_digits = "".join(filter(str.isdigit, cnpj))
            filtered = [
                p for p in filtered
                if cnpj_digits in "".join(filter(str.isdigit, p.get("cpf_cnpj") or p.get("CPF_CNPJ") or ""))
            ]
        if codigo:
            filtered = [
                p for p in filtered
                if codigo.lower() in str(p.get("codigo") or p.get("PESSOA") or "").lower()
            ]

        return filtered

    def post(self, request, *args, **kwargs):
        try:
            service = FedhubService()
            dados_pessoa = request.data

            logger.info(f"Dados recebidos para criar pessoa: {dados_pessoa}")

            resultado = service.criar_pessoa(dados_pessoa)
            if not resultado:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Erro ao criar pessoa no sistema",
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            if resultado.get("status") == "timeout":
                return Response(
                    {
                        "sucesso": False,
                        "erro": resultado.get(
                            "message", "Timeout ao criar pessoa no FedHub"
                        ),
                    },
                    status=status.HTTP_504_GATEWAY_TIMEOUT,
                )

            if resultado.get("status") != "success":
                http_status = resultado.get("http_status", status.HTTP_400_BAD_REQUEST)
                return Response(
                    {
                        "sucesso": False,
                        "erro": resultado.get("message", "Erro ao criar pessoa"),
                    },
                    status=http_status,
                )

            return Response(
                {
                    "sucesso": True,
                    "mensagem": "Pessoa criada com sucesso",
                    "data": resultado.get("data", {}),
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.error(f"Erro ao criar pessoa: {str(e)}", exc_info=True)
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro interno: {str(e)}",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class BuscarPessoaPorCodigoView(APIView):
    """
    Busca pessoa (favorecido) por código
    GET /pessoas/{codigo}/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, codigo, *args, **kwargs):
        try:
            service = FedhubService()
            dados = service.buscar_pessoa_por_codigo(codigo)
            if not dados:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar pessoa"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(dados, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Erro em BuscarPessoaPorCodigoView: {e}")
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
            nome = request.query_params.get("nome", "").strip()
            cnpj = request.query_params.get("cnpj", "").strip()
            codigo = request.query_params.get("codigo", "").strip()
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 20))

            service = FedhubService()
            dados = asyncio.run(service.buscar_todas_empresas())

            if not dados:
                return Response({
                    "status": "not_found",
                    "message": "Empresa não encontrada",
                    "timestamp": datetime.now().isoformat()
                }, status=status.HTTP_404_NOT_FOUND)

            if nome:
                dados = [
                    e for e in dados
                    if nome.lower() in (e.get("nome") or e.get("NOME") or "").lower()
                ]
            if cnpj:
                cnpj_digits = "".join(filter(str.isdigit, cnpj))
                dados = [
                    e for e in dados
                    if cnpj_digits in "".join(filter(str.isdigit, e.get("cnpj") or e.get("CNPJ") or ""))
                ]
            if codigo:
                dados = [
                    e for e in dados
                    if codigo.lower() in str(e.get("codigo") or e.get("CODIGO") or e.get("id") or "").lower()
                ]

            total = len(dados)
            start = (page - 1) * page_size
            end = start + page_size
            paginated = dados[start:end]

            return Response({
                "status": "success",
                "total_returned": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if total else 0,
                "data": paginated,
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
            
            fatura = kwargs.get('fatura')  
            
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


# consultas/views.py

class CriarPessoaView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            service = FedhubService()
            dados_pessoa = request.data
            
            logger.info(f"Dados recebidos para criar pessoa: {dados_pessoa}")
            
            # ✅ Chama o FastAPI para criar a pessoa
            resultado = service.criar_pessoa(dados_pessoa)
            
            if not resultado:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Erro ao criar pessoa no sistema"
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            if resultado.get("status") == "timeout":
                return Response(
                    {
                        "sucesso": False,
                        "erro": resultado.get(
                            "message", "Timeout ao criar pessoa no FedHub"
                        ),
                    },
                    status=status.HTTP_504_GATEWAY_TIMEOUT,
                )
            
            # Verifica se o FastAPI retornou erro
            if resultado.get("status") != "success":
                http_status = resultado.get("http_status", status.HTTP_400_BAD_REQUEST)
                return Response(
                    {
                        "sucesso": False,
                        "erro": resultado.get("message", "Erro ao criar pessoa")
                    },
                    status=http_status
                )
            
            # ✅ Retorna sucesso com Response
            return Response(
                {
                    "sucesso": True,
                    "mensagem": "Pessoa criada com sucesso",
                    "data": resultado.get("data", {})
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.error(f"Erro ao criar pessoa: {str(e)}", exc_info=True)
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro interno: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class BuscarCedentesView(APIView):
    """
    Busca todos os cedentes via FastAPI
    GET /cedentes/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            service = FedhubService()
            
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
    GET /cedentes/buscar/?nome=termo
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
            
            service = FedhubService()
            
            # Busca cedente por nome no FastAPI
            resultado = service.buscar_cedente_por_nome(nome)
            
            if not resultado:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Erro ao buscar cedente"
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            if resultado.get("status") != "success":
                return Response(
                    {
                        "sucesso": False,
                        "erro": resultado.get("message", "Erro ao buscar cedente")
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response(
                {
                    "sucesso": True,
                    "data": resultado.get("data", []),
                    "total": resultado.get("total", 0)
                },
                status=status.HTTP_200_OK
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


# *******************************************#
#********** Excel e PDF ********#
# *******************************************# 
class ExportarFaturasDinamicasPaginadasExcel(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    renderer_classes = [BinaryRenderer]

    def get(self, request, *args, **kwargs):
        service = FedhubService()
        
        logger.info(f"Exportação Excel dinâmica paginada - Parâmetros: {request.query_params}")

        # Coletar parâmetros (os mesmos da consulta)
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
            "por_pagina": request.query_params.get("por_pagina", 1000),
        }

        # Remover filtros vazios
        filtros_limpos = {k: v for k, v in filtros.items() if v not in [None, "", "null"]}
        
        # Adicionar limite maior para exportação
        filtros_limpos['pagina'] = 1
        filtros_limpos['por_pagina'] = 5000  # Limite maior para exportação

        try:
            # Buscar dados do microsserviço
            dados = service.buscar_faturas_dinamicamente_paginadas(filtros_limpos)
            
            if not dados or dados.get("status") != "success":
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Nenhum dado encontrado para exportação"
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            data_list = dados.get("data", [])
            
            if not data_list:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Nenhum registro encontrado com os filtros informados"
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            # Criar DataFrame pandas
            df = pd.DataFrame(data_list)
            
            # Selecionar e renomear colunas importantes para FATURAS
            colunas_selecionadas = [
                'fatura', 'apolice', 'administradora', 'seguradora', 'ramo',
                'data_fat', 'vencimento', 'status', 'quitado',
                'premio_bruto', 'premio_liq', 'premio_liquido',
                'dt_ini_vig', 'dt_fim_vig', 'quant_parcelas',
                'corretor', 'cod_corretor', 'numero_endosso'
            ]
            
            # Manter apenas colunas que existem no DataFrame (em minúsculo)
            colunas_disponiveis = [col for col in colunas_selecionadas if col in df.columns]
            df = df[colunas_disponiveis]
            
            # Renomear colunas para nomes mais amigáveis
            mapeamento_colunas = {
                'fatura': 'Nº Fatura',
                'apolice': 'Apólice',
                'administradora': 'Administradora',
                'seguradora': 'Seguradora',
                'ramo': 'Ramo',
                'data_fat': 'Data Fatura',
                'vencimento': 'Vencimento',
                'status': 'Status',
                'quitado': 'Quitado',
                'premio_bruto': 'Prêmio Bruto (R$)',
                'premio_liq': 'Prêmio Líquido (R$)',
                'premio_liquido': 'Prêmio Líquido (R$)',
                'dt_ini_vig': 'Início Vigência',
                'dt_fim_vig': 'Fim Vigência',
                'quant_parcelas': 'Quantidade Parcelas',
                'corretor': 'Corretor',
                'cod_corretor': 'Código Corretor',
                'numero_endosso': 'Nº Endosso'
            }
            
            df.rename(columns=mapeamento_colunas, inplace=True)
            
            # Formatar valores monetários
            colunas_monetarias = ['Prêmio Bruto (R$)', 'Prêmio Líquido (R$)']
            
            for col in colunas_monetarias:
                if col in df.columns:
                    # Converter para numérico e formatar
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    df[col] = df[col].apply(
                        lambda x: f'R$ {x:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.') 
                        if pd.notnull(x) else ''
                    )
            
            # Formatar datas
            colunas_datas = ['Data Fatura', 'Vencimento', 'Início Vigência', 'Fim Vigência']
            
            for col in colunas_datas:
                if col in df.columns:
                    # Converter para datetime
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    df[col] = df[col].dt.strftime('%d/%m/%Y')
            
            # Ordenar por data da fatura (mais recente primeiro)
            if 'Data Fatura' in df.columns:
                df = df.sort_values('Data Fatura', ascending=False)
            
            # Criar arquivo Excel em memória
            output = BytesIO()
            
            # Criar Excel writer com openpyxl
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Escrever dados principais
                df.to_excel(writer, sheet_name='Faturas Dinâmicas', index=False)
                
                # Ajustar largura das colunas
                worksheet = writer.sheets['Faturas Dinâmicas']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
                
                # Adicionar uma sheet com informações do relatório
                info_df = pd.DataFrame({
                    'Parâmetro': ['Data Exportação', 'Total Registros', 'Filtros Aplicados'],
                    'Valor': [
                        datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                        len(data_list),
                        ', '.join([f'{k}: {v}' for k, v in filtros_limpos.items() if k not in ['pagina', 'por_pagina']]) or 'Nenhum'
                    ]
                })
                
                info_df.to_excel(writer, sheet_name='Informações', index=False)
                
                # Formatar sheet de informações
                info_worksheet = writer.sheets['Informações']
                for column in info_worksheet.columns:
                    column_letter = column[0].column_letter
                    info_worksheet.column_dimensions[column_letter].width = 30
            
            output.seek(0)
            
            # Criar nome do arquivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'faturas_dinamicas_{timestamp}.xlsx'
            
            # Retornar arquivo Excel como resposta
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Access-Control-Expose-Headers'] = 'Content-Disposition'
            
            return response

        except Exception as e:
            logger.error(f"Erro ao exportar para Excel: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro ao gerar arquivo Excel: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )   
class ExportarFaturasComBoletosExcel(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    renderer_classes = [BinaryRenderer]

    def get(self, request, *args, **kwargs):
        service = FedhubService()
        
        logger.info(f"Exportação Excel - Parâmetros: {request.query_params}")

        # Coletar parâmetros (mesmos filtros da consulta normal)
        filtros = {
            "fatura": request.query_params.get("fatura"),
            "apolice": request.query_params.get("apolice"),
            "administradora": request.query_params.get("administradora"),
            "status": request.query_params.get("status"),
            "data_ini": request.query_params.get("data_ini"),
            "data_fim": request.query_params.get("data_fim"),
            "limit": request.query_params.get("limit", 500),
            "offset": request.query_params.get("offset", 0),
        }

        # Remover filtros vazios
        filtros_limpos = {k: v for k, v in filtros.items() if v not in [None, "", "null"]}

        try:
            # Buscar dados do microsserviço
            dados = service.buscar_faturas_com_boletos(filtros_limpos)
            
            if not dados or dados.get("status") != "success":
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Nenhum dado encontrado para exportação"
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            data_list = dados.get("data", [])
            
            if not data_list:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Nenhum registro encontrado com os filtros informados"
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            # Criar DataFrame pandas
            df = pd.DataFrame(data_list)
            
            # Selecionar e renomear colunas importantes
            colunas_selecionadas = [
                'FATURA', 'APOLICE', 'ADMINISTRADORA', 'SEGURADORA',
                'DATA_FAT', 'VENCIMENTO', 'STATUS', 'QUITADO',
                'NOME_COBRADO', 'CNPJ_COBRADO',
                'PREMIO_BRUTO', 'PREMIO_LIQ', 'VALOR',
                'DT_INI_VIG', 'DT_FIM_VIG',
                'NOSSO_NUMERO', 'DOCUMENTO', 'PARCELA', 'PARCELAS',
                'BOLETA_REC', 'BOLETA_QUITADA'
            ]
            
            # Manter apenas colunas que existem no DataFrame
            colunas_disponiveis = [col for col in colunas_selecionadas if col in df.columns]
            df = df[colunas_disponiveis]
            
            # Renomear colunas para nomes mais amigáveis
            mapeamento_colunas = {
                'FATURA': 'Nº Fatura',
                'APOLICE': 'Apólice',
                'ADMINISTRADORA': 'Administradora',
                'SEGURADORA': 'Seguradora',
                'DATA_FAT': 'Data Fatura',
                'VENCIMENTO': 'Vencimento',
                'STATUS': 'Status',
                'QUITADO': 'Quitado',
                'NOME_COBRADO': 'Tomador',
                'CNPJ_COBRADO': 'CNPJ',
                'PREMIO_BRUTO': 'Prêmio Bruto (R$)',
                'PREMIO_LIQ': 'Prêmio Líquido (R$)',
                'VALOR': 'Valor Boleto (R$)',
                'DT_INI_VIG': 'Início Vigência',
                'DT_FIM_VIG': 'Fim Vigência',
                'NOSSO_NUMERO': 'Nosso Número',
                'DOCUMENTO': 'Documento',
                'PARCELA': 'Parcela Atual',
                'PARCELAS': 'Total Parcelas',
                'BOLETA_REC': 'Boleta Recebida (R$)',
                'BOLETA_QUITADA': 'Boleta Quitada'
            }
            
            df.rename(columns=mapeamento_colunas, inplace=True)
            
            # Formatar valores monetários
            colunas_monetarias = ['Prêmio Bruto (R$)', 'Prêmio Líquido (R$)', 
                                  'Valor Boleto (R$)', 'Boleta Recebida (R$)']
            
            for col in colunas_monetarias:
                if col in df.columns:
                    # Converter para numérico e formatar
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    df[col] = df[col].apply(
                        lambda x: f'R$ {x:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.') 
                        if pd.notnull(x) else ''
                    )
            
            # Formatar datas
            colunas_datas = ['Data Fatura', 'Vencimento', 'Início Vigência', 'Fim Vigência']
            
            for col in colunas_datas:
                if col in df.columns:
                    # Converter para datetime
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    df[col] = df[col].dt.strftime('%d/%m/%Y')
            
            # Ordenar por data da fatura (mais recente primeiro)
            if 'Data Fatura' in df.columns:
                df = df.sort_values('Data Fatura', ascending=False)
            
            # Criar arquivo Excel em memória
            output = BytesIO()
            
            # Criar Excel writer com openpyxl
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Escrever dados principais
                df.to_excel(writer, sheet_name='Faturas', index=False)
                
                # Ajustar largura das colunas
                worksheet = writer.sheets['Faturas']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
                
                # Adicionar uma sheet com informações do relatório
                info_df = pd.DataFrame({
                    'Parâmetro': ['Data Exportação', 'Total Registros', 'Filtros Aplicados'],
                    'Valor': [
                        datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                        len(data_list),
                        ', '.join([f'{k}: {v}' for k, v in filtros_limpos.items()]) or 'Nenhum'
                    ]
                })
                
                info_df.to_excel(writer, sheet_name='Informações', index=False)
                
                # Formatar sheet de informações
                info_worksheet = writer.sheets['Informações']
                for column in info_worksheet.columns:
                    column_letter = column[0].column_letter
                    info_worksheet.column_dimensions[column_letter].width = 30
            
            output.seek(0)
            
            # Criar nome do arquivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'faturas_com_boletos_{timestamp}.xlsx'
            
            # Retornar arquivo Excel como resposta
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Access-Control-Expose-Headers'] = 'Content-Disposition'
            
            return response

        except Exception as e:
            logger.error(f"Erro ao exportar para Excel: {str(e)}")
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro ao gerar arquivo Excel: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )           
class ExportarFaturasComBoletosPDF(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    renderer_classes = [BinaryRenderer]

    def get(self, request, *args, **kwargs):
        service = FedhubService()

        filtros = {
            "fatura": request.query_params.get("fatura"),
            "apolice": request.query_params.get("apolice"),
            "administradora": request.query_params.get("administradora"),
            "status": request.query_params.get("status"),
            "data_ini": request.query_params.get("data_ini"),
            "data_fim": request.query_params.get("data_fim"),
            "limit": 500,
        }

        filtros_limpos = {k: v for k, v in filtros.items() if v}

        dados = service.buscar_faturas_com_boletos(filtros_limpos)

        if not dados or dados.get("status") != "success":
            return Response({"erro": "Nenhum dado encontrado"}, status=404)

        data_list = dados.get("data", [])

        response = HttpResponse(content_type="application/pdf")
        filename = f"faturas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Access-Control-Expose-Headers"] = "Content-Disposition"

        c = canvas.Canvas(response, pagesize=A4)
        width, height = A4

        y = height - 2 * cm

        c.setFont("Helvetica-Bold", 12)
        c.drawString(2 * cm, y, "Relatório de Faturas com Boletos")
        y -= 1 * cm

        c.setFont("Helvetica", 8)
        c.drawString(2 * cm, y, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        y -= 1 * cm

        headers = ["Fatura", "Apólice", "Status", "Vencimento", "Valor"]
        col_x = [2, 5, 9, 12, 16]

        c.setFont("Helvetica-Bold", 8)
        for i, h in enumerate(headers):
            c.drawString(col_x[i] * cm, y, h)

        y -= 0.5 * cm
        c.setFont("Helvetica", 8)

        for row in data_list:
            if y < 2 * cm:
                c.showPage()
                y = height - 2 * cm

            c.drawString(col_x[0] * cm, y, str(row.get("FATURA", "")))
            c.drawString(col_x[1] * cm, y, str(row.get("APOLICE", "")))
            c.drawString(col_x[2] * cm, y, str(row.get("STATUS", "")))
            c.drawString(col_x[3] * cm, y, str(row.get("VENCIMENTO", "")))
            c.drawRightString(col_x[4] * cm, y, str(row.get("VALOR", "")))

            y -= 0.4 * cm

        c.showPage()
        c.save()

        return response

# *******************************************#
#********** Localidades ********#
# *******************************************#    
class BuscarCidadesAutocomplete(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            termo = request.query_params.get("termo", "").strip()
            uf = request.query_params.get("uf", "RJ").upper().strip()
            
            if not termo or len(termo) < 2:
                return Response({
                    "status": "success",
                    "data": []
                })
            
            # AGORA É SÍNCRONO E NÃO USA BANCO DE DADOS!
            cidades = buscar_cidades_autocomplete_sync(termo, uf)
            
            return Response({
                "status": "success",
                "data": cidades
            })
            
        except Exception as e:
            logger.error(f"Erro no autocomplete: {str(e)}")
            return Response({
                "status": "error",
                "message": "Erro ao buscar cidades",
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class BuscarLocalidade(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            service = FedhubService()
            dados_localidade = service.buscar_localidades()
            
            # Se não conseguiu buscar do gateway, retorna dados vazios
            if not dados_localidade:
                return Response({
                    "status": "warning",
                    "message": "Nenhuma localidade encontrada",
                    "data": {}
                })
            
            # Estruturar resposta para o frontend
            return Response({
                "status": "success",
                "data": dados_localidade
            })
            
        except Exception as e:
            logger.error(f"Erro ao buscar localidade: {str(e)}")
            return Response({
                "status": "error",
                "message": "Erro ao buscar localidade",
                "data": {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# *******************************************#
#********** AUTOMAÇÕES E UTILITÁRIOS ********#
# *******************************************#            
class AutomacaoSepararPDFView(APIView):
    """Separa um PDF em múltiplos arquivos (um por página)"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        nome_base = request.data.get('nome_base', '')
        
        if not file:
            return Response(
                {"sucesso": False, "erro": "Nenhum arquivo enviado"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not file.name.lower().endswith('.pdf'):
            return Response(
                {"sucesso": False, "erro": "O arquivo deve ser um PDF"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = FedhubService()
            resultado = service.separar_pdf(file, nome_base)
            
            # Se o resultado for bytes (conteúdo do ZIP), retorna como download
            if isinstance(resultado, bytes):
                nome_base_clean = nome_base or file.name.replace('.pdf', '')
                response = HttpResponse(
                    resultado,
                    content_type='application/zip'
                )
                response['Content-Disposition'] = f'attachment; filename="{nome_base_clean}_separado.zip"'
                return response
            
            # Se for erro
            return Response(
                {"sucesso": False, "erro": resultado.get("message", "Erro ao processar")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
                
        except Exception as e:
            logger.error(f"Erro ao separar PDF: {str(e)}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )           
class AutomacaoUploadPDFsBBZView(APIView):
    """Apenas upload - salva os PDFs na pasta de origem"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request, *args, **kwargs):
        files = request.FILES.getlist('files')
        
        if not files:
            return Response(
                {"sucesso": False, "erro": "Nenhum arquivo enviado"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = FedhubService()
            resultado = service.upload_pdfs_bbz(files)
            
            if not resultado:
                return Response(
                    {"sucesso": False, "erro": "Sem resposta do FedHub"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            status_fedhub = resultado.get("status")

            if status_fedhub != "sucesso":
                return Response(
                    {
                        "sucesso": False,
                        "erro": resultado.get("message", f"Status inesperado: {status_fedhub}")
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            return Response({
                "sucesso": True,
                "mensagem": resultado.get("message"),
                "resultado": resultado.get("dados")
            }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Erro no upload: {str(e)}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class AutomacaoProcessarPDFsBBZView(APIView):
    """Apenas processa - move PDFs da pasta origem para pastas corretas"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        fazer_backup = request.data.get('fazer_backup', True)
        
        try:
            service = FedhubService()
            resultado = service.processar_pdfs_bbz(fazer_backup)
            
            if not resultado or resultado.get("status") != "sucesso":
                return Response(
                    {"sucesso": False, "erro": resultado.get("message", "Falha no processamento")},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            return Response({
                "sucesso": True,
                "mensagem": "PDFs processados com sucesso",
                "resultado": resultado.get("dados")
            }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Erro no processamento: {str(e)}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            

# ============================================
# VIEWS PARA ANALYTICS 
# ============================================

class AnalyticsFaturamentoPeriodoView(APIView):
    """
    1. Faturamento por período (agregado por mês)
    GET /analytics/faturamento/?data_ini=YYYY-MM-DD&data_fim=YYYY-MM-DD
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):  # Síncrono, não mais async
        try:
            data_ini_str = request.query_params.get('data_ini')
            data_fim_str = request.query_params.get('data_fim')
            
            if not data_ini_str or not data_fim_str:
                return Response(
                    {"sucesso": False, "erro": "Parâmetros data_ini e data_fim são obrigatórios"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            data_ini = parse_date(data_ini_str)
            data_fim = parse_date(data_fim_str)
            
            if not data_ini or not data_fim:
                return Response(
                    {"sucesso": False, "erro": "Datas inválidas. Use formato YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            service = AnalyticsService()
            # Converte a chamada assíncrona para síncrona
            resultado = async_to_sync(service.get_faturamento_periodo)(data_ini, data_fim)
            
            if resultado:
                return Response(resultado, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar serviço de analytics"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
        except Exception as e:
            logger.error(f"Erro em AnalyticsFaturamentoPeriodoView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class AnalyticsTopAdministradorasView(APIView):
    """
    2. Top administradoras que mais faturam
    GET /analytics/administradoras/top/?limit=10
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):  # Síncrono
        try:
            limit = request.query_params.get('limit', 10)
            
            try:
                limit = int(limit)
                limit = max(1, min(100, limit))
            except ValueError:
                limit = 10
            
            service = AnalyticsService()
            resultado = async_to_sync(service.get_top_administradoras)(limit)
            
            if resultado:
                return Response(resultado, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar serviço de analytics"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
        except Exception as e:
            logger.error(f"Erro em AnalyticsTopAdministradorasView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class AnalyticsInadimplenciaView(APIView):
    """
    3. Métricas de inadimplência
    GET /analytics/inadimplencia/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):  # Síncrono
        try:
            service = AnalyticsService()
            resultado = async_to_sync(service.get_inadimplencia)()
            
            if resultado:
                return Response(resultado, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar serviço de analytics"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
        except Exception as e:
            logger.error(f"Erro em AnalyticsInadimplenciaView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class AnalyticsFaturamentoPorAdministradoraView(APIView):
    """
    4. Faturamento detalhado por administradora no período
    GET /analytics/administradoras/faturamento/?data_ini=YYYY-MM-DD&data_fim=YYYY-MM-DD
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):  # Síncrono
        try:
            data_ini_str = request.query_params.get('data_ini')
            data_fim_str = request.query_params.get('data_fim')
            
            if not data_ini_str or not data_fim_str:
                return Response(
                    {"sucesso": False, "erro": "Parâmetros data_ini e data_fim são obrigatórios"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            data_ini = parse_date(data_ini_str)
            data_fim = parse_date(data_fim_str)
            
            if not data_ini or not data_fim:
                return Response(
                    {"sucesso": False, "erro": "Datas inválidas. Use formato YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            service = AnalyticsService()
            resultado = async_to_sync(service.get_faturamento_por_administradora)(data_ini, data_fim)
            
            if resultado:
                return Response(resultado, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar serviço de analytics"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
        except Exception as e:
            logger.error(f"Erro em AnalyticsFaturamentoPorAdministradoraView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class AnalyticsStatusFaturasView(APIView):
    """
    5. Distribuição de faturas por status
    GET /analytics/faturas/status/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):  # Síncrono
        try:
            service = AnalyticsService()
            resultado = async_to_sync(service.get_status_faturas)()
            
            if resultado:
                return Response(resultado, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar serviço de analytics"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
        except Exception as e:
            logger.error(f"Erro em AnalyticsStatusFaturasView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class AnalyticsDashboardCompletoView(APIView):
    """
    6. Dashboard completo (junção de todas as métricas)
    GET /analytics/dashboard/?data_ini=YYYY-MM-DD&data_fim=YYYY-MM-DD
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):  # Síncrono
        try:
            data_ini_str = request.query_params.get('data_ini')
            data_fim_str = request.query_params.get('data_fim')
            
            if not data_ini_str or not data_fim_str:
                return Response(
                    {"sucesso": False, "erro": "Parâmetros data_ini e data_fim são obrigatórios"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            data_ini = parse_date(data_ini_str)
            data_fim = parse_date(data_fim_str)
            
            if not data_ini or not data_fim:
                return Response(
                    {"sucesso": False, "erro": "Datas inválidas. Use formato YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            service = AnalyticsService()
            resultado = async_to_sync(service.get_dashboard_completo)(data_ini, data_fim)
            
            if resultado:
                # Adiciona metadata adicional do Django
                resultado["backend"] = "django-gateway"
                resultado["timestamp"] = resultado.get("timestamp", datetime.now().isoformat())
                return Response(resultado, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar serviço de analytics"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
        except Exception as e:
            logger.error(f"Erro em AnalyticsDashboardCompletoView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# *******************************************#
#********** Boleto FedBnk ********#
# *******************************************# 
class CancelarBoletoFedBnkView(APIView):
    """Cancela boleto(s) no sistema do FedBnk"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """
        Payload esperado:
        {
            "metodo": "INDIVIDUAL" ou "TODOS",
            "fatura": "167455",  # obrigatório
            "documento": "0001482774",  # opcional - para INDIVIDUAL
            "motivo": "motivo do cancelamento",
            "mail": "email@exemplo.com"
        }
        """
        try:
            data = request.data
            metodo = data.get("metodo")
            fatura = data.get("fatura")
            documento = data.get("documento")
            motivo = data.get("motivo", f"Cancelamento solicitado por {request.user.email}")
            mail = data.get("mail", request.user.email)
            
            if not fatura:
                return Response(
                    {"sucesso": False, "erro": "Número da fatura é obrigatório"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not metodo:
                return Response(
                    {"sucesso": False, "erro": "Metodo (INDIVIDUAL ou TODOS) é obrigatório"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Cancelamento {metodo} - Fatura: {fatura}, Documento: {documento}")
            
            # Payload para o FedHub (sempre com fatura, documento pode ser None)
            payload = {
                "fatura": fatura,
                "documento": documento if metodo == "INDIVIDUAL" else None,
                "motivo": motivo,
                "mail": mail
            }
            
            # Chamar o FedhubService
            service = FedhubService()
            resultado = service.cancelar_boleto_fedbnk(payload)
            
            if resultado and resultado.get("status") == "sucesso":
                return Response({
                    "sucesso": True,
                    "status": "success",
                    "message": resultado.get("message", "Cancelamento realizado com sucesso"),
                    "resultado": resultado.get("dados")
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "sucesso": False,
                    "status": "error",
                    "message": resultado.get("message", "Erro no cancelamento") if resultado else "Erro desconhecido"
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Erro no cancelamento: {str(e)}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
            
