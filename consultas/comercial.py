import pandas as pd
from io import BytesIO
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import HistoricoConsulta
from .serializers import (
    HistoricoConsultaSerializer,
    BulkCnpjRequestSerializer,
    ConsultaRequestSerializer,
)  # Importe o novo serializador
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
import requests
import os
import re
from django.http import FileResponse
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser
from concurrent.futures import ThreadPoolExecutor, as_completed


def consulta_comercial(cnpj):

    url = settings.ALT_CNPJ_URL

    access_token = os.environ.get("BIGDATA_ACCESS_TOKEN")
    token_id = os.environ.get("BIGDATA_TOKEN_ID")

    if not access_token or not token_id:
        raise ValueError(
            "As credenciais da BigDataCorp (BIGDATA_ACCESS_TOKEN e BIGDATA_TOKEN_ID) não estão configuradas nas variáveis de ambiente."
        )

    payload = {"q": f"doc{{{cnpj}}}", "Datasets": "relationships"}
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "AccessToken": access_token,
        "TokenId": token_id,
    }

    try:

        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(
            f"Erro HTTP na API BigDataCorp: {e.response.status_code} - {e.response.text}"
        )
        raise Exception(
            f"Erro na API BigDataCorp: {e.response.status_code} - {e.response.text}"
        ) from e
    except requests.exceptions.ConnectionError as e:
        print(f"Erro de conexão com a API BigDataCorp: {e}")
        raise Exception(f"Erro de conexão com a API BigDataCorp: {e}") from e
    except requests.exceptions.Timeout as e:
        print(f"Tempo limite excedido ao conectar com a API BigDataCorp: {e}")
        raise Exception(
            f"Tempo limite excedido ao conectar com a API BigDataCorp: {e}"
        ) from e
    except requests.exceptions.RequestException as e:
        print(f"Erro inesperado na requisição para a API BigDataCorp: {e}")
        raise Exception(
            f"Erro inesperado na requisição para a API BigDataCorp: {e}"
        ) from e


class ConsultaComercialAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = self.request.user

        if not user.is_authenticated:
            return Response(
                {
                    "detail": "Você precisa estar autenticado para acessar esta consulta."
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not (
            hasattr(user, "nivel_acesso")
            and (user.nivel_acesso == "admin" or user.nivel_acesso == "comercial")
        ):
            return Response(
                {
                    "detail": "Este usuário não possui nível de acesso para esta consulta."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            serializer = ConsultaRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            tipo_consulta = serializer.validated_data["tipo_consulta"]
            parametro_consulta_valor = serializer.validated_data["parametro_consulta"]
            origem = serializer.validated_data.get("origem", "manual")
            lote_id = serializer.validated_data.get("lote_id", None)

            if tipo_consulta.lower() != "cnpj_comercial":
                return Response(
                    {
                        "detail": "Neste endpoint, apenas consultas de Comercial são permitidas."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            resultado_api = consulta_comercial(parametro_consulta_valor)

            historico = HistoricoConsulta.objects.create(
                usuario=user,
                tipo_consulta=tipo_consulta,
                parametro_consulta=parametro_consulta_valor,
                resultado=resultado_api,
                origem=origem,
                lote_id=lote_id,
            )
            historico_serializer = HistoricoConsultaSerializer(historico)

            return Response(
                {
                    "mensagem": "Consulta de CNPJ realizada com sucesso.",
                    "resultado_api": resultado_api,
                    "historico_salvo": historico_serializer.data,
                    "origem": "manual",
                    "lote_id": None,
                },
                status=status.HTTP_200_OK,
            )
        except ValueError as ve:
            print(f"Erro de validação/configuração: {ve}")
            return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Erro inesperado na consulta comercial de CNPJ: {e}")
            return Response(
                {
                    "detail": f"Ocorreu um erro ao processar a consulta de CNPJ: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


def consulta_comercial_CPF(CPF):

    url = settings.CPF_URL

    access_token = os.environ.get("BIGDATA_ACCESS_TOKEN")
    token_id = os.environ.get("BIGDATA_TOKEN_ID")

    if not access_token or not token_id:
        raise ValueError(
            "As credenciais da BigDataCorp (BIGDATA_ACCESS_TOKEN e BIGDATA_TOKEN_ID) não estão configuradas nas variáveis de ambiente."
        )

    payload = {"q": f"doc{{{CPF}}}", "Datasets": "registration_data"}
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "AccessToken": access_token,
        "TokenId": token_id,
    }

    try:

        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(
            f"Erro HTTP na API BigDataCorp: {e.response.status_code} - {e.response.text}"
        )
        raise Exception(
            f"Erro na API BigDataCorp: {e.response.status_code} - {e.response.text}"
        ) from e
    except requests.exceptions.ConnectionError as e:
        print(f"Erro de conexão com a API BigDataCorp: {e}")
        raise Exception(f"Erro de conexão com a API BigDataCorp: {e}") from e
    except requests.exceptions.Timeout as e:
        print(f"Tempo limite excedido ao conectar com a API BigDataCorp: {e}")
        raise Exception(
            f"Tempo limite excedido ao conectar com a API BigDataCorp: {e}"
        ) from e
    except requests.exceptions.RequestException as e:
        print(f"Erro inesperado na requisição para a API BigDataCorp: {e}")
        raise Exception(
            f"Erro inesperado na requisição para a API BigDataCorp: {e}"
        ) from e


class ConsultaContatoComercialAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = self.request.user

        if not user.is_authenticated:
            return Response(
                {
                    "detail": "Você precisa estar autenticado para acessar esta consulta."
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not (
            hasattr(user, "nivel_acesso")
            and (user.nivel_acesso == "admin" or user.nivel_acesso == "comercial")
        ):
            return Response(
                {
                    "detail": "Este usuário não possui nível de acesso para esta consulta."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            serializer = ConsultaRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            tipo_consulta = serializer.validated_data["tipo_consulta"]
            parametro_consulta_valor = serializer.validated_data["parametro_consulta"]
            origem = serializer.validated_data.get("origem", "manual")
            lote_id = serializer.validated_data.get("lote_id", None)

            if tipo_consulta.lower() != "comercial":
                return Response(
                    {
                        "detail": "Neste endpoint, apenas consultas de Comercial são permitidas."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            resultado_api = consulta_comercial_CPF(parametro_consulta_valor)

            historico = HistoricoConsulta.objects.create(
                usuario=user,
                tipo_consulta=tipo_consulta,
                parametro_consulta=parametro_consulta_valor,
                resultado=resultado_api,
                origem=origem,
                lote_id=lote_id,
            )
            historico_serializer = HistoricoConsultaSerializer(historico)

            return Response(
                {
                    "mensagem": "Consulta de contato comercial realizada com sucesso.",
                    "resultado_api": resultado_api,
                    "historico_salvo": historico_serializer.data,
                    "origem": "manual",
                    "lote_id": None,
                },
                status=status.HTTP_200_OK,
            )
        except ValueError as ve:
            print(f"Erro de validação/configuração: {ve}")
            return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Erro inesperado na consulta comercial de CNPJ: {e}")
            return Response(
                {
                    "detail": f"Ocorreu um erro ao processar a consulta de CNPJ: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


##### MASSA ###########
def clean_doc_number(doc):
    """Remove caracteres não numéricos de CNPJ/CPF."""
    return re.sub(r"\D", "", doc)


class BulkConsultaComercialAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = self.request.user

        if not user.is_authenticated:
            return Response(
                {
                    "detail": "Você precisa estar autenticado para acessar esta consulta em massa."
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not (
            hasattr(user, "nivel_acesso")
            and (user.nivel_acesso == "admin" or user.nivel_acesso == "comercial")
        ):
            return Response(
                {
                    "detail": "Este usuário não possui nível de acesso para esta consulta em massa."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BulkCnpjRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        cnpjs_to_process = serializer.validated_data["cnpjs"]

        all_cpf_data = []  # Para coletar todos os dados de CPF para a planilha final

        for cnpj_raw in cnpjs_to_process:
            cnpj = clean_doc_number(cnpj_raw)
            cnpj_razao_social = "N/A"  # Inicializa aqui para cada CNPJ

            if not cnpj:
                all_cpf_data.append(
                    {
                        "CNPJ Original": cnpj_raw,
                        "Razão Social CNPJ": cnpj_razao_social,
                        "CPF": "N/A",
                        "Nome Relacionado ao CNPJ": "N/A",
                        "Tipo de Relacionamento (CNPJ)": "N/A",
                        "Nome do Relacionamento (CNPJ)": "N/A",
                        "Nome do CPF (Consulta Detalhada)": "N/A",
                        "Data Nascimento CPF (Consulta Detalhada)": "N/A",
                        "Email Principal (Consulta Detalhada)": "N/A",
                        "Email Secundário (Consulta Detalhada)": "N/A",
                        "Telefone Principal (Consulta Detalhada)": "N/A",
                        "Telefone Secundário (Consulta Detalhada)": "N/A",
                        "Endereço Principal (Consulta Detalhada)": "N/A",
                        "Endereço Secundário (Consulta Detalhada)": "N/A",
                        "Status Consulta CPF": "Erro CNPJ",
                        "Detalhes Consulta CPF": "CNPJ inválido ou vazio após limpeza.",
                    }
                )
                continue

            try:
                # 1. Consulta do CNPJ para Relacionamentos (sua BigDataCorp atual)
                cnpj_relacionamentos_result = consulta_comercial(cnpj)

                # Salvar histórico da consulta CNPJ (relacionamentos)
                HistoricoConsulta.objects.create(
                    usuario=user,
                    tipo_consulta="cnpj_comercial_relacionamentos",  # Nome mais específico
                    parametro_consulta=cnpj,
                    resultado=cnpj_relacionamentos_result,
                    origem="massa",
                    lote_id=None,
                )

                # 2. NOVA CONSULTA: Para obter a Razão Social da BrasilAPI
                try:
                    brasilapi_cnpj_url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
                    brasilapi_response = requests.get(brasilapi_cnpj_url, timeout=10)
                    brasilapi_response.raise_for_status()  # Levanta HTTPError para 4xx/5xx
                    brasilapi_data = brasilapi_response.json()

                    cnpj_razao_social = brasilapi_data.get("razao_social", "N/A")

                    # Salvar histórico da consulta BrasilAPI (opcional, pode gerar muitos logs/custo se não for de interesse)
                    HistoricoConsulta.objects.create(
                        usuario=user,
                        tipo_consulta="cnpj_brasilapi_razaosocial",
                        parametro_consulta=cnpj,
                        resultado=brasilapi_data,  # Salva o retorno completo da BrasilAPI
                        origem="massa",
                        lote_id=None,
                    )

                except requests.exceptions.RequestException as brasilapi_err:
                    print(f"Erro ao consultar BrasilAPI CNPJ {cnpj}: {brasilapi_err}")
                    cnpj_razao_social = "Erro BrasilAPI"
                except Exception as e:
                    print(f"Erro inesperado ao processar BrasilAPI CNPJ {cnpj}: {e}")
                    cnpj_razao_social = "Erro inesperado BrasilAPI"

                # 3. Extrair CPFs dos relacionamentos (usando cnpj_relacionamentos_result)
                cpfs_for_consult = []
                if (
                    cnpj_relacionamentos_result
                    and "Result" in cnpj_relacionamentos_result
                    and cnpj_relacionamentos_result["Result"]
                ):
                    data_entry = cnpj_relacionamentos_result["Result"][0]
                    if "Relationships" in data_entry and isinstance(
                        data_entry["Relationships"], dict
                    ):
                        all_relationships = data_entry["Relationships"].get(
                            "CurrentRelationships", []
                        )

                        for relationship in all_relationships:
                            relationship_type = relationship.get("RelationshipType")
                            entity_tax_id_type = relationship.get(
                                "RelatedEntityTaxIdType"
                            )
                            entity_tax_id_number = relationship.get(
                                "RelatedEntityTaxIdNumber"
                            )

                            display_relationship_type = (
                                relationship_type.capitalize()
                                if relationship_type
                                else "N/A"
                            )

                            if (
                                relationship_type
                                and relationship_type.upper()
                                in ["QSA", "OWNERSHIP", "REPRESENTANTELEGAL"]
                                and entity_tax_id_type
                                and entity_tax_id_type.upper() == "CPF"
                                and entity_tax_id_number
                            ):

                                cleaned_cpf = clean_doc_number(entity_tax_id_number)

                                if len(cleaned_cpf) == 11:
                                    cpfs_for_consult.append(
                                        {
                                            "cpf": cleaned_cpf,
                                            "related_entity_name": relationship.get(
                                                "RelatedEntityName", "N/A"
                                            ),
                                            "relationship_name": relationship.get(
                                                "RelationshipName", "N/A"
                                            ),
                                            "relationship_type": display_relationship_type,
                                        }
                                    )

                if not cpfs_for_consult:
                    all_cpf_data.append(
                        {
                            "CNPJ Original": cnpj_raw,
                            "Razão Social CNPJ": cnpj_razao_social,  # Usando a razão social obtida da BrasilAPI
                            "CPF": "N/A",
                            "Nome Relacionado ao CNPJ": "N/A",
                            "Tipo de Relacionamento (CNPJ)": "N/A",
                            "Nome do Relacionamento (CNPJ)": "N/A",
                            "Nome do CPF (Consulta Detalhada)": "N/A",
                            "Data Nascimento CPF (Consulta Detalhada)": "N/A",
                            "Email Principal (Consulta Detalhada)": "N/A",
                            "Email Secundário (Consulta Detalhada)": "N/A",
                            "Telefone Principal (Consulta Detalhada)": "N/A",
                            "Telefone Secundário (Consulta Detalhada)": "N/A",
                            "Endereço Principal (Consulta Detalhada)": "N/A",
                            "Endereço Secundário (Consulta Detalhada)": "N/A",
                            "Status Consulta CPF": "Aviso",
                            "Detalhes Consulta CPF": "Nenhum CPF relevante encontrado para este CNPJ ou não se enquadra nos tipos de relacionamento relevantes (QSA, Ownership, REPRESENTANTELEGAL).",
                        }
                    )

                for cpf_info in cpfs_for_consult:
                    cpf = cpf_info["cpf"]

                    cpf_detailed_name = "N/A"
                    cpf_detailed_birthdate = "N/A"
                    cpf_email_primary = "N/A"
                    cpf_email_secondary = "N/A"
                    cpf_phone_primary = "N/A"
                    cpf_phone_secondary = "N/A"
                    cpf_address_primary = "N/A"
                    cpf_address_secondary = "N/A"
                    cpf_status = "Erro"
                    cpf_details = "Erro desconhecido ao consultar CPF."

                    try:
                        # Consulta do CPF (sua BigDataCorp atual)
                        cpf_result = consulta_comercial_CPF(cpf)

                        # Salvar histórico da consulta CPF
                        HistoricoConsulta.objects.create(
                            usuario=user,
                            tipo_consulta="comercial",
                            parametro_consulta=cpf,
                            resultado=cpf_result,
                            origem="massa",
                            lote_id=None,
                        )

                        if (
                            cpf_result
                            and "Result" in cpf_result
                            and cpf_result["Result"]
                        ):
                            cpf_data_entry = cpf_result["Result"][0]
                            registration_data = cpf_data_entry.get(
                                "RegistrationData", {}
                            )
                            basic_data = registration_data.get("BasicData", {})
                            emails_data = registration_data.get("Emails", {})
                            phones_data = registration_data.get("Phones", {})
                            addresses_data = registration_data.get("Addresses", {})

                            # Dados Básicos
                            cpf_detailed_name = basic_data.get("Name", "N/A")
                            birth_date_str = basic_data.get("BirthDate", "N/A")
                            if birth_date_str != "N/A":
                                try:
                                    cpf_detailed_birthdate = pd.to_datetime(
                                        birth_date_str
                                    ).strftime("%d/%m/%Y")
                                except ValueError:
                                    cpf_detailed_birthdate = birth_date_str
                            else:
                                cpf_detailed_birthdate = "N/A"

                            # Emails
                            if "Primary" in emails_data:
                                cpf_email_primary = emails_data["Primary"].get(
                                    "EmailAddress", "N/A"
                                )
                            if "Secondary" in emails_data:
                                cpf_email_secondary = emails_data["Secondary"].get(
                                    "EmailAddress", "N/A"
                                )

                            # Telefones
                            if "Primary" in phones_data:
                                p_phone = phones_data["Primary"]
                                cpf_phone_primary = f"+{p_phone.get('CountryCode', '')} ({p_phone.get('AreaCode', '')}) {p_phone.get('Number', '')}".strip()
                                if cpf_phone_primary == "+ ()":
                                    cpf_phone_primary = "N/A"
                            if "Secondary" in phones_data:
                                s_phone = phones_data["Secondary"]
                                cpf_phone_secondary = f"+{s_phone.get('CountryCode', '')} ({s_phone.get('AreaCode', '')}) {s_phone.get('Number', '')}".strip()
                                if cpf_phone_secondary == "+ ()":
                                    cpf_phone_secondary = "N/A"

                            # Endereços
                            if "Primary" in addresses_data:
                                p_address = addresses_data["Primary"]
                                cpf_address_primary = f"{p_address.get('Typology', '')} {p_address.get('AddressMain', '')}, {p_address.get('Number', '')} {p_address.get('Complement', '')} - {p_address.get('Neighborhood', '')}, {p_address.get('City', '')}/{p_address.get('State', '')} - {p_address.get('ZipCode', '')}".strip()
                                cpf_address_primary = re.sub(
                                    r"\s+", " ", cpf_address_primary
                                )
                                cpf_address_primary = re.sub(
                                    r"(\s*,\s*){2,}", ", ", cpf_address_primary
                                )
                                cpf_address_primary = re.sub(
                                    r"(\s*-\s*){2,}", " - ", cpf_address_primary
                                )
                                if cpf_address_primary.strip() == ", - , / -":
                                    cpf_address_primary = "N/A"
                            if "Secondary" in addresses_data:
                                s_address = addresses_data["Secondary"]
                                cpf_address_secondary = f"{s_address.get('Typology', '')} {s_address.get('AddressMain', '')}, {s_address.get('Number', '')} {s_address.get('Complement', '')} - {s_address.get('Neighborhood', '')}, {s_address.get('City', '')}/{s_address.get('State', '')} - {s_address.get('ZipCode', '')}".strip()
                                cpf_address_secondary = re.sub(
                                    r"\s+", " ", cpf_address_secondary
                                )
                                cpf_address_secondary = re.sub(
                                    r"(\s*,\s*){2,}", ", ", cpf_address_secondary
                                )
                                cpf_address_secondary = re.sub(
                                    r"(\s*-\s*){2,}", " - ", cpf_address_secondary
                                )
                                if cpf_address_secondary.strip() == ", - , / -":
                                    cpf_address_secondary = "N/A"

                            cpf_status = "Sucesso"
                            cpf_details = "OK"

                        else:
                            cpf_status = "Aviso"
                            cpf_details = "Resposta da consulta CPF não contém 'Result' ou está vazia."

                    except Exception as cpf_e:
                        cpf_status = "Erro"
                        cpf_details = str(cpf_e)

                    # Adicionar dados formatados para a planilha final
                    all_cpf_data.append(
                        {
                            "CNPJ Original": cnpj_raw,
                            "Razão Social CNPJ": cnpj_razao_social,  # Usando a razão social da BrasilAPI
                            "CPF": cpf,
                            "Nome Relacionado ao CNPJ": cpf_info.get(
                                "related_entity_name", "N/A"
                            ),
                            "Tipo de Relacionamento (CNPJ)": cpf_info.get(
                                "relationship_type", "N/A"
                            ),
                            "Nome do Relacionamento (CNPJ)": cpf_info.get(
                                "relationship_name", "N/A"
                            ),
                            "Nome do CPF (Consulta Detalhada)": cpf_detailed_name,
                            "Data Nascimento CPF (Consulta Detalhada)": cpf_detailed_birthdate,
                            "Email Principal (Consulta Detalhada)": cpf_email_primary,
                            "Email Secundário (Consulta Detalhada)": cpf_email_secondary,
                            "Telefone Principal (Consulta Detalhada)": cpf_phone_primary,
                            "Telefone Secundário (Consulta Detalhada)": cpf_phone_secondary,
                            "Endereço Principal (Consulta Detalhada)": cpf_address_primary,
                            "Endereço Secundário (Consulta Detalhada)": cpf_address_secondary,
                            "Status Consulta CPF": cpf_status,
                            "Detalhes Consulta CPF": cpf_details,
                        }
                    )

            except ValueError as ve:
                all_cpf_data.append(
                    {
                        "CNPJ Original": cnpj_raw,
                        "Razão Social CNPJ": cnpj_razao_social,  # Usando a razão social da BrasilAPI
                        "CPF": "N/A",
                        "Nome Relacionado ao CNPJ": "N/A",
                        "Tipo de Relacionamento (CNPJ)": "N/A",
                        "Nome do Relacionamento (CNPJ)": "N/A",
                        "Nome do CPF (Consulta Detalhada)": "N/A",
                        "Data Nascimento CPF (Consulta Detalhada)": "N/A",
                        "Email Principal (Consulta Detalhada)": "N/A",
                        "Email Secundário (Consulta Detalhada)": "N/A",
                        "Telefone Principal (Consulta Detalhada)": "N/A",
                        "Telefone Secundário (Consulta Detalhada)": "N/A",
                        "Endereço Principal (Consulta Detalhada)": "N/A",
                        "Endereço Secundário (Consulta Detalhada)": "N/A",
                        "Status Consulta CPF": "Erro CNPJ",
                        "Detalhes Consulta CPF": f"Erro de validação/configuração ao consultar CNPJ: {str(ve)}",
                    }
                )
            except Exception as e:
                all_cpf_data.append(
                    {
                        "CNPJ Original": cnpj_raw,
                        "Razão Social CNPJ": cnpj_razao_social,  # Usando a razão social da BrasilAPI
                        "CPF": "N/A",
                        "Nome Relacionado ao CNPJ": "N/A",
                        "Tipo de Relacionamento (CNPJ)": "N/A",
                        "Nome do Relacionamento (CNPJ)": "N/A",
                        "Nome do CPF (Consulta Detalhada)": "N/A",
                        "Data Nascimento CPF (Consulta Detalhada)": "N/A",
                        "Email Principal (Consulta Detalhada)": "N/A",
                        "Email Secundário (Consulta Detalhada)": "N/A",
                        "Telefone Principal (Consulta Detalhada)": "N/A",
                        "Telefone Secundário (Consulta Detalhada)": "N/A",
                        "Endereço Principal (Consulta Detalhada)": "N/A",
                        "Endereço Secundário (Consulta Detalhada)": "N/A",
                        "Status Consulta CPF": "Erro CNPJ",
                        "Detalhes Consulta CPF": f"Erro inesperado ao consultar CNPJ: {str(e)}",
                    }
                )

        # Gerar a planilha Excel em memória
        df = pd.DataFrame(all_cpf_data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Resultados CPF")
        output.seek(0)

        response = FileResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            'attachment; filename="resultados_consulta_massa_cpf.xlsx"'
        )
        return response


class ComercialRegiaoAPIView(APIView):
    def post(self, request, *args, **kwargs):
        user = self.request.user

        if not user.is_authenticated:
            return Response(
                {"detail": "Você precisa estar autenticado para acessar esta consulta em massa."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            uf = request.data.get('uf', '').upper()
            cidade = request.data.get('cidade', '').upper()
            bairro_filtro = request.data.get('bairro', '').upper()

            if not uf or not cidade:
                return Response(
                    {"detail": "UF e Cidade são obrigatórios para a pesquisa."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            cnaes = ['6821801', '6821802', '6822600']
            todos_resultados = []

            # 2. Função auxiliar para execução paralela
            def buscar_dados_cnae(cnae):
                try:
                    url = f"https://minhareceita.org/?cnae={cnae}&uf={uf}"
                    
                    # === PONTO DE DEBUG 1: URL E STATUS ===
                    print(f"\n[DEBUG] CNAE {cnae}: Requisição para -> {url}") 
                    response = requests.get(url, timeout=30) 
                    print(f"[DEBUG] CNAE {cnae}: Status Code -> {response.status_code}")
                    # ======================================
                    
                    if response.status_code == 200:
                        dados = response.json()
                        
                        # === PONTO DE DEBUG 2: TRATAMENTO DO RETORNO ===
                        # ⚠️ Se o retorno JSON vier aninhado (ex: {"data": [...]}), corrija aqui
                        if not isinstance(dados, list) and isinstance(dados, dict) and 'data' in dados:
                             dados = dados.get('data', [])
                             print(f"[DEBUG] CNAE {cnae}: Corrigido retorno aninhado. (Usando chave 'data')")
                        
                        if not isinstance(dados, list):
                            print(f"[ERRO] CNAE {cnae}: Retorno JSON não é uma lista após correção. Abortando.")
                            return []
                        # ===============================================

                        
                        # FILTRAGEM: O filtro por Cidade e Bairro ocorre aqui
                        filtrados = [
                            empresa 
                            for empresa in dados
                            if empresa.get('municipio', '').upper() == cidade
                            and (not bairro_filtro or empresa.get('bairro', '').upper() == bairro_filtro)
                        ]
                        
                        # === PONTO DE DEBUG 3: RESULTADO DO FILTRO ===
                        print(f"[DEBUG] CNAE {cnae}: Total ANTES do filtro: {len(dados)}")
                        print(f"[DEBUG] CNAE {cnae}: Total DEPOIS do filtro: {len(filtrados)}")
                        if len(dados) > 0 and len(filtrados) == 0:
                            print("[DEBUG] ATENÇÃO: O filtro está rejeitando tudo. Verifique as chaves 'municipio' e 'bairro' no JSON de resposta da API.")
                        # =============================================

                        # PADRONIZAÇÃO DO RETORNO: 
                        return [
                            {
                                "nome": emp.get("razao_social") or emp.get("nome_fantasia"),
                                "tipo": (
                                     "Imobiliária"
                                     if cnae.startswith("6821")
                                     else "Administradora"
                                 ),
                                "endereco": f"{emp.get('logradouro')}, {emp.get('numero')} - {emp.get('bairro')}, {emp.get('municipio')} - {emp.get('uf')}",
                                "cep": emp.get("cep", "Sem CEP"),
                                "telefone": emp.get("ddd_telefone_1", "Sem Telefone"), 
                                "cnpj": emp.get("cnpj", "Não encontrado"),
                                "mei": emp.get("opcao_pelo_mei", "false"),
                                "porte": emp.get("porte", "Não informado"),
                                "cnae": cnae,
                            }
                            for emp in filtrados
                        ]
                    return []
                except Exception as erro_req:
                    print(f"[ERRO] CNAE {cnae} para UF {uf}: {erro_req}")
                    return []

            # 3. Execução Paralela e Coleta dos Resultados
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(buscar_dados_cnae, cnae) for cnae in cnaes]
                
                for future in as_completed(futures):
                    resultado = future.result()
                    if resultado:
                        todos_resultados.extend(resultado)

            return Response(todos_resultados, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Erro interno na View: {e}")
            return Response(
                {'detail': 'Não foi possível realizar a consulta devido a um erro interno.'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )