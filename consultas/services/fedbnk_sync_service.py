import requests
import logging
from django.conf import settings
from typing import Dict, Any

logger = logging.getLogger(__name__)


class FedBnkSyncService:
    def __init__(self):
        self.webhook_url = settings.WEBHOOK_URL

    def sincronizar_boletos(self, numero_fatura: str) -> Dict[str, Any]:
        url = f"{self.webhook_url}/boletofedbnk/sincronizar/"

        response = requests.post(
            url,
            params={"numero_fatura": numero_fatura},
            headers={"Content-Type": "application/json"},
            timeout=120,
        )

        if response.status_code != 200:
            logger.error(f"Erro ao sincronizar via FINANC: {response.status_code} - {response.text}")
            raise Exception(f"Erro ao sincronizar: {response.text}")

        return response.json()
