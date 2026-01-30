# import logging
# from rest_framework import generics, status
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.views import APIView
# from rest_framework_simplejwt.authentication import JWTAuthentication
# import requests
# import json

# from consultas.services.firebird_service import FirebirdService
# from consultas.utils.renderers import BinaryRenderer
# from .serializers import ConsultaRequestSerializer, HistoricoConsultaSerializer
# from .models import HistoricoConsulta
# from .integrations import ConsultaCEP, ConsultaCPF, ConsultaCNPJ
# from django.contrib.auth import get_user_model
# from rest_framework.pagination import PageNumberPagination

# import pandas as pd
# from io import BytesIO
# from django.http import HttpResponse
# from datetime import datetime

# from reportlab.lib.pagesizes import A4
# from reportlab.pdfgen import canvas
# from reportlab.lib.units import cm

# logger = logging.getLogger(__name__)

# class RealizarConsultaView(APIView):

#     authentication_classes = [JWTAuthentication]

#     permission_classes = [IsAuthenticated]

#     def post(self, request, *args, **kwargs):
#         # Instancia o serializer com os dados da requisição.
#         # O ConsultaRequestSerializer é responsável por validar e processar
#         # os dados de entrada, incluindo a conversão de JSON strings para dicionários Python
#         # para tipos de consulta como 'cpf_alternativa', 'cnpj_razao_social' e 'cep_rua_cidade'.
#         serializer = ConsultaRequestSerializer(data=request.data)

#         # Valida os dados da requisição. Se houver erros, retorna 400 Bad Request.
#         if serializer.is_valid():
#             # Extrai os dados validados do serializer.
#             tipo_consulta = serializer.validated_data["tipo_consulta"]
#             # 'parametro_consulta_processed' será uma string (CPF, CNPJ, CEP)
#             # ou um dicionário Python (para consultas alternativas com JSON).
#             parametro_consulta_processed = serializer.validated_data[
#                 "parametro_consulta"
#             ]

#             # Campos opcionais com valores padrão.
#             origem = serializer.validated_data.get("origem", "manual")
#             lote_id = serializer.validated_data.get("lote_id", None)

#             resultado_api = (
#                 None  # Variável para armazenar o resultado retornado pela API externa.
#             )
#             parametro_consulta_para_historico = ""  # Variável para o valor a ser salvo no campo `parametro_consulta` do modelo HistoricoConsulta.

#             try:
#                 # Lógica condicional para chamar a função de integração correta
#                 # baseada no 'tipo_consulta' e processar o 'parametro_consulta_processed'.

#                 if tipo_consulta == "endereco":  # Consulta de CEP simples (BrasilAPI)
#                     parametro_consulta_para_historico = (
#                         parametro_consulta_processed  # Já é o CEP limpo
#                     )
#                     resultado_api = ConsultaCEP.consultar(parametro_consulta_processed)

#                 elif tipo_consulta == "cpf":  # Consulta de CPF simples (BigDataCorp)
#                     parametro_consulta_para_historico = (
#                         parametro_consulta_processed  # Já é o CPF limpo
#                     )
#                     resultado_api = ConsultaCPF.consultar(parametro_consulta_processed)

#                 elif tipo_consulta == "cnpj":  # Consulta de CNPJ simples (BrasilAPI)
#                     parametro_consulta_para_historico = (
#                         parametro_consulta_processed  # Já é o CNPJ limpo
#                     )
#                     resultado_api = ConsultaCNPJ.consultar(parametro_consulta_processed)

#                 elif (
#                     tipo_consulta == "cpf_alternativa"
#                 ):  # Consulta de CPF por chaves alternativas (BigDataCorp)
#                     # Para salvar no histórico, o dicionário precisa ser convertido de volta para JSON string.
#                     parametro_consulta_para_historico = json.dumps(
#                         parametro_consulta_processed
#                     )
#                     # Passa o dicionário Python para a função de integração.
#                     resultado_api = ConsultaCPF.consultar_cpf_alternativa(
#                         parametro_consulta_processed
#                     )

