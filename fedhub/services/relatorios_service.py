"""Proxy ao relatório de faturas pendentes do FedHub (spec relatorio-faturas-pendentes, RF-FAT-001).

Repassa os filtros como vieram da tela e devolve a resposta do FedHub sem
recontar nada (RNF-FAT-002). FedHub fora do ar é rotina: timeout explícito e
erros traduzidos para a view responder 502/504 sem esgotar workers.
"""
import logging
from typing import Any, Dict, Optional

import requests
from decouple import config

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

FILTROS_ACEITOS = (
    "fatura", "seguradora", "cedente", "administradora", "apolice",
    "vencimento_ini", "vencimento_fim", "vigencia_ini",
    "situacao", "classificacao", "ordenar_por",
)


class FedHubIndisponivel(Exception):
    """FedHub não respondeu (conexão recusada, DNS, túnel fechado)."""


class FedHubDemorou(Exception):
    """FedHub não respondeu dentro do timeout."""


class FedHubRecusou(Exception):
    """FedHub respondeu com erro; `status_code` e `detalhe` vêm dele."""

    def __init__(self, status_code: int, detalhe: Any):
        super().__init__(f"FedHub respondeu {status_code}")
        self.status_code = status_code
        self.detalhe = detalhe


def filtrar_parametros(query_params) -> Dict[str, str]:
    """Só os filtros do contrato, sem vazios — o FedHub aplica os padrões."""
    return {
        chave: query_params.get(chave)
        for chave in FILTROS_ACEITOS
        if query_params.get(chave) not in (None, "", "null", "undefined")
    }


class RelatoriosFedhubService:
    TIMEOUT = 60  # relatório é lista inteira; 60 s cobre a base atual com folga

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or config("FEDHUB_URL", default="http://localhost:8090")).rstrip("/")

    def faturas_pendentes(self, filtros: Dict[str, str]) -> Dict[str, Any]:
        url = f"{self.base_url}/api/faturas/relatorios/pendentes"
        try:
            resposta = requests.get(url, params=filtros, headers=get_headers(), timeout=self.TIMEOUT)
        except requests.Timeout as erro:
            logger.warning("FedHub demorou no relatório de pendentes: %s", erro)
            raise FedHubDemorou() from erro
        except requests.RequestException as erro:
            logger.warning("FedHub indisponível no relatório de pendentes: %s", erro)
            raise FedHubIndisponivel() from erro

        if resposta.status_code != 200:
            try:
                detalhe = resposta.json()
            except ValueError:
                detalhe = resposta.text[:300]
            raise FedHubRecusou(resposta.status_code, detalhe)
        return resposta.json()
