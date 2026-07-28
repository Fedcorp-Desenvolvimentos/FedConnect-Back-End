# consultas/services/firebird.py

from typing import Any, Dict, Optional
import requests
import logging

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

class FedhubService:
    def __init__(self):
        pass

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

    