#                 elif (
#                     tipo_consulta == "cnpj_razao_social"
#                 ):  # Consulta de CNPJ por Razão Social/Nome (BigDataCorp)
#                     # Para salvar no histórico, o dicionário precisa ser convertido de volta para JSON string.
#                     parametro_consulta_para_historico = json.dumps(
#                         parametro_consulta_processed
#                     )
#                     # Passa o dicionário Python para a função de integração.
#                     resultado_api = ConsultaCNPJ.consultar_por_razao_social_bigdatacorp(
#                         parametro_consulta_processed
#                     )

#                 elif (
#                     tipo_consulta == "cep_rua_cidade"
#                 ):  # Consulta de CEP por Rua e Cidade (ViaCEP)
#                     # Para salvar no histórico, o dicionário precisa ser convertido de volta para JSON string.
#                     parametro_consulta_para_historico = json.dumps(
#                         parametro_consulta_processed
#                     )
#                     # Passa o dicionário Python (contendo 'estado', 'cidade', 'logradouro') para a função de integração.
#                     resultado_api = ConsultaCEP.consultar_por_rua_e_cidade(
#                         parametro_consulta_processed
#                     )

#                 else:
#                     # Caso um 'tipo_consulta' inválido passe pela validação (o que não deveria ocorrer com ChoiceField)
#                     return Response(
#                         {"detail": "Tipo de consulta inválido."},
#                         status=status.HTTP_400_BAD_REQUEST,
#                     )

#                 # Salva o histórico da consulta no banco de dados.
#                 historico = HistoricoConsulta.objects.create(
#                     usuario=request.user,  # O usuário logado que realizou a consulta.
#                     tipo_consulta=tipo_consulta,
#                     parametro_consulta=parametro_consulta_para_historico,  # O valor (string ou JSON string) a ser salvo.
#                     resultado=resultado_api,  # O resultado JSON completo da API externa.
#                     origem=origem,
#                     lote_id=lote_id,
#                 )

#                 # Serializa o objeto de histórico salvo para a resposta da API.
#                 historico_serializer = HistoricoConsultaSerializer(historico)

#                 # Retorna uma resposta de sucesso com os detalhes da consulta e o histórico salvo.
#                 return Response(
#                     {
#                         "mensagem": "Consulta realizada com sucesso.",
#                         "resultado_api": resultado_api,
#                         "historico_salvo": historico_serializer.data,
#                         "origem": origem,  # Inclui a origem na resposta
#                     },
#                     status=status.HTTP_200_OK,
#                 )

#             except ValueError as e:
#                 # Captura erros de validação de negócio ou erros específicos da camada de integração.
#                 # Ex: "CEP não encontrado.", "CPF inválido."
#                 return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
#             except requests.exceptions.RequestException as e:
#                 # Captura erros de comunicação com APIs externas (problemas de rede, timeouts, etc.).
#                 return Response(
#                     {"detail": f"Erro de comunicação com a API externa: {str(e)}"},
#                     status=status.HTTP_503_SERVICE_UNAVAILABLE,  # Service Unavailable indica que o serviço externo está indisponível
#                 )
#             except Exception as e:
#                 # Captura qualquer outro erro inesperado que possa ocorrer.
#                 # É crucial logar esses erros para depuração em produção.
#                 print(f"Erro inesperado na RealizarConsultaView: {e}")
#                 return Response(
#                     {"detail": f"Erro interno ao processar consulta: {str(e)}"},
#                     status=status.HTTP_500_INTERNAL_SERVER_ERROR,  # Internal Server Error para erros não previstos.
#                 )

#         # Se o serializer não for válido (erros de validação de entrada).
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# # --- View para Listar o Histórico de Consultas ---
# class StandardResultsPagination(PageNumberPagination):
#     page_size = 10  # Deve ser o mesmo que intensPorPagina no frontend
#     page_size_query_param = "page_size"
#     max_page_size = 100


# class HistoricoConsultaListView(generics.ListAPIView):

#     serializer_class = HistoricoConsultaSerializer
#     permission_classes = [IsAuthenticated]
#     authentication_classes = [JWTAuthentication]

#     def get_queryset(self):

#         user = self.request.user
#         if user.is_authenticated:
#             # Admins podem ver todo o histórico.
#             if hasattr(user, "nivel_acesso") and user.nivel_acesso == "admin":
#                 return HistoricoConsulta.objects.all().order_by("-data_consulta")
#             else:
#                 # Usuários comuns veem apenas seu próprio histórico.
#                 return HistoricoConsulta.objects.filter(usuario=user).order_by(
#                     "-data_consulta"
#                 )
#         return (
#             HistoricoConsulta.objects.none()
#         )  # Retorna queryset vazia se não autenticado.


# # --- View para Detalhes de uma Consulta Específica no Histórico ---
# class HistoricoConsultaDetailView(generics.RetrieveAPIView):
#     queryset = HistoricoConsulta.objects.all()
#     serializer_class = HistoricoConsultaSerializer
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]

#     def get_object(self):
#         queryset = self.get_queryset()
#         # Tenta obter o objeto pelo PK (ID) fornecido na URL.
#         obj = generics.get_object_or_404(queryset, pk=self.kwargs["pk"])

#         user = self.request.user
#         # Admins podem ver qualquer consulta.
#         if hasattr(user, "nivel_acesso") and user.nivel_acesso == "admin":
#             return obj
#         # Usuários comuns só podem ver suas próprias consultas.
#         elif obj.usuario == user:
#             return obj
#         else:
#             # Se o usuário não tem permissão para acessar a consulta.
#             self.permission_denied(
#                 self.request,
#                 message="Você não tem permissão para acessar esta consulta.",
#             )


# # --- View para Listar o Histórico de Consultas de um Usuário Específico (Geralmente para Admins) ---
# class HistoricoConsultaUserListView(generics.ListAPIView):
#     serializer_class = HistoricoConsultaSerializer
#     authentication_classes = [JWTAuthentication, JWTAuthentication]
#     permission_classes = [
#         IsAuthenticated
#     ]  # Adicionado IsOwnerOrAdmin para restringir acesso

#     def get_queryset(self):
#         # Apenas admins devem ter acesso a esta view para buscar histórico de outros usuários.
#         # A permissão 'IsOwnerOrAdmin' deve lidar com isso.

#         user_id = self.kwargs["user_id"]  # Obtém o ID do usuário da URL.
#         User = get_user_model()  # Obtém o modelo de usuário customizado.

#         try:
#             target_user = User.objects.get(
#                 pk=user_id
#             )  # Tenta encontrar o usuário pelo ID.
#         except User.DoesNotExist:
#             return (
#                 HistoricoConsulta.objects.none()
#             )  # Retorna vazio se o usuário não existir.

#         # Retorna o histórico de consultas para o usuário alvo.
#         return HistoricoConsulta.objects.filter(usuario=target_user).order_by(
#             "-data_consulta"
#         )

# # Buscar Fatura por Numero da Fatura
# class BuscarFaturaPorNumero(APIView):
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]
    
#     def get(self, request, numero_fatura: str, *args, **kwargs):
#         service = FirebirdService()
#         dados = service.buscar_fatura_por_numero(numero_fatura)

#         if not dados:
#             return Response(
#                 {"sucesso": False, "erro": "Fatura não encontrada"},
#                 status=404
#             )

#         return Response({
#             "sucesso": True,
#             "data": dados
#         })

# # Buscar Fatura por parametros - QUERY APENAS NA TABELA 'FATURAS'
# class BuscarFaturaDinamicamente(APIView):
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]

#     def get(self, request, *args, **kwargs):
#         service = FirebirdService()
        
#         logger.info(f"Parâmetros da requisição: {request.query_params}")

