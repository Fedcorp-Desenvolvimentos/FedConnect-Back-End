# consultas/services/firebird.py

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


class ComissaoService:
    def __init__(self):
        self.base_url = config("FEDHUB_URL", default="http://localhost:8090").rstrip("/")  # URL do serviço Fedhub

    # ============================================================
    # Comissões / Vouchers (Recibos de Comissões)
    # ============================================================
    
    def consultar_comissoes(self, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Consulta comissões com voucher (consulta/histórico)
        GET /api/vouchers/consultar-faturas-comissoes
        """
        try:
            query_params = {}
            
            if params:
                for key, value in params.items():
                    if value not in [None, '', 'null']:
                        query_params[key] = value
            
            logger.info(f"Chamando FastAPI CONSULTA com params: {query_params}")
            
            response = requests.get(
                f"{self.base_url}/api/vouchers/consultar-faturas-comissoes",
                params=query_params,
                headers=get_headers(),
                timeout=60,
            )
            
            if response.status_code != 200:
                logger.error(f"FastAPI erro {response.status_code}: {response.text}")
                return None
            
            data = response.json()
            return {
                "status": "success",
                "total_registros": data.get("total_registros", 0),
                "data": data.get("data", []),
                "has_more": data.get("has_more", False),
                "filtros_aplicados": data.get("filtros_aplicados", {}),
            }
            
        except Exception as e:
            logger.error(f"Erro ao consultar comissões: {e}")
            return None
    
    def buscar_produtos_por_favorecido(self, favorecido: str) -> Optional[Dict[str, Any]]:
        """
        Busca lista de produtos distintos por favorecido
        GET /api/vouchers/produtos-por-favorecido?favorecido=...
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/vouchers/produtos-por-favorecido",
                params={"favorecido": favorecido},
                headers=get_headers(),
                timeout=30,
            )
            
            if response.status_code != 200:
                logger.error(f"FastAPI erro {response.status_code}: {response.text}")
                return None
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Erro ao buscar produtos por favorecido: {e}")
            return None
    
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

    def buscar_comissoes_v2(self, data_corte: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Busca comissões usando a V2 do FastAPI (100% consistente)
        GET /api/vouchers/buscar-faturas-comissoes-v2
        """
        try:
            # Inicializa params se None
            if params is None:
                params = {}
            
            # Valida formato da data
            from datetime import datetime
            datetime.strptime(data_corte, '%Y-%m-%d')
            
            # Monta os parâmetros da query (inclui data_corte)
            query_params = {}
            
            # Adiciona data_corte como parâmetro
            query_params['data_corte'] = data_corte
            
            # Limpa parâmetros vazios
            for key, value in params.items():
                if value not in [None, "", "null"]:
                    # Converte favorecido para int se necessário
                    if key == 'favorecido' and value:
                        try:
                            query_params[key] = int(value)
                        except ValueError:
                            query_params[key] = value
                    else:
                        query_params[key] = value
            
            logger.info(f"Chamando FastAPI V2 com params: {query_params}")
            
            # 🔥 ROTA CORRETA
            response = requests.get(
                f"{self.base_url}/api/vouchers/buscar-faturas-comissoes",
                params=query_params,
                headers=get_headers(),
                timeout=120,  # Timeout maior para queries complexas
            )
            
            if response.status_code != 200:
                logger.error(f"FastAPI V2 erro {response.status_code}: {response.text}")
                return None
                
            data = response.json()
            
            # Verifica status da resposta
            if data.get("status") != "success":
                logger.error(f"FastAPI V2 retornou erro: {data}")
                return None
            
            if "data" in data:
                
                logger.info(f"Dados retornados: {data.get('data')[:5]}... (total {len(data.get('data', []))} registros)")
                return {
                    "status": "success",
                    "total_registros": data.get("total_registros", len(data.get("data", []))),
                    "has_more": data.get("has_more", False),
                    "data": data.get("data", []),
                }
                
            return data
            
        except ValueError as e:
            logger.error(f"Formato de data inválido: {data_corte}. Use YYYY-MM-DD")
            return {
                "status": "error",
                "message": f"Formato de data inválido: {data_corte}. Use YYYY-MM-DD"
            }
        except requests.RequestException as e:
            logger.error(f"Erro ao chamar FastAPI V2: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao chamar FastAPI V2: {e}")
            return None   

    def emitir_recibo_comissao(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Emite recibo do corretor via FastAPI
        POST /api/vouchers/emitir-recibo
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/vouchers/emitir-recibo",
                json=payload,
                headers=get_headers(),
                timeout=120,
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"FastAPI erro {response.status_code}: {response.text}")
                return None
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Erro ao emitir recibo do corretor: {e}")
            return None
    
    def emitir_voucher_comissao(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Emite voucher de comissão via FastAPI
        POST /api/voucher/emitir-voucher
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/vouchers/emitir-voucher",
                json=payload,
                headers=get_headers(),
                timeout=120,  # Timeout maior para gerar PDF
            )
            if response.status_code not in [200, 201]:
                logger.error(f"FastAPI erro {response.status_code}: {response.text}")
                return None
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Erro ao emitir voucher: {e}")
            return None
        
    def cancelar_comissao(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Cancela uma comissão via FastAPI
        POST /api/vouchers/cancelar-comissao
        
        Payload esperado:
        {
            "numero_comissao": "20129486",
            "parcela": 1,
            "documento": "0001525504",
            "favorecido": "0000002098",
            "tipo_comissao": "BENEFICIO",
            "voucher": "20129486",
            "motivo_cancelamento": "Cancelamento solicitado pelo usuário"
        }
        """
        try:
            logger.info(f"Cancelando comissão no FedHub: {payload}")
            
            response = requests.post(
                f"{self.base_url}/api/vouchers/cancelar-comissao",
                json=payload,
                headers=get_headers(),
                timeout=300,
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"FastAPI erro {response.status_code}: {response.text}")
                return {
                    "status": "error",
                    "message": f"Erro na API do FedHub: {response.status_code}"
                }
            
            data = response.json()
            
            # Verifica se o FedHub retornou sucesso
            if data.get("status") == "success":
                return {
                    "status": "success",
                    "message": data.get("message", "Comissão cancelada com sucesso"),
                    "data": data.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": data.get("message", "Falha ao cancelar comissão")
                }
                
        except requests.RequestException as e:
            logger.error(f"Erro ao chamar FastAPI para cancelar comissão: {e}")
            return {
                "status": "error",
                "message": f"Erro de comunicação: {str(e)}"
            }