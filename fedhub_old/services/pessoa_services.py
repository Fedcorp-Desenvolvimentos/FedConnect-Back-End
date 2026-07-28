# consultas/services/firebird.py

from typing import Any, Dict, Optional
import requests
import logging

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

class FedhubService:
    def __init__(self):
        pass

    # Pessoas
    def buscar_pessoas(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Busca pessoas (favorecidos) - proxy para FedHub
        GET /api/pessoas/
        """
        try:
            params_limpos = {k: v for k, v in params.items() if v not in [None, "", []]}
            response = requests.get(
                f"{self.base_url}/api/pessoas/",
                params=params_limpos,
                headers=get_headers(),
                timeout=30,
            )
            if response.status_code != 200:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                return None
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar pessoas: {e}")
            return None


        

