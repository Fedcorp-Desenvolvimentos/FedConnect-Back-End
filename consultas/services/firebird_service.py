# consultas/services/firebird.py

from datetime import timedelta
from datetime import timedelta
import secrets
from django.utils import timezone
from typing import Any, Dict, List, Optional
import httpx
import requests
import logging

from rest_framework import settings

from django.conf import settings
from django.template.loader import render_to_string

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)


class FirebirdService:
    def __init__(self):
        self.base_url = "https://fedhub-api-local.ngrok.app"
        # self.base_url = "http://localhost:8090"

    # Faturas
    def buscar_fatura_por_numero(self, numero_fatura: str):
        try:
            response = requests.get(
                f"{self.base_url}/api/faturas/fatura/{numero_fatura}",
                headers=get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data.get("data")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Firebird: {e}")
            return None

    def buscar_faturamento(self, filtros: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Busca faturas com boletos associados - usa a rota /faturamento do FedHub
        """
        try:
            # Remove filtros vazios
            params = {k: v for k, v in filtros.items() if v not in [None, "", []]}

            # IMPORTANTE: Garantir que page e page_size sejam inteiros
            if "page" in params:
                params["page"] = int(params["page"])
            if "page_size" in params:
                params["page_size"] = int(params["page_size"])

            logger.info(f"Chamando FedHub - faturamento com params: {params}")

            response = requests.get(
                f"{self.base_url}/api/faturas/faturamento",
                params=params,
                headers=get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(
                    f"Erro ao consultar FedHub - FATURAMENTO - {response.status_code} | {response.text}"
                )
                return None

            data = response.json()
            # logger.info(f"Resposta do FedHub DADOS COMPLETOS - FATURAMENTO: {data}")
            # logger.info(f"Resposta do FedHub: {data.get('status')}")

            logger.info(
                f"Quantidade de faturas retornadas: {len(data.get('data', [])) if data.get('status') == 'success' else 'N/A'}"
            )

            if data.get("status") != "success":
                return None

            return data

        except requests.RequestException as e:
            logger.error(f"Erro comunicação com o FedHub - FATURAMENTO: {e}")
            return None

    async def buscar_fatura_por_nosso_numero(self, nosso_numero: str):
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    f"{self.base_url}/api/boletos/buscar/por-nosso-numero/{nosso_numero}/",
                    headers=get_headers(),
                )

                if response.status_code != 200:
                    logger.error(f"Fedhub erro {response.status_code}: {response.text}")
                    return None

                data = response.json()
                return data.get("data") if data.get("status") == "success" else None

        except httpx.RequestError as e:
            logger.error(f"Erro ao chamar Fedhub: {e}")
            return None

    async def buscar_todas_faturas(
        self, fatura_numero: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Busca dados da fatura no microsserviço Firebird (8090)
        Rota: /api/faturas/fatura-postos-vida/{fatura_numero}
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/faturas/fatura-postos-vida/{fatura_numero}"
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get("status") == "success":
                        return data.get("data", [])
                    else:
                        logger.warning(
                            f"Fatura {fatura_numero} não encontrada: {data.get('message')}"
                        )
                        return None
                else:
                    logger.error(
                        f"Erro HTTP {response.status_code} ao buscar fatura {fatura_numero}"
                    )
                    return None

        except httpx.TimeoutException:
            logger.error(f"Timeout ao buscar fatura {fatura_numero}")
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar fatura {fatura_numero}: {str(e)}")
            return None

    def rodar_procedure_tratamento_erro(self) -> Optional[Dict[str, Any]]:
        """
        Roda a procedure de tratamento de erro do FedHub (FastAPI)
        POST /fatura/rodar-procedure-tratamento-erro/
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/faturas/fatura/rodar-procedure-tratamento-erro/",
                headers=get_headers(),
                timeout=60,  # Timeout maior pois pode demorar
            )

            if response.status_code != 200:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                return {
                    "status": "error",
                    "message": f"Erro na API do FedHub: {response.status_code}",
                }

            data = response.json()

            # Verificar formato da resposta do FastAPI
            if data.get("status") == "success":
                return {
                    "status": "success",
                    "message": data.get("message", "Procedure executada com sucesso"),
                    "data": data.get("data", {}),
                }
            else:
                return {
                    "status": "error",
                    "message": data.get("message", "Falha na execução da procedure"),
                }

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar FedHub para procedure: {e}")
            return {"status": "error", "message": f"Erro de comunicação: {str(e)}"}

    def converter_boleto_csv(self, fatura: int) -> Optional[Dict[str, Any]]:
        """
        Converte boletos de uma fatura para CSV
        GET /api/faturas/fatura/converter-boleto-csv/{fatura}/
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/faturas/fatura/converter-boleto-csv/{fatura}/",
                headers=get_headers(),
                timeout=60,  # Timeout maior pois pode gerar muitos dados
            )
            
            logger.info(f"Chamando FedHub para converter CSV - URL: {response.url} | Status: {response.status_code}")
            
            # Verifica se é uma resposta de arquivo CSV (content-type: text/csv)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")

                # Se for CSV, processa como texto
                if "text/csv" in content_type:
                    return {
                        "status": "success",
                        "csv_content": response.text,
                        "filename": (
                            response.headers.get("content-disposition", "")
                            .split("filename=")[-1]
                            .strip('"')
                            if "filename="
                            in response.headers.get("content-disposition", "")
                            else f"boletos_fatura_{fatura}.csv"
                        ),
                    }

                # Se for JSON, parse normal
                data = response.json()

                # Verificar estrutura da resposta do FedHub
                if data.get("status") == "success":
                    # Se já tem csv_content, retorna direto
                    if "csv_content" in data:
                        return data

                    # Se tem data mas não csv_content, converte aqui
                    if "data" in data and data["data"]:
                        # Importa a função de conversão
                        from consultas.utils.csv_utils import convert_to_csv
                        logger.info(f" resposta do fedhub: {response.text}")
                        dados = [
                            {k.upper(): v for k, v in item.items()}
                            for item in data["data"]
                        ]
                        csv_content = convert_to_csv(
                            dados,
                            fieldnames=[
                                "CNPJ", "POSTO", "NOME", "LINHA_BARRA",
                                "LINHA_DIGITAVEL", "VENCIMENTO", "VALOR"
                            ]
                        )

                        return {
                            "status": "success",
                            "csv_content": csv_content,
                            "filename": f"boletos_fatura_{fatura}.csv",
                            "total_registros": len(data["data"]),
                        }

                # Se status for not_found
                if data.get("status") == "not_found":
                    return data

                # Se chegou aqui, algo deu errado
                logger.error(f"Resposta inesperada do FedHub: {data}")
                return None

            # Status diferente de 200
            logger.error(f"FedHub erro {response.status_code}: {response.text}")
            return {
                "status": "error",
                "message": f"Erro na API do FedHub: {response.status_code}",
            }

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar FedHub para converter CSV: {e}")
            return {"status": "error", "message": f"Erro de comunicação: {str(e)}"}

    # Empresas
    async def buscar_empresa_por_cnpj(
        self, cnpj: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Busca empresa por CNPJ no microsserviço Firebird
        """
        try:
            # Limpar CNPJ
            cnpj_limpo = "".join(filter(str.isdigit, cnpj))

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/empresas/{cnpj_limpo}"
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get("status") == "success":
                        return data.get("data", [])
                    else:
                        logger.warning(f"Empresa CNPJ {cnpj} não encontrada")
                        return None
                else:
                    logger.error(
                        f"Erro HTTP {response.status_code} ao buscar empresa {cnpj}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Erro ao buscar empresa {cnpj}: {str(e)}")
            return None

    async def buscar_todas_empresas(self):
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/api/empresas/",
                headers=get_headers(),
            )

        if response.status_code != 200:
            logger.error(f"Firebird erro {response.status_code}")
            return None

        data = response.json()

        if data.get("status") != "success":
            return None

        return data.get("data")

    # Administradoras
    def buscar_administradoras(self):
        try:
            response = requests.get(
                f"{self.base_url}/api/administradoras/",
                timeout=30,
                headers=get_headers(),
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data.get("data")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Firebird: {e}")
            return None

    def buscar_administradora_por_nome(self, nome: str):
        try:
            response = requests.get(
                f"{self.base_url}/api/administradoras/por-nome/{nome}",
                timeout=30,
                headers=get_headers(),
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data.get("data")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Firebird: {e}")
            return None

    def buscar_administradora_por_codigo(self, codigo: str):
        try:
            response = requests.get(
                f"{self.base_url}/api/administradoras/por-codigo/{codigo}",
                headers=get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data.get("data")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Firebird: {e}")
            return None

    def buscar_administradora_por_codigo_com_postos_vida(self, codigo: str):
        try:
            response = requests.get(
                f"{self.base_url}/api/administradoras/posto/{codigo}",
                headers=get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data.get("data")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Firebird: {e}")
            return None

    # Corretores
    def buscar_corretor_por_codigo(self, codigo: str):
        try:
            response = requests.get(
                f"{self.base_url}/api/corretores/corretor/{codigo}",
                headers=get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if not data.get("encontrado"):
                return None

            return data.get("dados")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Firebird: {e}")
            return None

    # Cedentes
    def buscar_todos_cedentes(self, codigo: str):
        try:
            response = requests.get(
                f"{self.base_url}/api/cedentes/", headers=get_headers(), timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if not data.get("encontrado"):
                return None

            return data.get("dados")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Firebird: {e}")
            return None

    def buscar_cedente_por_codigo(self, codigo: str):
        try:
            response = requests.get(
                f"{self.base_url}/api/cedentes/cedente/{codigo}",
                headers=get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if not data.get("encontrado"):
                return None

            return data.get("dados")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Firebird: {e}")
            return None

    # Nota Fiscal
    def buscar_nfse_por_boleto(self, documento: str):
        try:
            # 1. Buscar ID da NFSE no Firebird
            response = requests.get(
                f"{self.base_url}/api/nfse/consultar-nfse-por-boleto/{documento}/",
                headers=get_headers(),
                timeout=30,
            )

            logger.info(
                f"Buscando NFSE por boleto - URL: {response.url} | Dados: {response.text}"
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            registros = data.get("data", [])

            if not registros:
                return None

            # 2. Pegar o ID da NFSE
            id_nfse = registros[0].get("id_nfs_e")

            if not id_nfse:
                logger.warning(f"NFSE sem ID para documento {documento}")
                return None

            # 3. Segunda chamada (outro backend)
            url_nfse = f"https://fedcorp-nfs-e-django-ebh2e.ondigitalocean.app/api/consultas/nfse/{id_nfse}/"
            # url_nfse = f"http://localhost:8000/api/consultas/nfse/{id_nfse}/"

            response_nfse = requests.get(url_nfse, headers=get_headers(), timeout=30)

            logger.info(
                f"Buscando NFSE completa - URL: {url_nfse} | Dados: {response_nfse.text}"
            )

            if response_nfse.status_code != 200:
                logger.error(
                    f"Erro ao buscar NFSE completa: {response_nfse.status_code}"
                )
                return None

            nfse_data = response_nfse.json()

            return nfse_data

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar serviços: {e}")
            return None

    # Email
    def enviar_email_recuperacao_senha(self, email: str, user: Any) -> bool:
        try:
            with httpx.Client() as client:

                # 🔐 Gerar NOVO token (sobrescreve o anterior)
                reset_token = secrets.token_urlsafe(32)
                expires_at = timezone.now() + timedelta(hours=24)

                # SOBRESCREVE o token anterior (se existir)
                user.reset_password_token = reset_token
                user.reset_password_token_created_at = timezone.now()
                user.reset_password_token_expires_at = expires_at
                # Não precisa limpar antes, apenas sobrescreve
                user.save(
                    update_fields=[
                        "reset_password_token",
                        "reset_password_token_created_at",
                        "reset_password_token_expires_at",
                    ]
                )

                logger.info(
                    f"Novo token gerado (sobrescreveu anterior) para: {user.email}"
                )
                logger.info(f"Token expira em: {expires_at}")

                frontend_url = settings.FRONTEND_URL

                # Construir link de reset
                reset_url = f"{frontend_url}/resetar-senha/{reset_token}"

                logger.info(f"Link de reset gerado: {reset_url}")

                html_body = render_to_string(
                    "email/resetar_senha.html",
                    {
                        "nome_usuario": user.nome_completo or user.email,
                        "reset_url": reset_url,
                    },
                )

                response = client.post(
                    f"{self.base_url}/api/email/send/gmail",
                    json={
                        "to_email": email,
                        "subject": "Redefinição de Senha - FedConnect",
                        "body": html_body,
                        "is_html": True,
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    logger.info(f"Email enviado com sucesso via Gateway para: {email}")
                else:
                    logger.error(
                        f"Gateway retornou erro {response.status_code}: {response.text}"
                    )

            return True

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar serviço de email: {e}")
            return False

    def enviar_email_fatura_mensal(
        self, email: str, nome_usuario: str, data_fatura: str
    ) -> bool:
        try:
            pass
        except requests.RequestException as e:
            logger.error(f"Erro ao chamar serviço de email: {e}")
            return False

    def enviar_email_segunda_via(
        self, email: str, nome_usuario: str, data_fatura: str
    ) -> bool:
        try:
            pass
        except requests.RequestException as e:
            logger.error(f"Erro ao chamar serviço de email: {e}")
            return False

    def enviar_email_aviso_vencimento(
        self, email: str, nome_usuario: str, data_vencimento: str
    ) -> bool:
        try:
            pass
        except requests.RequestException as e:
            logger.error(f"Erro ao chamar serviço de email: {e}")
            return False

    # Localidades
    def buscar_localidades(self) -> Optional[Dict[str, Any]]:
        """
        Busca localidades do gateway FastAPI
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/armazenamento/localidades",
                headers=get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"Gateway erro {response.status_code}: {response.text}")
                return None

            data = response.json()

            if data.get("status") != "SUCCESS":
                logger.error(f"Gateway retornou erro: {data.get('message')}")
                return None

            return data.get("data", {})

        except requests.RequestException as e:
            logger.error(f"Erro ao buscar localidades do gateway: {e}")
            return None

    # Automação
    def separar_pdf(self, file, nome_base: str = "") -> bytes:
        """
        Chama o FedHub para separar o PDF em páginas individuais
        """
        try:
            # Preparar arquivo para envio
            files = {"file": (file.name, file.read(), "application/pdf")}

            data = {}
            if nome_base:
                data["nome_base"] = nome_base

            logger.info(f"Enviando PDF para separação: {file.name}")

            response = requests.post(
                f"{self.base_url}/api/automatizador/separar-pdf",
                files=files,
                data=data,
                timeout=300,
            )

            if response.status_code != 200:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                # Tentar parsear como JSON de erro
                try:
                    error_data = response.json()
                    return {
                        "status": "erro",
                        "message": error_data.get("message", "Erro desconhecido"),
                    }
                except:
                    return {
                        "status": "erro",
                        "message": f"Erro HTTP {response.status_code}",
                    }

            # Verificar se a resposta é um ZIP (content-type application/zip)
            if response.headers.get("content-type") == "application/zip":
                return response.content  # Retorna bytes do ZIP

            # Tentar parsear como JSON (caso de erro)
            try:
                return response.json()
            except:
                return response.content

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar FedHub para separar PDF: {e}")
            return {"status": "erro", "message": str(e)}

    def upload_pdfs_bbz(self, files: list) -> Optional[Dict[str, Any]]:
        """
        Apenas envia arquivos PDF para o FedHub salvar na pasta de origem
        """
        try:
            files_to_send = []
            for file in files:
                file_content = file.read()
                files_to_send.append(
                    ("files", (file.name, file_content, "application/pdf"))
                )

            logger.info(
                f"Enviando {len(files_to_send)} arquivos para o FedHub (apenas upload)"
            )

            response = requests.post(
                f"{self.base_url}/api/automatizador/upload-pdfs-bbz",
                files=files_to_send,
                timeout=300,
            )

            logger.info(f"Resposta completa do FedHub: {response.json()}")

            logger.info(f"Resposta do FedHub: status={response.status_code}")

            if response.status_code != 200:
                logger.error(f"Gateway erro {response.status_code}: {response.text}")
                return None

            return response.json()

        except Exception as e:
            logger.error(f"Erro ao chamar gateway: {e}")
            raise

    def processar_pdfs_bbz(self, fazer_backup: bool = True) -> Optional[Dict[str, Any]]:
        """
        Chama o FedHub para processar os PDFs que já estão na pasta de origem
        """
        try:
            data = {"fazer_backup": str(fazer_backup).lower()}

            logger.info(f"Chamando FedHub para processar PDFs (backup={fazer_backup})")

            response = requests.post(
                f"{self.base_url}/api/automate/processar-pdfs-bbz",
                data=data,
                timeout=300,
            )

            logger.info(f"Resposta do FedHub: status={response.status_code}")

            if response.status_code != 200:
                logger.error(f"Gateway erro {response.status_code}: {response.text}")
                return None

            return response.json()

        except Exception as e:
            logger.error(f"Erro ao chamar gateway: {e}")
            raise

    # Boleto FedBnk
    def cancelar_boleto_fedbnk(self, payload: dict) -> Optional[Dict[str, Any]]:
        """Cancela boleto(s) no FedHub"""
        try:
            # URL correta do FedHub (única rota para cancelamento)
            url = f"{self.base_url}/api/fedbnk/cancelar/"

            response = requests.post(
                url,
                headers=get_headers(),
                json=payload,  # Payload: {fatura, documento, motivo, mail}
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                return {
                    "status": "erro",
                    "message": f"Erro na API do FedHub: {response.status_code}",
                }

            # logger.info(f"Resposta do FedHub para cancelamento: {response.json()}")

            data = response.json()

            # Retornar no formato esperado
            if data.get("status") == "success":
                return {
                    "status": "sucesso",
                    "message": data.get(
                        "message", "Cancelamento realizado com sucesso"
                    ),
                    "dados": data.get("dados"),
                }
            else:
                return {
                    "status": "erro",
                    "message": data.get("message", "Falha no cancelamento"),
                }

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar FedHub: {e}")
            return {"status": "erro", "message": f"Erro de comunicação: {str(e)}"}

    # Processamento de pagamento de boleto via webhook do Santander
    async def processar_pagamento_boleto(
        self, documento: str, fatura: str, dados_pagamento: dict
    ):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/santander/webhook/processar-pagamento/{documento}/{fatura}",
                    headers=get_headers(),
                    json=dados_pagamento,
                )

                if response.status_code != 200:
                    logger.error(f"Fedhub erro {response.status_code}: {response.text}")
                    return None

                data = response.json()
                return data.get("data") if data.get("status") == "success" else None

        except httpx.RequestError as e:
            logger.error(f"Erro ao chamar Fedhub: {e}")
            return None
    
    def processar_dados_segunda_via_boleto(self, fatura: str):
        """Este método já está síncrono - perfeito!"""
        try:
            # ⚠️ IMPORTANTE: Validar se fatura não é None
            if not fatura:
                logger.error("Fatura não informada")
                return None
                
            # Usando GET (não POST) como está no FastAPI
            response = requests.get(
                f"{self.base_url}/api/faturamento/dados-segunda-via/{fatura}/",
                headers=get_headers(),
                timeout=30.0
            )

            # Log mais detalhado
            logger.info(f"Chamando FedHub: {self.base_url}/api/faturamento/dados-segunda-via/{fatura}/")
            logger.info(f"Status code: {response.status_code}")
            logger.info(f"Response: {response.text}")

            if response.status_code != 200:
                logger.error(f"Fedhub erro {response.status_code}: {response.text}")
                return None

            data = response.json()
            
            # Verificar estrutura da resposta
            if data.get("status") == "success":
                return data.get("data")
            else:
                logger.error(f"Fedhub retornou status não-success: {data}")
                return None

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Fedhub: {e}")
            return None
