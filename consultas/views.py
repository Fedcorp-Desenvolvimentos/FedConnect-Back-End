from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
import requests
import json
from .serializers import ConsultaRequestSerializer, HistoricoConsultaSerializer
from .models import HistoricoConsulta
from .integrations import ConsultaCEP, ConsultaCPF, ConsultaCNPJ
from users.permissions import IsOwnerOrAdmin
from django.contrib.auth import get_user_model
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, TextField
from django.db.models.functions import Cast, Coalesce


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
