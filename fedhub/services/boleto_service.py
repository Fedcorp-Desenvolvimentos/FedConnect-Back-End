# consultas/services/firebird.py

import requests
import logging

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)


class FedhubService:
    def __init__(self):
        pass

    # Segunda via de boleto
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
            # logger.info(f"Chamando FedHub: {self.base_url}/api/faturamento/dados-segunda-via/{fatura}/")
            # logger.info(f"Status code: {response.status_code}")
            # logger.info(f"Response: {response.text}")

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
        

