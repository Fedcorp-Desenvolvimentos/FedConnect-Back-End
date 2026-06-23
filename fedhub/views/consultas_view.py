import asyncio
import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
import requests

from consultas.cache.cidade_cache import buscar_cidades_autocomplete_sync
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

