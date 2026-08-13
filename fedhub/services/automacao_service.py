    
# consultas/services/firebird.py

from decouple import config
from typing import Any, Dict, Optional
import requests

from consultas.utils.get_headers import get_auth_headers
import logging

logger = logging.getLogger(__name__)

class AutomacaoService:
    def __init__(self):
        self.base_url = config("FEDHUB_URL", default="http://localhost:8090")  # URL do serviço Fedhub

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
                f"{self.base_url}/api/automate/separar-pdf",
                headers=get_auth_headers(),
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
                f"{self.base_url}/api/automate/upload-pdfs-bbz",
                headers=get_auth_headers(),
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
                headers=get_auth_headers(),
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