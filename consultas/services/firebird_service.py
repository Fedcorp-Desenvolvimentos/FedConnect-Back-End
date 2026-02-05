# consultas/services/firebird.py

from typing import Any, Dict, List, Optional
import httpx
import requests
import logging

logger = logging.getLogger(__name__)

class FirebirdService:
    def __init__(self):
        # self.base_url = "http://localhost:8090"
        self.base_url = "https://steeply-outlandish-reese.ngrok-free.dev"

    def buscar_fatura_por_numero(self, numero_fatura: str):
        try:
            response = requests.get(
                f"{self.base_url}/api/faturas/fatura/{numero_fatura}",
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data.get("data")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Firebird: {e}")
            return None

    def buscar_fatura_dinamicamente(
        self,
        filtros: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Encaminha filtros dinâmicos para o microsserviço Firebird
        """
        try:
            # Remove filtros vazios / None
            params = {k: v for k, v in filtros.items() if v not in [None, "", []]}

            response = requests.get(
                f"{self.base_url}/api/faturas/fatura-dinamica",
                params=params,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(
                    f"Erro Firebird dinâmica {response.status_code} | {response.text}"
                )
                return None

            data = response.json()
            # print(f"DADOS DE RETORNO DA CONSULTA DINAMICA >>> {data}")

            if data.get("status") != "success":
                return None

            return data

        except requests.RequestException as e:
            logger.error(f"Erro comunicação Firebird dinâmica: {e}")
            return None

    def buscar_faturas_com_boletos(self, filtros: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Busca faturas com boletos associados
        """
        try:
            # Remove filtros vazios
            params = {k: v for k, v in filtros.items() if v not in [None, "", []]}

            response = requests.get(
                f"{self.base_url}/api/faturas/faturas-com-boletos",
                params=params,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(
                    f"Erro Firebird faturas-com-boletos {response.status_code} | {response.text}"
                )
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data

        except requests.RequestException as e:
            logger.error(f"Erro comunicação Firebird faturas-com-boletos: {e}")
            return None
         
    def buscar_faturas_dinamicamente_paginadas(
        self,
        filtros: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Busca faturas dinâmicas COM PAGINAÇÃO REAL
        Rota: /api/faturas/faturas-dinamicas-paginadas
        """
        try:
            # Remove filtros vazios / None
            params = {k: v for k, v in filtros.items() if v not in [None, "", []]}

            response = requests.get(
                f"{self.base_url}/api/faturas/faturas-dinamicas-paginadas",
                params=params,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(
                    f"Erro Firebird faturas-dinamicas-paginadas {response.status_code} | {response.text}"
                )
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data

        except requests.RequestException as e:
            logger.error(f"Erro comunicação Firebird faturas-dinamicas-paginadas: {e}")
            return None

    def buscar_faturas_com_boletos_paginadas(
        self,
        filtros: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Busca faturas com boletos COM PAGINAÇÃO REAL
        Rota: /api/faturas/faturas-com-boletos-paginadas
        """
        try:
            # Remove filtros vazios
            params = {k: v for k, v in filtros.items() if v not in [None, "", []]}

            response = requests.get(
                f"{self.base_url}/api/faturas/faturas-com-boletos-paginadas",
                params=params,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(
                    f"Erro Firebird faturas-com-boletos-paginadas {response.status_code} | {response.text}"
                )
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data

        except requests.RequestException as e:
            logger.error(f"Erro comunicação Firebird faturas-com-boletos-paginadas: {e}")
            return None
    
    async def buscar_todas_faturas(self, fatura_numero: str) -> Optional[List[Dict[str, Any]]]:
        """
        Busca dados da fatura no microsserviço Firebird (8090)
        Rota: /api/faturas/fatura-postos-vida/{fatura_numero}
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/faturas/fatura-postos-vida/{fatura_numero}"
                )

                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("status") == "success":
                        return data.get("data", [])
                    else:
                        logger.warning(f"Fatura {fatura_numero} não encontrada: {data.get('message')}")
                        return None
                else:
                    logger.error(f"Erro HTTP {response.status_code} ao buscar fatura {fatura_numero}")
                    return None
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout ao buscar fatura {fatura_numero}")
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar fatura {fatura_numero}: {str(e)}")
            return None

    async def buscar_empresa_por_cnpj(self, cnpj: str) -> Optional[List[Dict[str, Any]]]:
        """
        Busca empresa por CNPJ no microsserviço Firebird
        """
        try:
            # Limpar CNPJ
            cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
            
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
                    logger.error(f"Erro HTTP {response.status_code} ao buscar empresa {cnpj}")
                    return None
                    
        except Exception as e:
            logger.error(f"Erro ao buscar empresa {cnpj}: {str(e)}")
            return None

    async def buscar_todas_empresas(self):
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/api/empresas/todas-empresas"
            )

        if response.status_code != 200:
            logger.error(f"Firebird erro {response.status_code}")
            return None

        data = response.json()

        if data.get("status") != "success":
            return None

        return data.get("data")
    
    def buscar_administradora_por_nome(self, nome: str):
            try:
                response = requests.get(
                    f"{self.base_url}/api/administradoras/por-nome/{nome}",
                    timeout=30
                )

                if response.status_code != 200:
                    logger.error(f"Firebird erro {response.status_code}")
                    return None

                data = response.json()

                if data.get("status") != "success":
                    return None

                return data.get("data")

            except requests.RequestException as e:
                logger.error(f"Erro ao chamar Firebird: {e}")
                return None
        
    def buscar_administradora_por_codigo(self, codigo: str):
        try:
            response = requests.get(
                f"{self.base_url}/api/administradoras/por-codigo/{codigo}",
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data.get("data")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Firebird: {e}")
            return None
        
    def buscar_administradora_por_codigo_com_postos_vida(self, codigo: str):
        try:
            response = requests.get(
                f"{self.base_url}/api/administradoras/posto/{codigo}",
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if data.get("status") != "success":
                return None

            return data.get("data")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Firebird: {e}")
            return None
