# consultas/services/fedhub_service.py
import httpx
import logging

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

class FedhubService:
    def __init__(self):
        self.base_url = "https://fedhub-api-local.ngrok.app"
        # self.base_url = "http://localhost:8090"

    async def processar_pagamento_boleto(self, documento: str, fatura: str, dados_pagamento: dict):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/santander/webhook/processar-pagamento/{documento}/{fatura}",
                    headers=get_headers(),
                    json=dados_pagamento
                )

                if response.status_code != 200:
                    logger.error(f"Fedhub erro {response.status_code}: {response.text}")
                    return None

                data = response.json()
                return data.get("data") if data.get("status") == "success" else None

        except httpx.RequestError as e:
            logger.error(f"Erro ao chamar Fedhub: {e}")
            return None
        
    async def buscar_fatura_por_nosso_numero(self, nosso_numero: str):
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    f"{self.base_url}/api/boletos/buscar/por-nosso-numero/{nosso_numero}/",
                    headers=get_headers()
                )

                if response.status_code != 200:
                    logger.error(f"Fedhub erro {response.status_code}: {response.text}")
                    return None

                data = response.json()
                return data.get("data") if data.get("status") == "success" else None

        except httpx.RequestError as e:
            logger.error(f"Erro ao chamar Fedhub: {e}")
            return None
    