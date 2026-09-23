"""Painel de TV: repasse do que o FedHub lê no Data Lake CORP.

O FedConnect roda fora da rede do escritório e não alcança o lake; o FedHub
alcança, e expõe `GET /api/lake/painel-tv` — mês corrente contra o mesmo mês
do ano anterior, por seguradora × ramo, com a meta do mês (view `vw_painel_tv`
do contrato do financeiro do lake). Este módulo só repassa: nada é somado,
convertido ou arredondado aqui — a regra mora no lake, e a tela soma o que
precisa para exibir.

Autenticação em duas pontas, de propósito diferentes: o USUÁRIO prova quem é
ao FedConnect (JWT, na view); o FEDCONNECT prova quem é ao FedHub (headers de
`get_headers`, os mesmos dos outros serviços que falam com ele).
"""
from __future__ import annotations

import logging

import requests
from decouple import config

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

TIMEOUT_S = 15


class LakeIndisponivel(Exception):
    """O FedHub respondeu, mas o lake não: `erro` é o nome que o FedHub dá ao estado
    (`lake_nao_configurado`, `lake_indisponivel`, `contrato_nao_publicado`)."""

    def __init__(self, erro: str, detalhe: str = ""):
        super().__init__(erro)
        self.erro = erro
        self.detalhe = detalhe


def linhas() -> list[dict]:
    base_url = config("FEDHUB_URL").rstrip("/")
    resposta = requests.get(f"{base_url}/api/lake/painel-tv", headers=get_headers(), timeout=TIMEOUT_S)
    if resposta.status_code == 503:
        detail = (resposta.json() or {}).get("detail") or {}
        raise LakeIndisponivel(detail.get("erro", "lake_indisponivel"), detail.get("detalhe", ""))
    resposta.raise_for_status()
    return resposta.json().get("linhas", [])
