# fedhub/services/administradoras_service.py

import requests
import logging
from decouple import config
from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

class AdministradorasService:
    def __init__(self):
        self.base_url = config("FEDHUB_URL", default="http://localhost:8090").rstrip("/")  # URL do serviço Fedhub

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

    