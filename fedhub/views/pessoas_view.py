import asyncio
import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from fedhub.services.pessoa_services import PessoasService
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================
# PESSOAS
# ============================================================

class BuscarPessoasView(APIView):
    """
    Busca pessoas (favorecidos)
    GET /pessoas/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            service = PessoasService()
            
            # Parâmetros de busca
            limit = request.query_params.get("limit", 20)
            search = request.query_params.get("search", "").strip()
            offset = request.query_params.get("offset", 0)

            params = {
                "status": "A",
                "limit": int(limit),
                "offset": int(offset),
            }
            
            if search:
                params["nome"] = search

            # Chama o FastAPI
            dados = service.buscar_pessoas(params)
            
            if not dados:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar pessoas"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            # Extrai dados da resposta
            data = dados.get("data") if isinstance(dados, dict) else dados
            total = dados.get("total", len(data)) if isinstance(dados, dict) else len(data) if isinstance(data, list) else 0

            return Response(
                {
                    "sucesso": True,
                    "data": data,
                    "total": total,
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Erro em BuscarPessoasView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class PessoaDetailView(APIView):
    """
    Busca e atualiza uma pessoa por código
    GET /pessoas/{codigo}/
    PUT /pessoas/{codigo}/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, codigo, *args, **kwargs):
        try:
            service = PessoasService()
            dados = service.buscar_pessoa_por_codigo(codigo)
            
            if not dados:
                return Response(
                    {"sucesso": False, "erro": "Pessoa não encontrada"},
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
            logger.error(f"Erro em PessoaDetailView.GET: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, codigo, *args, **kwargs):
        try:
            service = PessoasService()
            dados_pessoa = request.data
            
            logger.info(f"Dados recebidos para atualizar pessoa {codigo}: {dados_pessoa}")
            
            resultado = service.atualizar_pessoa(codigo, dados_pessoa)
            
            if not resultado:
                return Response(
                    {
                        "sucesso": False,
                        "erro": "Erro ao atualizar pessoa no sistema"
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            if resultado.get("status") == "timeout":
                return Response(
                    {
                        "sucesso": False,
                        "erro": resultado.get(
                            "message", "Timeout ao atualizar pessoa no FedHub"
                        ),
                    },
                    status=status.HTTP_504_GATEWAY_TIMEOUT,
                )
            
            if resultado.get("status") != "success":
                http_status = resultado.get("http_status", status.HTTP_400_BAD_REQUEST)
                return Response(
                    {
                        "sucesso": False,
                        "erro": resultado.get("message", "Erro ao atualizar pessoa")
                    },
                    status=http_status
                )
            
            return Response(
                {
                    "sucesso": True,
                    "mensagem": "Pessoa atualizada com sucesso",
                    "data": resultado.get("data", {})
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Erro em PessoaDetailView.PUT: {str(e)}", exc_info=True)
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro interno: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CriarPessoaView(APIView):
    """
    Cria uma nova pessoa (favorecido)
    POST /pessoas/criar/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            dados_pessoa = request.data
            
            if not dados_pessoa.get('nome'):
                return Response(
                    {"sucesso": False, "erro": "Campo 'nome' é obrigatório"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not dados_pessoa.get('cpf_cnpj'):
                return Response(
                    {"sucesso": False, "erro": "Campo 'cpf_cnpj' é obrigatório"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            payload = {
                'nome': dados_pessoa.get('nome', ''),
                'cpf_cnpj': dados_pessoa.get('cpf_cnpj', '').replace('.', '').replace('/', '').replace('-', ''),
                'tipo': dados_pessoa.get('tipo', 'J'),  # J ou F
                'sexo': dados_pessoa.get('sexo', 'J'),
                'data_cadastro': dados_pessoa.get('data_cadastro', datetime.now().strftime('%Y-%m-%d')),
                'cep': dados_pessoa.get('cep', '').replace('-', ''),
                'uf': dados_pessoa.get('uf', ''),
                'cidade': dados_pessoa.get('cidade', ''),
                'bairro': dados_pessoa.get('bairro', ''),
                'endereco': dados_pessoa.get('endereco', ''),
                'telefone1_ddd': dados_pessoa.get('telefone1_ddd', ''),
                'telefone1_numero': dados_pessoa.get('telefone1_numero', '').replace('-', ''),
                'telefone2_ddd': dados_pessoa.get('telefone2_ddd', ''),
                'telefone2_numero': dados_pessoa.get('telefone2_numero', '').replace('-', ''),
                'email': dados_pessoa.get('email', ''),
                'contato': dados_pessoa.get('contato', ''),
                'observacoes': dados_pessoa.get('observacoes', ''),
                'banco': dados_pessoa.get('banco', ''),
                'agencia': dados_pessoa.get('agencia', ''),
                'conta': dados_pessoa.get('conta', ''),
                'favorecido': dados_pessoa.get('favorecido', ''),
                'chave_pix': dados_pessoa.get('chave_pix', ''),
                'emite_nota_fiscal': 'S' if dados_pessoa.get('emite_nota_fiscal') else 'N',
                'melhor_dia_pagamento': dados_pessoa.get('melhor_dia_pagamento', '0'),
                'cedente': dados_pessoa.get('cedente', ''),
                'optante_simples': 'S' if dados_pessoa.get('optante_simples') else 'N',
                'possui_portal': 'S' if dados_pessoa.get('possui_portal') else 'N',
                'portal': dados_pessoa.get('portal', ''),
                'gerente_comercial': dados_pessoa.get('gerente_comercial', ''),
            }
            
            logger.info(f"Dados mapeados para criar pessoa: {payload}")
            
            service = PessoasService()
            resultado = service.criar_pessoa(payload)
            
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
            
            if resultado.get("status") != "success":
                http_status = resultado.get("http_status", status.HTTP_400_BAD_REQUEST)
                return Response(
                    {
                        "sucesso": False,
                        "erro": resultado.get("message", "Erro ao criar pessoa")
                    },
                    status=http_status
                )
            
            return Response(
                {
                    "sucesso": True,
                    "mensagem": "Pessoa criada com sucesso",
                    "data": resultado.get("data", {})
                },
                status=status.HTTP_201_CREATED
            )
            
            # return Response(
            #     {
            #         "sucesso": True,
            #         "mensagem": "Pessoa criada com sucesso",
            #         "data": payload
            #     },
            #     status=status.HTTP_201_CREATED
            # )

        except Exception as e:
            logger.error(f"Erro ao criar pessoa: {str(e)}", exc_info=True)
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Erro interno: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
            service = PessoasService()
            dados = service.buscar_pessoa_por_codigo(codigo)
            
            if not dados:
                return Response(
                    {"sucesso": False, "erro": "Pessoa não encontrada"},
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
            logger.error(f"Erro em BuscarPessoaPorCodigoView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class BuscarGerentesComerciaisView(APIView):
    """
    Busca gerentes comerciais ativos do Firebird
    GET /pessoas/gerentes-comerciais/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            service = PessoasService()
            dados = service.buscar_gerentes_comerciais()
            
            if not dados:
                return Response(
                    {"sucesso": False, "erro": "Erro ao consultar gerentes comerciais"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            
            return Response(dados, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Erro em BuscarGerentesComerciaisView: {e}")
            return Response(
                {"sucesso": False, "erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )