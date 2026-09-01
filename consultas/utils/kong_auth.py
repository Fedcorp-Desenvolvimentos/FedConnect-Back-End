# consultas/utils/kong_auth.py
#
# JWT do Kong — a camada de BORDA do gateway (ver FedHub-Backend/GATEWAY.md).
# Não confundir com o bearer interno do FedHub (fedhub_auth.py): o token do
# Kong abre o gateway; o token do FedHub autoriza dentro do FedHub.
#
# O token é gerado LOCALMENTE (HS256 com o segredo compartilhado do consumer
# no kong.yml do droplet) — não há emissor central, a assinatura é validada
# matematicamente pelo Kong. Cache thread-safe, renovação 60s antes do exp.
#
# Fail-open deliberado: sem FEDHUB_JWT_SECRET no ambiente, gateway_headers()
# retorna {} e nada muda — dev local (FedHub direto) e rollback via ngrok
# continuam funcionando sem qualquer configuração extra.
#
# Envs:
#   FEDHUB_JWT_KEY     — key do consumer no kong.yml (ex. "fedconnect")
#   FEDHUB_JWT_SECRET  — segredo do consumer (nunca em commit)
#   FEDHUB_GATEWAY_AUTH_HEADER — header onde o token vai (default
#       X-Gateway-Authorization, que exige `header_names` no plugin jwt do
#       kong.yml; usar "Authorization" só se o Kong ficar com o default —
#       nesse caso o bearer interno do FedHub é sobrescrito e o FedHub
#       autentica apenas pela X-Application-Key legada).

import threading
import time

import jwt
from decouple import config

_VALIDADE_S = 900  # 15 min (payload do GATEWAY.md)
_MARGEM_RENOVACAO = 60  # renova 60s antes de expirar

HEADER_PADRAO = "X-Gateway-Authorization"


class KongAuth:
    def __init__(self):
        self._lock = threading.Lock()
        self._token = None
        self._expira_em = 0.0

    def token(self) -> str | None:
        segredo = config("FEDHUB_JWT_SECRET", default="")
        if not segredo:
            return None
        agora = time.time()
        with self._lock:
            if self._token is None or agora >= self._expira_em - _MARGEM_RENOVACAO:
                exp = int(agora) + _VALIDADE_S
                self._token = jwt.encode(
                    {"iss": config("FEDHUB_JWT_KEY", default="fedconnect"), "exp": exp},
                    segredo,
                    algorithm="HS256",
                )
                self._expira_em = float(exp)
        return self._token


_auth = KongAuth()


def kong_token() -> str | None:
    """Token do Kong (cacheado) ou None se o gateway não está configurado."""
    return _auth.token()


def gateway_headers() -> dict:
    """Header de autenticação do gateway, ou {} fora do gateway."""
    token = kong_token()
    if not token:
        return {}
    header = config("FEDHUB_GATEWAY_AUTH_HEADER", default=HEADER_PADRAO)
    return {header: f"Bearer {token}"}
