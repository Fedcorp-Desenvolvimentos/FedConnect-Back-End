# consultas/services/firebird.py

import requests
import logging

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

class CedentesService:
    def __init__(self):
        pass

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

    