# consultas/services/firebird.py

from typing import Any, Dict, Optional
import requests
import logging

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

class FedhubService:
    def __init__(self):
        pass

    def buscar_faturas_comissoes(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Busca faturas para emissão de recibos de comissões
        GET /api/vouchers/buscar-faturas-comissoes
        """
        try:
            params_limpos = {k: v for k, v in params.items() if v not in [None, "", []]}
            response = requests.get(
                f"{self.base_url}/api/vouchers/buscar-faturas-comissoes",
                params=params_limpos,
                headers=get_headers(),
                timeout=30,
            )
            if response.status_code != 200:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                return None
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar faturas comissão: {e}")
            return None

    def buscar_comissoes_por_fatura(self, numero_fatura: str) -> Optional[Dict[str, Any]]:
        """
        Busca comissões individuais de uma fatura
        GET /api/vouchers/comissoes-por-fatura/{numero_fatura}
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/vouchers/comissoes-por-fatura/{numero_fatura}",
                headers=get_headers(),
                timeout=30,
            )
            if response.status_code != 200:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                return None
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar comissões por fatura: {e}")
            return None

    def emitir_voucher(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Emite voucher/recibo de comissão
        POST /api/vouchers/emitir
        Payload: {fatura, parcela, tipo_fat}
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/vouchers/emitir",
                json=payload,
                headers=get_headers(),
                timeout=30,
            )
            if response.status_code not in [200, 201]:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                return None
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Erro ao emitir voucher: {e}")
            return None



