# consultas/services/analytics_service.py

import logging
import httpx
from typing import Dict, Any, Optional
from datetime import date
from django.conf import settings

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Serviço para comunicação com o microserviço de Analytics (FastAPI)"""
    
    def __init__(self):
        # URL do FastAPI (ajuste conforme sua configuração)
        self.base_url = "https://fedhub-api-local.ngrok.app"
        # self.base_url = "http://localhost:8090"
    
    def _get_headers(self) -> Dict[str, str]:
        """Retorna headers padrão para comunicação com o FastAPI"""
        return {
            "X-API-Key": getattr(settings, 'FASTAPI_API_KEY', 'internal-secret-key'),
            "Content-Type": "application/json"
        }
    
    async def get_faturamento_periodo(
        self, 
        data_ini: date, 
        data_fim: date
    ) -> Optional[Dict[str, Any]]:
        """1. Faturamento por período (agregado por mês)"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/analytics/faturamento",
                    params={
                        "data_ini": data_ini.isoformat(),
                        "data_fim": data_fim.isoformat()
                    },
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Erro FastAPI: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Erro ao chamar FastAPI (faturamento_periodo): {e}")
            return None
    
    async def get_top_administradoras(self, limit: int = 10) -> Optional[Dict[str, Any]]:
        """2. Top administradoras que mais faturam"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/analytics/administradoras/top",
                    params={"limit": limit},
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Erro FastAPI: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Erro ao chamar FastAPI (top_administradoras): {e}")
            return None
    
    async def get_inadimplencia(self) -> Optional[Dict[str, Any]]:
        """3. Métricas de inadimplência"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/analytics/inadimplencia",
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Erro FastAPI: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Erro ao chamar FastAPI (inadimplencia): {e}")
            return None
    
    async def get_faturamento_por_administradora(
        self, 
        data_ini: date, 
        data_fim: date
    ) -> Optional[Dict[str, Any]]:
        """4. Faturamento detalhado por administradora no período"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/analytics/administradoras/faturamento",
                    params={
                        "data_ini": data_ini.isoformat(),
                        "data_fim": data_fim.isoformat()
                    },
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Erro FastAPI: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Erro ao chamar FastAPI (faturamento_por_administradora): {e}")
            return None
    
    async def get_status_faturas(self) -> Optional[Dict[str, Any]]:
        """5. Distribuição de faturas por status"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/analytics/faturas/status",
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Erro FastAPI: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Erro ao chamar FastAPI (status_faturas): {e}")
            return None
    
    async def get_dashboard_completo(
        self, 
        data_ini: date, 
        data_fim: date
    ) -> Optional[Dict[str, Any]]:
        """6. Dashboard completo (busca paralela via FastAPI)"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/analytics/dashboard",
                    params={
                        "data_ini": data_ini.isoformat(),
                        "data_fim": data_fim.isoformat()
                    },
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Erro FastAPI: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Erro ao chamar FastAPI (dashboard_completo): {e}")
            return None