#         filtros = {
#             "fatura": request.query_params.get("fatura"),
#             "apolice": request.query_params.get("apolice"),
#             "administradora": request.query_params.get("administradora"),
#             "seguradora": request.query_params.get("seguradora"),
#             "status": request.query_params.get("status"),
#             "ramo": request.query_params.get("ramo"),
#             "data_ini": request.query_params.get("data_ini"),
#             "data_fim": request.query_params.get("data_fim"),
#             "valor_min": request.query_params.get("valor_min"),
#             "valor_max": request.query_params.get("valor_max"),
#             "limit": request.query_params.get("limit", 100),
#             "offset": request.query_params.get("offset", 0),
#         }

#         # Remover filtros vazios
#         filtros_limpos = {k: v for k, v in filtros.items() if v not in [None, "", "null"]}
#         logger.info(f"Filtros limpos: {filtros_limpos}")

#         try:
#             dados = service.buscar_fatura_dinamicamente(filtros_limpos)
#             logger.info(f"Dados retornados do Firebird: {dados}")

#             if not dados:
#                 return Response(
#                     {
#                         "sucesso": False,
#                         "erro": "Nenhuma fatura encontrada com os filtros informados",
#                         "resultado": []
#                     },
#                     status=status.HTTP_404_NOT_FOUND
#                 )

#             # Verificar estrutura dos dados retornados
#             if isinstance(dados, dict):
#                 # Se for um dicionário, verificar se tem estrutura específica
#                 if "status" in dados and dados["status"] == "success":
#                     resultado = dados.get("data", [])
                    
#                     # Garantir que seja uma lista
#                     if not isinstance(resultado, list):
#                         resultado = [resultado] if resultado else []
                        
#                     return Response(
#                         {
#                             "sucesso": True,
#                             "resultado": {
#                                 "data": resultado,
#                                 "total": len(resultado)
#                             }
#                         },
#                         status=status.HTTP_200_OK
#                     )
#                 else:
#                     # Retornar lista vazia
#                     return Response(
#                         {
#                             "sucesso": True,
#                             "resultado": {
#                                 "data": [],
#                                 "total": 0
#                             }
#                         },
#                         status=status.HTTP_200_OK
#                     )
#             elif isinstance(dados, list):
#                 # Já é uma lista
#                 return Response(
#                     {
#                         "sucesso": True,
#                         "resultado": {
#                             "data": dados,
#                             "total": len(dados)
#                         }
#                     },
#                     status=status.HTTP_200_OK
#                 )
#             else:
#                 # Converter qualquer outro tipo para lista
#                 return Response(
#                     {
#                         "sucesso": True,
#                         "resultado": {
#                             "data": [dados] if dados else [],
#                             "total": 1 if dados else 0
#                         }
#                     },
#                     status=status.HTTP_200_OK
#                 )

#         except Exception as e:
#             logger.error(f"Erro ao buscar fatura dinamicamente: {str(e)}")
#             return Response(
#                 {
#                     "sucesso": False,
#                     "erro": f"Erro interno ao processar consulta: {str(e)}",
#                     "resultado": []
#                 },
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
            
# # Buscar Fatura por parametros - QUERY NAS TABELAS 'FATURAS' + 'BOLETOS'
# class BuscarFaturasComBoletos(APIView):
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]

#     def get(self, request, *args, **kwargs):
#         service = FirebirdService()
        
#         logger.info(f"Parâmetros da requisição de faturas com boletos: {request.query_params}")

#         # Coletar todos os parâmetros possíveis
#         filtros = {
#             "fatura": request.query_params.get("fatura"),
#             "apolice": request.query_params.get("apolice"),
#             "administradora": request.query_params.get("administradora"),
#             "status": request.query_params.get("status"),
#             "data_ini": request.query_params.get("data_ini"),
#             "data_fim": request.query_params.get("data_fim"),
#             "limit": request.query_params.get("limit", 200),
#             "offset": request.query_params.get("offset", 0),
#         }

#         # Remover filtros vazios
#         filtros_limpos = {k: v for k, v in filtros.items() if v not in [None, "", "null"]}
#         logger.info(f"Filtros limpos para faturas com boletos: {filtros_limpos}")

