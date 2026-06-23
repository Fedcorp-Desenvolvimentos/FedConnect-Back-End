# consultas/services/firebird.py

from typing import Any, Dict, List, Optional
import httpx
import requests
import logging

from consultas.utils.get_headers import get_headers

logger = logging.getLogger(__name__)

class FedhubService:
    def __init__(self):
        pass

    # Faturas
    def buscar_fatura_por_numero(self, numero_fatura: str):
        try:
            response = requests.get(
                f"{self.base_url}/api/faturas/fatura/{numero_fatura}",
                headers=get_headers(),
                timeout=30,
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

    def buscar_faturamento(self, filtros: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Busca faturas com boletos associados - usa a rota /faturamento do FedHub
        """
        try:
            # Remove filtros vazios
            params = {k: v for k, v in filtros.items() if v not in [None, "", []]}

            # IMPORTANTE: Garantir que page e page_size sejam inteiros
            if "page" in params:
                params["page"] = int(params["page"])
            if "page_size" in params:
                params["page_size"] = int(params["page_size"])

            logger.info(f"Chamando FedHub - faturamento com params: {params}")

            response = requests.get(
                f"{self.base_url}/api/faturas/faturamento",
                params=params,
                headers=get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(
                    f"Erro ao consultar FedHub - FATURAMENTO - {response.status_code} | {response.text}"
                )
                return None

            data = response.json()
            # logger.info(f"Resposta do FedHub DADOS COMPLETOS - FATURAMENTO: {data}")
            # logger.info(f"Resposta do FedHub: {data.get('status')}")

            logger.info(
                f"Quantidade de faturas retornadas: {len(data.get('data', [])) if data.get('status') == 'success' else 'N/A'}"
            )

            if data.get("status") != "success":
                return None

            return data

        except requests.RequestException as e:
            logger.error(f"Erro comunicação com o FedHub - FATURAMENTO: {e}")
            return None

    async def buscar_fatura_por_nosso_numero(self, nosso_numero: str):
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    f"{self.base_url}/api/boletos/buscar/por-nosso-numero/{nosso_numero}/",
                    headers=get_headers(),
                )

                if response.status_code != 200:
                    logger.error(f"Fedhub erro {response.status_code}: {response.text}")
                    return None

                data = response.json()
                return data.get("data") if data.get("status") == "success" else None

        except httpx.RequestError as e:
            logger.error(f"Erro ao chamar Fedhub: {e}")
            return None

    async def buscar_todas_faturas(
        self, fatura_numero: str
    ) -> Optional[List[Dict[str, Any]]]:
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
                        logger.warning(
                            f"Fatura {fatura_numero} não encontrada: {data.get('message')}"
                        )
                        return None
                else:
                    logger.error(
                        f"Erro HTTP {response.status_code} ao buscar fatura {fatura_numero}"
                    )
                    return None

        except httpx.TimeoutException:
            logger.error(f"Timeout ao buscar fatura {fatura_numero}")
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar fatura {fatura_numero}: {str(e)}")
            return None

    def rodar_procedure_tratamento_erro(self) -> Optional[Dict[str, Any]]:
        """
        Roda a procedure de tratamento de erro do FedHub (FastAPI)
        POST /fatura/rodar-procedure-tratamento-erro/
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/faturas/fatura/rodar-procedure-tratamento-erro/",
                headers=get_headers(),
                timeout=60,  # Timeout maior pois pode demorar
            )

            if response.status_code != 200:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                return {
                    "status": "error",
                    "message": f"Erro na API do FedHub: {response.status_code}",
                }

            data = response.json()

            # Verificar formato da resposta do FastAPI
            if data.get("status") == "success":
                return {
                    "status": "success",
                    "message": data.get("message", "Procedure executada com sucesso"),
                    "data": data.get("data", {}),
                }
            else:
                return {
                    "status": "error",
                    "message": data.get("message", "Falha na execução da procedure"),
                }

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar FedHub para procedure: {e}")
            return {"status": "error", "message": f"Erro de comunicação: {str(e)}"}

    def converter_boleto_csv(self, fatura: int) -> Optional[Dict[str, Any]]:
        """
        Converte boletos de uma fatura para CSV
        GET /api/faturas/fatura/converter-boleto-csv/{fatura}/
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/faturas/fatura/converter-boleto-csv/{fatura}/",
                headers=get_headers(),
                timeout=60,  # Timeout maior pois pode gerar muitos dados
            )
            
            logger.info(f"Chamando FedHub para converter CSV - URL: {response.url} | Status: {response.status_code}")
            
            # Verifica se é uma resposta de arquivo CSV (content-type: text/csv)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")

                # Se for CSV, processa como texto
                if "text/csv" in content_type:
                    return {
                        "status": "success",
                        "csv_content": response.text,
                        "filename": (
                            response.headers.get("content-disposition", "")
                            .split("filename=")[-1]
                            .strip('"')
                            if "filename="
                            in response.headers.get("content-disposition", "")
                            else f"boletos_fatura_{fatura}.csv"
                        ),
                    }

                # Se for JSON, parse normal
                data = response.json()

                # Verificar estrutura da resposta do FedHub
                if data.get("status") == "success":
                    # Se já tem csv_content, retorna direto
                    if "csv_content" in data:
                        return data

                    # Se tem data mas não csv_content, converte aqui
                    if "data" in data and data["data"]:
                        # Importa a função de conversão
                        from consultas.utils.csv_utils import convert_to_csv
                        logger.info(f" resposta do fedhub: {response.text}")
                        dados = [
                            {k.upper(): v for k, v in item.items()}
                            for item in data["data"]
                        ]
                        csv_content = convert_to_csv(
                            dados,
                            fieldnames=[
                                "CNPJ", "POSTO", "NOME", "LINHA_BARRA",
                                "LINHA_DIGITAVEL", "VENCIMENTO", "VALOR"
                            ]
                        )

                        return {
                            "status": "success",
                            "csv_content": csv_content,
                            "filename": f"boletos_fatura_{fatura}.csv",
                            "total_registros": len(data["data"]),
                        }

                # Se status for not_found
                if data.get("status") == "not_found":
                    return data

                # Se chegou aqui, algo deu errado
                logger.error(f"Resposta inesperada do FedHub: {data}")
                return None

            # Status diferente de 200
            logger.error(f"FedHub erro {response.status_code}: {response.text}")
            return {
                "status": "error",
                "message": f"Erro na API do FedHub: {response.status_code}",
            }

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar FedHub para converter CSV: {e}")
            return {"status": "error", "message": f"Erro de comunicação: {str(e)}"}

