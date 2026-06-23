# consultas/services/firebird.py

import requests
import logging

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

class FedhubService:
    def __init__(self):
        pass
    
    # Nota Fiscal
    def buscar_nfse_por_boleto(self, documento: str):
        try:
            # 1. Buscar ID da NFSE no Firebird
            response = requests.get(
                f"{self.base_url}/api/nfse/consultar-nfse-por-boleto/{documento}/",
                headers=get_headers(),
                timeout=30,
            )

            logger.info(
                f"Buscando NFSE por boleto - URL: {response.url} | Dados: {response.text}"
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            registros = data.get("data", [])

            if not registros:
                return None

            # 2. Pegar o ID da NFSE
            id_nfse = registros[0].get("id_nfs_e")

            if not id_nfse:
                logger.warning(f"NFSE sem ID para documento {documento}")
                return None

            # 3. Segunda chamada (outro backend)
            url_nfse = f"https://fedcorp-nfs-e-django-ebh2e.ondigitalocean.app/api/consultas/nfse/{id_nfse}/"
            # url_nfse = f"http://localhost:8000/api/consultas/nfse/{id_nfse}/"

            response_nfse = requests.get(url_nfse, headers=get_headers(), timeout=30)

            logger.info(
                f"Buscando NFSE completa - URL: {url_nfse} | Dados: {response_nfse.text}"
            )

            if response_nfse.status_code != 200:
                logger.error(
                    f"Erro ao buscar NFSE completa: {response_nfse.status_code}"
                )
                return None

            nfse_data = response_nfse.json()

            return nfse_data

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar serviços: {e}")
            return None

    