# consultas/services/firebird.py

from decouple import config
from typing import Any, Dict, Optional
import requests
import logging

from consultas.utils.get_headers import get_headers
logger = logging.getLogger(__name__)

class PessoasService:
    def __init__(self):
        self.base_url = config("FEDHUB_URL", default="http://localhost:8090").rstrip("/")  # URL do serviço Fedhub

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
        
    def criar_pessoa(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Cria uma nova pessoa - proxy para FedHub
        POST /api/pessoas/criar-pessoa
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/pessoas/criar-pessoa",
                json=payload,
                headers=get_headers(),
                timeout=30,
            )

            # Trata sucesso (200 ou 201)
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    
                    # Verifica se o FastAPI retornou sucesso
                    if data.get("status") == "success":
                        return data
                    else:
                        # FastAPI retornou erro
                        logger.error(f"FastAPI retornou erro: {data}")
                        return {
                            "status": "error",
                            "message": data.get("message", "Erro ao criar pessoa no FastAPI"),
                            "http_status": response.status_code,
                        }
                except ValueError:
                    logger.error(f"Resposta inválida do FastAPI: {response.text}")
                    return {
                        "status": "error",
                        "message": "Resposta inválida do FastAPI",
                        "http_status": 502,
                    }

            # Trata erro 404 - rota não encontrada
            if response.status_code == 404:
                logger.error(f"Rota /api/pessoas/criar-pessoa não encontrada no FastAPI")
                return {
                    "status": "error",
                    "message": "Rota de criação de pessoa não encontrada no FastAPI",
                    "http_status": 404,
                }

            # Trata outros erros HTTP
            logger.error(f"FastAPI erro {response.status_code}: {response.text}")
            return {
                "status": "error",
                "message": f"Erro no FastAPI: {response.status_code}",
                "http_status": response.status_code,
            }

        except requests.Timeout:
            logger.error("Timeout ao criar pessoa no FastAPI")
            return {
                "status": "timeout",
                "message": "Timeout ao aguardar resposta do FastAPI",
                "http_status": 504,
            }

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar FastAPI para criar pessoa: {e}")
            return {
                "status": "error",
                "message": f"Erro de comunicação com FastAPI: {str(e)}",
                "http_status": 503,
            }
            
    def buscar_gerentes_comerciais(self) -> Optional[Dict[str, Any]]:
        """
        Busca gerentes comerciais ativos do Firebird
        GET /api/pessoas/gerentes-comerciais
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/pessoas/gerentes-comerciais",
                headers=get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"FedHub erro ao buscar gerentes comerciais: {response.status_code}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data

        except requests.RequestException as e:
            logger.error(f"Erro ao buscar gerentes comerciais no FedHub: {e}")
            return None

    def buscar_pessoa_por_codigo(self, codigo: str) -> Optional[Dict[str, Any]]:
        try: 
            response = requests.get(
                f"{self.base_url}/api/pessoas/{codigo}/",
                headers=get_headers(),
                timeout=30,
            )
            if response.status_code != 200:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                return None
            data = response.json()
            if data.get("status") != "success":
                logger.error(f"FedHub retornou erro: {data}")
                return None
            return data.get("data")
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar pessoa por código: {e}")
            return None
        
    def atualizar_pessoa(self, codigo: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Atualiza uma pessoa existente - proxy para FedHub
        PUT /api/pessoas/{codigo}
        """
        try:
            response = requests.put(
                f"{self.base_url}/api/pessoas/{codigo}",
                json=payload,
                headers=get_headers(),
                timeout=30,
            )

            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    
                    if data.get("status") == "success":
                        return data
                    else:
                        logger.error(f"FastAPI retornou erro: {data}")
                        return {
                            "status": "error",
                            "message": data.get("message", "Erro ao atualizar pessoa no FastAPI"),
                            "http_status": response.status_code,
                        }
                except ValueError:
                    logger.error(f"Resposta inválida do FastAPI: {response.text}")
                    return {
                        "status": "error",
                        "message": "Resposta inválida do FastAPI",
                        "http_status": 502,
                    }

            logger.error(f"FastAPI erro {response.status_code}: {response.text}")
            return {
                "status": "error",
                "message": f"Erro no FastAPI: {response.status_code}",
                "http_status": response.status_code,
            }

        except requests.Timeout:
            logger.error("Timeout ao atualizar pessoa no FastAPI")
            return {
                "status": "timeout",
                "message": "Timeout ao aguardar resposta do FastAPI",
                "http_status": 504,
            }

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar FastAPI para atualizar pessoa: {e}")
            return {
                "status": "error",
                "message": f"Erro de comunicação com FastAPI: {str(e)}",
                "http_status": 503,
            }