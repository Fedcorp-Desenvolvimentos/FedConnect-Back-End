# consultas/services/firebird.py

from decouple import config
from typing import Any, Dict, Optional
import requests
import logging

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

class BancosService:
    def __init__(self):
        self.base_url = config("FEDHUB_URL", default="http://localhost:8090")  # URL do serviço Fedhub
        
    # BANCOS
    def buscar_bancos(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Busca bancos - proxy para FedHub
        GET /api/bancos/
        """
        try:
            params_limpos = {k: v for k, v in params.items() if v not in [None, "", []]}
            response = requests.get(
                f"{self.base_url}/api/bancos/",
                params=params_limpos,
                headers=get_headers(),
                timeout=30,
            )
            
            if response.status_code != 200:
                logger.error(f"FedHub erro ao buscar bancos: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            
            if data.get("status") != "success":
                logger.error(f"FedHub retornou erro: {data}")
                return None
            
            return data
            
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar bancos no FedHub: {e}")
            return None
    
    def buscar_banco_por_codigo(self, codigo: str) -> Optional[Dict[str, Any]]:
        """
        Busca banco por código - proxy para FedHub
        GET /api/bancos/{codigo}
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/bancos/{codigo}",
                headers=get_headers(),
                timeout=30,
            )
            
            if response.status_code != 200:
                logger.error(f"FedHub erro ao buscar banco {codigo}: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            
            if data.get("status") != "success":
                logger.error(f"FedHub retornou erro: {data}")
                return None
            
            return data.get("data")
            
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar banco {codigo} no FedHub: {e}")
            return None
    
    def buscar_banco_por_nome(self, nome: str) -> Optional[Dict[str, Any]]:
        """
        Busca banco por nome - proxy para FedHub
        GET /api/bancos/nome/{nome}
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/bancos/nome/{nome}",
                headers=get_headers(),
                timeout=30,
            )
            
            if response.status_code != 200:
                logger.error(f"FedHub erro ao buscar banco por nome {nome}: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            
            if data.get("status") != "success":
                logger.error(f"FedHub retornou erro: {data}")
                return None
            
            return data
            
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar banco por nome {nome} no FedHub: {e}")
            return None