#         try:
#             # Aqui você precisa criar um novo método no FirebirdService
#             # ou usar o base_url diretamente para a nova rota
#             dados = service.buscar_faturas_com_boletos(filtros_limpos)
#             logger.info(f"Dados retornados do serviço de faturas com boletos: {dados}")

#             if dados.get("status") != "success":
#                 return Response(
#                     {
#                         "sucesso": False,
#                         "erro": dados.get("message", "Erro ao buscar faturas"),
#                         "resultado": []
#                     },
#                     status=status.HTTP_404_NOT_FOUND
#                 )

#             return Response(
#                 {
#                     "sucesso": True,
#                     "resultado": {
#                         "data": dados.get("data", []),
#                         "total": dados.get("total", 0),
#                         "total_registros": dados.get("total_registros", 0),
#                         "has_more": dados.get("has_more", False),
#                         "limit": dados.get("limit", 200),
#                         "offset": dados.get("offset", 0),
#                         "filters": dados.get("filters", {})
#                     }
#                 },
#                 status=status.HTTP_200_OK
#             )

#         except requests.RequestException as e:
#             logger.error(f"Erro de comunicação ao buscar faturas com boletos: {str(e)}")
#             return Response(
#                 {
#                     "sucesso": False,
#                     "erro": f"Erro de comunicação com o serviço de faturas: {str(e)}",
#                     "resultado": []
#                 },
#                 status=status.HTTP_503_SERVICE_UNAVAILABLE
#             )
#         except Exception as e:
#             logger.error(f"Erro inesperado ao buscar faturas com boletos: {str(e)}")
#             return Response(
#                 {
#                     "sucesso": False,
#                     "erro": f"Erro interno ao processar consulta: {str(e)}",
#                     "resultado": []
#                 },
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
            
# class ExportarFaturasComBoletosExcel(APIView):
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]
    
#     renderer_classes = [BinaryRenderer]

#     def get(self, request, *args, **kwargs):
#         service = FirebirdService()
        
#         logger.info(f"Exportação Excel - Parâmetros: {request.query_params}")

#         # Coletar parâmetros (mesmos filtros da consulta normal)
#         filtros = {
#             "fatura": request.query_params.get("fatura"),
#             "apolice": request.query_params.get("apolice"),
#             "administradora": request.query_params.get("administradora"),
#             "status": request.query_params.get("status"),
#             "data_ini": request.query_params.get("data_ini"),
#             "data_fim": request.query_params.get("data_fim"),
#             "limit": request.query_params.get("limit", 500),
#             "offset": request.query_params.get("offset", 0),
#         }

#         # Remover filtros vazios
#         filtros_limpos = {k: v for k, v in filtros.items() if v not in [None, "", "null"]}

#         try:
#             # Buscar dados do microsserviço
#             dados = service.buscar_faturas_com_boletos(filtros_limpos)
            
#             if not dados or dados.get("status") != "success":
#                 return Response(
#                     {
#                         "sucesso": False,
#                         "erro": "Nenhum dado encontrado para exportação"
#                     },
#                     status=status.HTTP_404_NOT_FOUND
#                 )

#             data_list = dados.get("data", [])
            
#             if not data_list:
#                 return Response(
#                     {
#                         "sucesso": False,
#                         "erro": "Nenhum registro encontrado com os filtros informados"
#                     },
#                     status=status.HTTP_404_NOT_FOUND
#                 )

#             # Criar DataFrame pandas
#             df = pd.DataFrame(data_list)
            
#             # Selecionar e renomear colunas importantes
#             colunas_selecionadas = [
#                 'FATURA', 'APOLICE', 'ADMINISTRADORA', 'SEGURADORA',
#                 'DATA_FAT', 'VENCIMENTO', 'STATUS', 'QUITADO',
#                 'NOME_COBRADO', 'CNPJ_COBRADO',
#                 'PREMIO_BRUTO', 'PREMIO_LIQ', 'VALOR',
#                 'DT_INI_VIG', 'DT_FIM_VIG',
#                 'NOSSO_NUMERO', 'DOCUMENTO', 'PARCELA', 'PARCELAS',
#                 'BOLETA_REC', 'BOLETA_QUITADA'
#             ]
            
