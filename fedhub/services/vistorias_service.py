# fedhub/services/vistorias_service.py

import requests
import logging
from typing import Any, Dict, Optional

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)


class VistoriasService:
    """Service para consulta de vistorias via FedHub"""

    def __init__(self):
        from consultas.services.fedhub_service import FedhubService
        self.fedhub = FedhubService()
        self.base_url = self.fedhub.base_url

    def listar_estados(self) -> Optional[Dict[str, Any]]:
        """Lista estados das vistorias"""
        try:
            response = requests.get(
                f"{self.base_url}/api/vistorias/estados",
                headers=get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data

        except requests.RequestException as e:
            logger.error(f"Erro ao listar estados: {e}")
            return None

    def listar_vistoriadores(self) -> Optional[Dict[str, Any]]:
        """Lista vistoriadores ativos"""
        try:
            response = requests.get(
                f"{self.base_url}/api/vistorias/vistoriadores",
                headers=get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data

        except requests.RequestException as e:
            logger.error(f"Erro ao listar vistoriadores: {e}")
            return None

    def listar_administradoras(self) -> Optional[Dict[str, Any]]:
        """Lista administradoras (pessoas ativas)"""
        try:
            response = requests.get(
                f"{self.base_url}/api/vistorias/administradoras",
                headers=get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data

        except requests.RequestException as e:
            logger.error(f"Erro ao listar administradoras: {e}")
            return None

    def consultar_vistorias(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Consulta vistorias com filtros"""
        try:
            # Remove filtros vazios
            params_limpos = {k: v for k, v in params.items() if v not in [None, "", []]}

            logger.info(f"Consultando vistorias com params: {params_limpos}")

            response = requests.get(
                f"{self.base_url}/api/vistorias/",
                params=params_limpos,
                headers=get_headers(),
                timeout=60,
            )

            if response.status_code != 200:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data

        except requests.RequestException as e:
            logger.error(f"Erro ao consultar vistorias: {e}")
            return None

    def exportar_excel(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Exporta vistorias para Excel"""
        try:
            # Remove filtros vazios
            params_limpos = {k: v for k, v in params.items() if v not in [None, "", []]}

            logger.info(f"Exportando vistorias para Excel com params: {params_limpos}")

            response = requests.get(
                f"{self.base_url}/api/vistorias/exportar/excel",
                params=params_limpos,
                headers=get_headers(),
                timeout=120,
            )

            if response.status_code != 200:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                return None

            # Retorna o conteúdo do arquivo
            filename = response.headers.get("X-Filename", "vistorias.xlsx")

            return {
                "status": "success",
                "content": response.content,
                "filename": filename,
                "content_type": response.headers.get("content-type"),
            }

        except requests.RequestException as e:
            logger.error(f"Erro ao exportar Excel: {e}")
            return None

    def exportar_pdf(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Exporta vistorias para PDF"""
        try:
            # Remove filtros vazios
            params_limpos = {k: v for k, v in params.items() if v not in [None, "", []]}

            logger.info(f"Exportando vistorias para PDF com params: {params_limpos}")

            response = requests.get(
                f"{self.base_url}/api/vistorias/exportar/pdf",
                params=params_limpos,
                headers=get_headers(),
                timeout=120,
            )

            if response.status_code != 200:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                return None

            # Retorna o conteúdo do arquivo
            filename = response.headers.get("X-Filename", "relatorio-vistoria.pdf")

            return {
                "status": "success",
                "content": response.content,
                "filename": filename,
                "content_type": response.headers.get("content-type"),
            }

        except requests.RequestException as e:
            logger.error(f"Erro ao exportar PDF: {e}")
            return None
