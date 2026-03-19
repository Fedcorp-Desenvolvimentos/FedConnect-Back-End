# consultas/services/fedhub_service.py

import requests
import logging

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

class FedhubService:
    def __init__(self):
        # self.base_url = "http://localhost:8090"
        self.base_url = "https://steeply-outlandish-reese.ngrok-free.dev"

    def atualizar_boleto_santander(self, numero_fatura: str):
        try:
            response = requests.post(
                f"{self.base_url}/api/boletos/processar-boleto/{numero_fatura}",
                # headers=get_headers(),
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Fedhub erro {response.status_code}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data.get("data")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Fedhub: {e}")
            return None

    