#             # Manter apenas colunas que existem no DataFrame
#             colunas_disponiveis = [col for col in colunas_selecionadas if col in df.columns]
#             df = df[colunas_disponiveis]
            
#             # Renomear colunas para nomes mais amigáveis
#             mapeamento_colunas = {
#                 'FATURA': 'Nº Fatura',
#                 'APOLICE': 'Apólice',
#                 'ADMINISTRADORA': 'Administradora',
#                 'SEGURADORA': 'Seguradora',
#                 'DATA_FAT': 'Data Fatura',
#                 'VENCIMENTO': 'Vencimento',
#                 'STATUS': 'Status',
#                 'QUITADO': 'Quitado',
#                 'NOME_COBRADO': 'Tomador',
#                 'CNPJ_COBRADO': 'CNPJ',
#                 'PREMIO_BRUTO': 'Prêmio Bruto (R$)',
#                 'PREMIO_LIQ': 'Prêmio Líquido (R$)',
#                 'VALOR': 'Valor Boleto (R$)',
#                 'DT_INI_VIG': 'Início Vigência',
#                 'DT_FIM_VIG': 'Fim Vigência',
#                 'NOSSO_NUMERO': 'Nosso Número',
#                 'DOCUMENTO': 'Documento',
#                 'PARCELA': 'Parcela Atual',
#                 'PARCELAS': 'Total Parcelas',
#                 'BOLETA_REC': 'Boleta Recebida (R$)',
#                 'BOLETA_QUITADA': 'Boleta Quitada'
#             }
            
#             df.rename(columns=mapeamento_colunas, inplace=True)
            
#             # Formatar valores monetários
#             colunas_monetarias = ['Prêmio Bruto (R$)', 'Prêmio Líquido (R$)', 
#                                   'Valor Boleto (R$)', 'Boleta Recebida (R$)']
            
#             for col in colunas_monetarias:
#                 if col in df.columns:
#                     # Converter para numérico e formatar
#                     df[col] = pd.to_numeric(df[col], errors='coerce')
#                     df[col] = df[col].apply(
#                         lambda x: f'R$ {x:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.') 
#                         if pd.notnull(x) else ''
#                     )
            
#             # Formatar datas
#             colunas_datas = ['Data Fatura', 'Vencimento', 'Início Vigência', 'Fim Vigência']
            
#             for col in colunas_datas:
#                 if col in df.columns:
#                     # Converter para datetime
#                     df[col] = pd.to_datetime(df[col], errors='coerce')
#                     df[col] = df[col].dt.strftime('%d/%m/%Y')
            
#             # Ordenar por data da fatura (mais recente primeiro)
#             if 'Data Fatura' in df.columns:
#                 df = df.sort_values('Data Fatura', ascending=False)
            
#             # Criar arquivo Excel em memória
#             output = BytesIO()
            
#             # Criar Excel writer com openpyxl
#             with pd.ExcelWriter(output, engine='openpyxl') as writer:
#                 # Escrever dados principais
#                 df.to_excel(writer, sheet_name='Faturas', index=False)
                
#                 # Ajustar largura das colunas
#                 worksheet = writer.sheets['Faturas']
#                 for column in worksheet.columns:
#                     max_length = 0
#                     column_letter = column[0].column_letter
                    
#                     for cell in column:
#                         try:
#                             if len(str(cell.value)) > max_length:
#                                 max_length = len(str(cell.value))
#                         except:
#                             pass
                    
#                     adjusted_width = min(max_length + 2, 50)
#                     worksheet.column_dimensions[column_letter].width = adjusted_width
                
