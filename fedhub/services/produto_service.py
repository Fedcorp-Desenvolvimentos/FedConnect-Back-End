# fedhub/services/produto_service.py
from typing import Any, Dict, Optional
import requests
import logging
from decouple import config
from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)


class ProdutoService:
    def __init__(self):
        self.base_url = config("FEDHUB_URL", default="http://localhost:8090").rstrip("/")  # URL do serviço Fedhub
    
    def buscar_produtos(self) -> Optional[Dict[str, Any]]:
        """
        Busca todos os produtos distintos do Firebird
        GET /api/pessoas/produtos
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/produtos/",
                headers=get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"FedHub erro ao buscar produtos: {response.status_code}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data

        except requests.RequestException as e:
            logger.error(f"Erro ao buscar produtos no FedHub: {e}")
            return None
        
    