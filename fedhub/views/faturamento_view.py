import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from fedhub.services.faturamento_service import FaturamentoService

from django.http import HttpResponse

logger = logging.getLogger(__name__)

class BuscarFaturamento(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        service = FaturamentoService()
        
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

class TratamentoDeErroView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        Roda a procedure de tratamento de erros no FastAPI
        POST /faturamento/tratamento-de-erros/rodar-procedure/
        """
        try:
            service = FaturamentoService()
            
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
            service = FaturamentoService()
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
            
            service = FaturamentoService()
            resultado = service.processar_dados_segunda_via_boleto(fatura)
            
            if resultado is None:
                logger.error(f"Erro ao gerar segunda via do boleto para fatura {fatura}")
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Erro ao gerar segunda via do boleto"
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            dados = resultado.get("dados") or []
            sem_registro = resultado.get("sem_registro") or []

            if resultado.get("nao_encontrada"):
                return Response(
                    {"sucesso": False, "erro": f"Fatura {fatura} não encontrada ou sem boleto ativo."},
                    status=status.HTTP_404_NOT_FOUND
                )

            if not dados:
                # FedHub: nenhum boleto desta fatura foi enviado ao banco (API ou remessa)
                docs = ", ".join(b.get("documento") or "?" for b in sem_registro)
                return Response(
                    {
                        "sucesso": False,
                        "erro": (
                            f"Nenhum boleto da fatura {fatura} consta como enviado ao banco "
                            f"({len(sem_registro)} sem registro: {docs}). Não há 2ª via a emitir."
                        ),
                        "sem_registro": sem_registro,
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY
                )
            
            return Response(
                {
                    "sucesso": True,
                    "dados": dados,
                    "sem_registro": sem_registro,
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
            service = FaturamentoService()
            resultado = service.emitir_segunda_via_boleto(fatura, boletos)

            if resultado and resultado.get("status") == "rejeitado":
                # FedHub recusou o lote: boleto(s) sem registro no banco (422)
                return Response(
                    {"sucesso": False, "erro": resultado.get("erro"), "rejeitados": resultado.get("rejeitados") or []},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY
                )

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