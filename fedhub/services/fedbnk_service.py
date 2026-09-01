# fedhub/services/fedbnk_service.py

from decouple import config
from typing import Any, Dict, Optional
import requests
import logging

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

class FedhubService:
    def __init__(self):
        self.base_url = config("FEDHUB_URL", default="http://localhost:8090").rstrip("/")  # URL do serviço Fedhub
        self.webhook_url = config("WEBHOOK_URL", default="http://localhost:8000")  # URL do webhook para sincronização
        
    def cancelar_boleto_fedbnk(self, payload: dict) -> Optional[Dict[str, Any]]:
            """Cancela boleto(s) no FedHub"""
            try:
                url = f"{self.base_url}/api/fedpay/cancelamento"

                fedhub_payload = {
                    "fatura": int(payload["fatura"]),
                    "documento": payload.get("documento"),
                }

                response = requests.post(
                    url,
                    headers=get_headers(),
                    json=fedhub_payload,
                    timeout=30,
                )
    
                if response.status_code != 200:
                    logger.error(f"FedHub erro {response.status_code}: {response.text}")
                    return {
                        "status": "erro",
                        "message": f"Erro na API do FedHub: {response.status_code}",
                    }
    
                # logger.info(f"Resposta do FedHub para cancelamento: {response.json()}")
    
                data = response.json()
    
                # Retornar no formato esperado
                if data.get("status") == "success":
                    return {
                        "status": "sucesso",
                        "message": data.get(
                            "message", "Cancelamento realizado com sucesso"
                        ),
                        "dados": data.get("dados"),
                    }
                else:
                    return {
                        "status": "erro",
                        "message": data.get("message", "Falha no cancelamento"),
                    }
    
            except requests.RequestException as e:
                logger.error(f"Erro ao chamar FedHub: {e}")
                return {"status": "erro", "message": f"Erro de comunicação: {str(e)}"}
        
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
        