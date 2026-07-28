import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from consultas.services.fedhub_service import FedhubService

from datetime import datetime

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

            comissoes_validas = []
            for comissao in lista_comissoes:
                numero_comissao = comissao.get("voucher")
                favorecido = comissao.get("favorecido")
                if not all([numero_comissao, favorecido]):
                    logger.warning(f"Comissão ignorada devido a dados faltantes: {comissao}")
                    continue
                comissoes_validas.append({
                    "numero_comissao": comissao.get("voucher"),
                    "parcela": comissao.get("parcela"),
                    "documento": comissao.get("documento"),
                    "favorecido": favorecido,
                    "tipo_comissao": comissao.get("tipo"),
                    "voucher": comissao.get("voucher"),
                    "fatura": comissao.get("fatura"),
                    "motivo_cancelamento": comissao.get("motivo_cancelamento", "Cancelamento solicitado pelo usuário")
                })

            logger.info(f"Enviando {len(comissoes_validas)} comissões em lote para cancelamento")

            payload_fedhub = {"comissoes": comissoes_validas}
            resultado = service.cancelar_comissao(payload_fedhub)

            if resultado and resultado.get("status") == "success":
                comissoes_canceladas = resultado.get("total_canceladas", len(comissoes_validas))
            else:
                comissoes_canceladas = 0
                logger.error(f"Erro no cancelamento em lote: {resultado}")

            return Response(
                {
                    "sucesso": True,
                    "mensagem": f"{comissoes_canceladas} comissão(ões) cancelada(s) com sucesso.",
                    "total_processadas": len(lista_comissoes),
                    "total_canceladas": comissoes_canceladas,
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
