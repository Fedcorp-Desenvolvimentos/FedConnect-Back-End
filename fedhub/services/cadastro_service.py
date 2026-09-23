# fedhub/services/cadastro_service.py
#
# Proxy transparente do módulo `etl` do FedHub (/api/etl/*) para a tela de
# cadastro novo do FedConnect — spec specs/cadastro-etl/, ADR-0008. Ao
# contrário dos outros proxies, NÃO envelopa em {sucesso, resultado}: status e
# corpo do FedHub voltam como estão, porque o contrato de campos mora na spec
# do FedHub (FedHub-Backend/specs/etl-cadastro-api/) e a tela o consome tal
# qual. Túnel fora / rede / timeout viram 503 no MESMO formato de erro do
# FedHub ({"erro","mensagem"}), para o frontend tratar um shape só.
#
# Credenciais: get_headers() (bearer do cliente `fedconnect` + chave legada +
# JWT do Kong). Timeouts justificados pelas medições do FedHub em 2026-09-23
# (lista de condomínios 1,9 s; histórico da maior administradora 1,1 s) com
# folga para o ngrok; escrita é uma transação sem banco emissor.

import logging
from typing import Any, Dict, Optional

import requests
from decouple import config

from consultas.utils.get_headers import get_auth_headers

logger = logging.getLogger(__name__)

PREFIXO = "/api/etl/"
TIMEOUT_LEITURA = 20
TIMEOUT_ESCRITA = 30
METODOS = ("GET", "POST", "PUT", "PATCH")
HEADERS_REPASSADOS = ("Idempotent-Replayed", "Retry-After")

INDISPONIVEL = {"erro": "servico_indisponivel", "mensagem": "FedHub indisponível no momento — tente novamente em instantes.", "origem": "fedconnect"}


class CadastroService:
    def __init__(self):
        self.base_url = config("FEDHUB_URL", default="http://localhost:8090").rstrip("/")

    def _url(self, rota: str) -> str:
        return f"{self.base_url}{PREFIXO}{rota.strip('/')}"

    @staticmethod
    def _headers(operador: str, request_id: str, idempotency_key: Optional[str]) -> Dict[str, str]:
        headers = {**get_auth_headers(), "Accept": "application/json", "Content-Type": "application/json", "X-Operador": operador, "X-Request-Id": request_id}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    @staticmethod
    def _resposta(response: requests.Response) -> Dict[str, Any]:
        try:
            body = response.json()
        except ValueError:
            logger.error(f"Cadastro/etl: resposta não-JSON do FedHub ({response.status_code}): {response.text[:300]}")
            return {"http_status": 503, "body": dict(INDISPONIVEL), "headers": {}}
        repassados = {h: response.headers[h] for h in HEADERS_REPASSADOS if h in response.headers}
        return {"http_status": response.status_code, "body": body, "headers": repassados}

    def repassar(self, metodo: str, rota: str, *, params=None, corpo: Optional[bytes] = None, operador: str = "", request_id: str = "", idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """{FEDHUB_URL}/api/etl/<rota> com a query e o corpo como vieram; devolve {http_status, body, headers}."""
        metodo = metodo.upper()
        timeout = TIMEOUT_LEITURA if metodo == "GET" else TIMEOUT_ESCRITA
        try:
            response = requests.request(
                metodo, self._url(rota), params=params, data=corpo if metodo != "GET" else None,
                headers=self._headers(operador, request_id, idempotency_key), timeout=timeout,
            )
            return self._resposta(response)
        except requests.RequestException as e:
            logger.error(f"Cadastro/etl: erro de comunicação em {metodo} {rota}: {type(e).__name__}")
            return {"http_status": 503, "body": {**INDISPONIVEL, "mensagem": "Falha de comunicação com o FedHub — tente novamente em instantes."}, "headers": {}}