#                 # Adicionar uma sheet com informações do relatório
#                 info_df = pd.DataFrame({
#                     'Parâmetro': ['Data Exportação', 'Total Registros', 'Filtros Aplicados'],
#                     'Valor': [
#                         datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
#                         len(data_list),
#                         ', '.join([f'{k}: {v}' for k, v in filtros_limpos.items()]) or 'Nenhum'
#                     ]
#                 })
                
#                 info_df.to_excel(writer, sheet_name='Informações', index=False)
                
#                 # Formatar sheet de informações
#                 info_worksheet = writer.sheets['Informações']
#                 for column in info_worksheet.columns:
#                     column_letter = column[0].column_letter
#                     info_worksheet.column_dimensions[column_letter].width = 30
            
#             output.seek(0)
            
#             # Criar nome do arquivo
#             timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
#             filename = f'faturas_com_boletos_{timestamp}.xlsx'
            
#             # Retornar arquivo Excel como resposta
#             response = HttpResponse(
#                 output.getvalue(),
#                 content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
#             )
#             response['Content-Disposition'] = f'attachment; filename="{filename}"'
#             response['Access-Control-Expose-Headers'] = 'Content-Disposition'
            
#             return response

#         except Exception as e:
#             logger.error(f"Erro ao exportar para Excel: {str(e)}")
#             return Response(
#                 {
#                     "sucesso": False,
#                     "erro": f"Erro ao gerar arquivo Excel: {str(e)}"
#                 },
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
            
# class ExportarFaturasComBoletosPDF(APIView):
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]
#     renderer_classes = [BinaryRenderer]

#     def get(self, request, *args, **kwargs):
#         service = FirebirdService()

#         filtros = {
#             "fatura": request.query_params.get("fatura"),
#             "apolice": request.query_params.get("apolice"),
#             "administradora": request.query_params.get("administradora"),
#             "status": request.query_params.get("status"),
#             "data_ini": request.query_params.get("data_ini"),
#             "data_fim": request.query_params.get("data_fim"),
#             "limit": 500,
#         }

#         filtros_limpos = {k: v for k, v in filtros.items() if v}

#         dados = service.buscar_faturas_com_boletos(filtros_limpos)

#         if not dados or dados.get("status") != "success":
#             return Response({"erro": "Nenhum dado encontrado"}, status=404)

#         data_list = dados.get("data", [])

#         response = HttpResponse(content_type="application/pdf")
#         filename = f"faturas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
#         response["Content-Disposition"] = f'attachment; filename="{filename}"'
#         response["Access-Control-Expose-Headers"] = "Content-Disposition"

#         c = canvas.Canvas(response, pagesize=A4)
#         width, height = A4

#         y = height - 2 * cm

#         c.setFont("Helvetica-Bold", 12)
#         c.drawString(2 * cm, y, "Relatório de Faturas com Boletos")
#         y -= 1 * cm

#         c.setFont("Helvetica", 8)
#         c.drawString(2 * cm, y, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
#         y -= 1 * cm

#         headers = ["Fatura", "Apólice", "Status", "Vencimento", "Valor"]
#         col_x = [2, 5, 9, 12, 16]

#         c.setFont("Helvetica-Bold", 8)
#         for i, h in enumerate(headers):
#             c.drawString(col_x[i] * cm, y, h)

#         y -= 0.5 * cm
#         c.setFont("Helvetica", 8)

#         for row in data_list:
#             if y < 2 * cm:
#                 c.showPage()
#                 y = height - 2 * cm

#             c.drawString(col_x[0] * cm, y, str(row.get("FATURA", "")))
#             c.drawString(col_x[1] * cm, y, str(row.get("APOLICE", "")))
#             c.drawString(col_x[2] * cm, y, str(row.get("STATUS", "")))
#             c.drawString(col_x[3] * cm, y, str(row.get("VENCIMENTO", "")))
#             c.drawRightString(col_x[4] * cm, y, str(row.get("VALOR", "")))

#             y -= 0.4 * cm

#         c.showPage()
#         c.save()

#         return response