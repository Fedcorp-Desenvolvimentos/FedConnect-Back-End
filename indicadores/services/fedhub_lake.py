"""Cliente HTTP do FedConnect para as rotas `/api/lake/*` do FedHub.

Um lugar só para: montar a URL a partir de `FEDHUB_URL`, mandar os headers que
o repositório já usa com o FedHub (`get_headers`), aplicar o tempo limite e
traduzir a resposta em três famílias que quem chama precisa distinguir:

- `RespostaDoLake` (2xx): o corpo, como veio;
- `RecusaDoFedHub` (4xx): o FedHub entendeu e recusou — `erro` nomeado no
  `detail` (`referencia_desconhecida`, `meta_inexistente`, `meta_duplicada`,
  ou a validação 422 do FastAPI). Vira 400/404/409 para o front;
- `LakeIndisponivel` (5xx, timeout, conexão): o FedHub ou o lake não estão de
  pé. Vira 503 para o front, com o `erro` que o FedHub nomeou quando houver.

Nada aqui interpreta o dado: quem interpreta é a view, e quem decide o número
é o lake.
"""
from __future__ import annotations

import logging

import requests
from decouple import config

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

TIMEOUT_S = 15


class RecusaDoFedHub(Exception):
    def __init__(self, status: int, detail):
        super().__init__(f"FedHub respondeu {status}")
        self.status = status
        self.detail = detail if isinstance(detail, dict) else {"erro": "recusado", "detalhe": str(detail)}

    @property
    def erro(self) -> str:
        return self.detail.get("erro", "recusado")

    @property
    def detalhe(self) -> str:
        return self.detail.get("detalhe") or str(self.detail)


class LakeIndisponivel(Exception):
    def __init__(self, erro: str, detalhe: str = ""):
        super().__init__(erro)
        self.erro = erro
        self.detalhe = detalhe


def _url(caminho: str) -> str:
    return f"{config('FEDHUB_URL').rstrip('/')}/api/lake/{caminho.lstrip('/')}"


def chamar(metodo: str, caminho: str, *, params=None, json=None):
    """Executa a chamada e devolve o corpo (dict) ou `None` para 204."""
    try:
        resposta = requests.request(
            metodo, _url(caminho), params=params, json=json, headers=get_headers(), timeout=TIMEOUT_S
        )
    except requests.RequestException as erro:
        logger.warning("FedHub/lake fora do alcance em %s %s: %s", metodo, caminho, erro)
        raise LakeIndisponivel("fedhub_indisponivel", str(erro)) from erro

    if resposta.status_code == 204:
        return None
    try:
        corpo = resposta.json()
    except ValueError:
        corpo = {"detail": {"erro": "resposta_invalida", "detalhe": resposta.text[:200]}}

    if resposta.status_code >= 500:
        detail = (corpo or {}).get("detail") or {}
        raise LakeIndisponivel(detail.get("erro", "lake_indisponivel"), detail.get("detalhe", ""))
    detail = (corpo or {}).get("detail")
    if resposta.status_code == 404 and not (isinstance(detail, dict) and "erro" in detail):
        # 404 do próprio FastAPI ("Not Found"), sem `erro` nomeado: o FedHub que
        # respondeu não tem a rota — versão antiga no ar. É indisponibilidade,
        # não recusa; a tela tem de dizer "FedHub sem a rota", não "meta inválida".
        raise LakeIndisponivel("fedhub_sem_rota", f"o FedHub em uso não tem /api/lake/{caminho}")
    if resposta.status_code >= 400:
        raise RecusaDoFedHub(resposta.status_code, detail)
    return corpo
