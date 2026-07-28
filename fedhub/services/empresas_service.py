# fedhub/services/empresas_service.py

from decouple import config
from datetime import timedelta
import secrets
from django.utils import timezone
from typing import Any, Dict, List, Optional
import httpx
import requests
import logging

from rest_framework import settings

from django.conf import settings
from django.template.loader import render_to_string

from consultas.utils.get_headers import get_headers
import json

logger = logging.getLogger(__name__)


class EmpresasService:
    def __init__(self):
        self.base_url = config("FEDHUB_URL", default="http://localhost:8090")  # URL do serviço Fedhub

    # Empresas
    async def buscar_empresa_por_cnpj(
        self, cnpj: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Busca empresa por CNPJ no microsserviço Firebird
        """
        try:
            # Limpar CNPJ
            cnpj_limpo = "".join(filter(str.isdigit, cnpj))

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/empresas/{cnpj_limpo}"
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get("status") == "success":
                        return data.get("data", [])
                    else:
                        logger.warning(f"Empresa CNPJ {cnpj} não encontrada")
                        return None
                else:
                    logger.error(
                        f"Erro HTTP {response.status_code} ao buscar empresa {cnpj}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Erro ao buscar empresa {cnpj}: {str(e)}")
            return None

    async def buscar_todas_empresas(self, params: Optional[Dict[str, Any]] = None):
        async with httpx.AsyncClient(timeout=30.0) as client:
            query_params = {}
            if params:
                query_params = {k: v for k, v in params.items() if v not in [None, "", []]}

            response = await client.get(
                f"{self.base_url}/api/empresas/",
                params=query_params,
                headers=get_headers(),
            )

        if response.status_code != 200:
            logger.error(f"Firebird erro {response.status_code}")
            return None

        data = response.json()

        if data.get("status") != "success":
            return None

        return data.get("data")