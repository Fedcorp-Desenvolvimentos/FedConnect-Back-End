# consultas/services/firebird.py

from typing import Any, Dict, Optional
import requests
import logging
from decouple import config
from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

class CedenteService:
    def __init__(self):
        self.base_url = config("FEDHUB_URL", default="http://localhost:8090").rstrip("/")  # URL do serviço Fedhub

    # Cedentes
    def buscar_todos_cedentes(self) -> Optional[Dict[str, Any]]:
        """
        Busca todos os cedentes no FastAPI
        GET /api/cedentes/
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/cedentes/",
                headers=get_headers(),
                timeout=30,
            )
            
            if response.status_code != 200:
                logger.error(f"FastAPI erro {response.status_code}: {response.text}")
                return None
            
            data = response.json()
            
            # Verifica estrutura da resposta
            if data.get("status") != "success":
                logger.error(f"FastAPI retornou erro: {data}")
                return None
            
            return data
            
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar cedentes: {e}")
            return None

    def buscar_cedente_por_nome(self, nome: str) -> Optional[Dict[str, Any]]:
        """
        Busca cedente por nome no FastAPI
        GET /api/cedentes/por-nome/?nome=termo
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/cedentes/por-nome",
                params={"nome": nome},
                headers=get_headers(),
                timeout=30,
            )
            
            if response.status_code != 200:
                logger.error(f"FastAPI erro {response.status_code}: {response.text}")
                return None
            
            data = response.json()
            
            if data.get("status") != "success":
                logger.error(f"FastAPI retornou erro: {data}")
                return None
            
            return data
            
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar cedente por nome: {e}")
            return None