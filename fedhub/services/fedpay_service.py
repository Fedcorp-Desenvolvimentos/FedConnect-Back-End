# fedhub/services/fedpay_service.py
#
# Proxy das rotas /api/fedpay/* do FedHub para a tela de tratamento de
# boletos. O X-Application-Key vem de get_headers(); a hierarquia de acesso
# (nível do operador) é montada na VIEW a partir do request.user — nunca
# vem do cliente.

from typing import Any, Dict, Optional

from decouple import config
import requests
import logging

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

# O tratamento cancela no banco emissor, recria e reemite — pode levar
# minutos numa fatura grande (retries do banco + geração de PDF).
TIMEOUT_CONSULTA = 30
TIMEOUT_TRATAMENTO = 300


class FedPayService:
    def __init__(self):
        self.base_url = config("FEDHUB_URL", default="http://localhost:8090")

    def _headers(self, isfedcob: bool = False) -> Dict[str, str]:
        headers = get_headers()
        if isfedcob:
            headers["isfedcob"] = "true"
        return headers

    def _resposta(self, response: requests.Response) -> Dict[str, Any]:
        """Normaliza a resposta do FedHub: {"http_status", "body"}.

        O FedHub devolve o bloco amigável (resumo/pendencias) no corpo 2xx e,
        nos erros, dentro de "detail" — aqui o detail é desembrulhado para o
        front receber o mesmo shape nos dois casos. Corpo não-JSON (túnel
        ngrok fora = HTML/5xx sem JSON da aplicação) vira erro de comunicação.
        """
        try:
            body = response.json()
        except ValueError:
            logger.error(f"FedPay: resposta não-JSON do FedHub ({response.status_code}): {response.text[:300]}")
            return {
                "http_status": 503,
                "body": {"status": "error", "message": "FedHub indisponível no momento — tente novamente em instantes."},
            }
        if isinstance(body, dict) and isinstance(body.get("detail"), dict):
            body = body["detail"]
        return {"http_status": response.status_code, "body": body}

    def consultar_fatura(self, fatura: str, isfedcob: bool = False) -> Dict[str, Any]:
        """GET /api/fedpay/consulta/{fatura} — estado dos boletos no banco emissor."""
        try:
            response = requests.get(
                f"{self.base_url}/api/fedpay/consulta/{fatura}",
                headers=self._headers(isfedcob),
                timeout=TIMEOUT_CONSULTA,
            )
            return self._resposta(response)
        except requests.RequestException as e:
            logger.error(f"FedPay: erro de comunicação na consulta da fatura {fatura}: {e}")
            return {
                "http_status": 503,
                "body": {"status": "error", "message": "Falha de comunicação com o FedHub — tente novamente em instantes."},
            }

    def tratar(self, payload: dict, isfedcob: bool = False) -> Dict[str, Any]:
        """POST /api/fedpay/tratamento — cancela, recria com ajustes e reemite."""
        try:
            response = requests.post(
                f"{self.base_url}/api/fedpay/tratamento",
                headers=self._headers(isfedcob),
                json=payload,
                timeout=TIMEOUT_TRATAMENTO,
            )
            return self._resposta(response)
        except requests.RequestException as e:
            logger.error(f"FedPay: erro de comunicação no tratamento da fatura {payload.get('fatura')}: {e}")
            return {
                "http_status": 503,
                "body": {"status": "error", "message": "Falha de comunicação com o FedHub — o tratamento pode não ter concluído; consulte a fatura antes de repetir."},
            }
