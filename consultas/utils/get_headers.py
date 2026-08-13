from typing import Dict

from decouple import config

from consultas.utils.fedhub_auth import bearer_token


def get_auth_headers() -> Dict:
    """Só as credenciais do FedHub, sem Content-Type — para requisições
    multipart (upload de arquivos), onde forçar application/json quebra."""
    headers = {"X-Application-Key": config("FEDHUB_X_API_KEY", default="")}
    token = bearer_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def get_headers() -> Dict:
    """Headers padrão para todas as requisições JSON ao FedHub.

    Durante a migração enviam as duas credenciais: o bearer token novo
    (renovável, com escopos) e a X-Application-Key legada. Se o token não
    estiver disponível, a chave legada sozinha continua funcionando.
    """
    return {
        **get_auth_headers(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
