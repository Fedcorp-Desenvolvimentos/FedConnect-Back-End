# consultas/services/firebird.py

from decouple import config
from typing import Any, Dict, Optional
import requests
import logging

from consultas.utils.get_headers import get_headers
import json

logger = logging.getLogger(__name__)

MOTIVOS_REJEICAO = {
    "sem_registro": "não consta como enviado ao banco",
    "nao_localizado": "não encontrado na fatura",
    "inativo": "cancelado ou baixado",
    "chave_ausente": "sem fatura/nosso número",
}


def _detalhe_fedhub(response) -> dict:
    """Corpo de erro do FedHub: FastAPI embrulha o HTTPException em {"detail": {...}}."""
    try:
        corpo = response.json()
    except ValueError:
        return {}
    detalhe = corpo.get("detail", corpo) if isinstance(corpo, dict) else {}
    return detalhe if isinstance(detalhe, dict) else {}


def mensagem_rejeicao(rejeitados: list) -> str:
    """Texto para o operador a partir de `rejeitados` do FedHub (spec fedpay-pdf-somente-registrados)."""
    if not rejeitados:
        return "O FedHub recusou a emissão da 2ª via: boleto(s) sem registro no banco. Reconsulte a fatura."
    partes = []
    for r in rejeitados:
        motivo = MOTIVOS_REJEICAO.get(r.get("motivo"), r.get("motivo") or "recusado")
        partes.append(f"nosso número {r.get('nosso_numero') or '?'} ({motivo})")
    n = len(rejeitados)
    return (
        f"{n} boleto(s) não podem ter 2ª via: {'; '.join(partes)}. "
        "Reconsulte a fatura — só boletos enviados ao banco (API ou remessa) são emitidos."
    )


class FaturamentoService:
    def __init__(self):
            self.base_url = config("FEDHUB_URL", default="http://localhost:8090")
            
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
        
        
        # Segunda via de boleto
    
    def processar_dados_segunda_via_boleto(self, fatura: str):
        """Processa dados da segunda via do boleto"""
        try:
            if not fatura:
                logger.error("Fatura não informada")
                return None
            
            # logger.info(f"DADOS ANTES DE CHAMAR O FEDHUB: {fatura}")
                
            response = requests.get(
                f"{self.base_url}/api/faturamento/dados-segunda-via/{fatura}",
                headers=get_headers(),
                timeout=30.0
            )

            # FedHub (spec fedpay-pdf-somente-registrados): boletos que nunca foram
            # ao banco não entram em `data`; vêm em `sem_registro`. Todos fora → 422.
            if response.status_code == 422:
                detalhe = _detalhe_fedhub(response)
                sem_registro = detalhe.get("sem_registro") or []
                logger.warning(f"Fedhub 422 na fatura {fatura}: {len(sem_registro)} boleto(s) sem envio ao banco")
                return {"dados": [], "sem_registro": sem_registro}

            if response.status_code == 404:
                logger.warning(f"Fedhub 404 na fatura {fatura}: sem boleto ativo")
                return {"dados": [], "sem_registro": [], "nao_encontrada": True}

            if response.status_code != 200:
                logger.error(f"Fedhub erro {response.status_code}: {response.text}")
                return None

            data = response.json()
            
            if data.get("status") != "success":
                logger.error(f"Fedhub retornou status não-success: {data}")
                return None
            
            dados_lista = data.get("data", [])
            sem_registro = data.get("sem_registro") or []
            
            if not dados_lista:
                logger.error("Nenhum dado retornado pelo Fedhub")
                return None
            
            for dado in dados_lista:
                try:
                    valor_total_str = dado.get("VALOR_TOTAL", "0")
                    deducoes_str = dado.get("DEDUCOES", "0")
                    
                    def parse_br_currency(val_str):
                        if not val_str:
                            return 0.0
                        # Remove pontos de milhar e substitui vírgula por ponto
                        cleaned = val_str.replace(".", "").replace(",", ".")
                        try:
                            return float(cleaned)
                        except ValueError:
                            return 0.0
                    
                    valor_total_float = parse_br_currency(valor_total_str)
                    deducoes_float = parse_br_currency(deducoes_str)
                    
                    valor_com_deducoes = valor_total_float + deducoes_float
                    
                    # logger.info(f"Boleto {dado.get('NOSSO_NUMERO')}: "
                    #         f"Total={valor_total_str}, "
                    #         f"Deduções={deducoes_str}, "
                    #         f"Resultado={valor_com_deducoes}")
                    
                    # Formata o valor calculado para string BR
                    valor_formatado = f"{valor_com_deducoes:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    
                    dado["VALOR_DOCUMENTO"] = valor_formatado
                    dado["VALOR_TOTAL_COM_DEDUCOES"] = valor_formatado
                    
                except Exception as e:
                    logger.error(f"Erro ao processar boleto {dado.get('NOSSO_NUMERO')}: {e}")
                    # Mantém o valor original se der erro
                    dado["VALOR_DOCUMENTO"] = dado.get("VALOR_TOTAL", "0,00")
                    dado["VALOR_TOTAL_COM_DEDUCOES"] = dado.get("VALOR_TOTAL", "0,00")
            
            return {"dados": dados_lista, "sem_registro": sem_registro}

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Fedhub: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro ao processar dados: {e}", exc_info=True)
            return None
        
    @staticmethod
    def _normalize_boleto_keys(boleto: dict) -> dict:
        field_map = {
            'EMISSOR': 'emissor',
            'CNPJ_EMISSOR': 'cnpj_emissor',
            'ESTIPULANTE': 'estipulante',
            'CNPJ_ESTIPULANTE': 'cnpj_estipulante',
            'CO_ESTIPULANTE': 'co-estipulante',
            'CNPJ_CO_ESTIPULANTE': 'cnpj_co-estipulante',
            'FATURA_NUM': 'fatura_num',
            'DATA_EMISSAO': 'data_emissao',
            'VALOR_TOTAL': 'valor_total',
            'LINHA_DIGITAVEL': 'linha_digitavel',
            'LINHA_PURIFICADA': 'linha_purificada',
            'VENCIMENTO': 'vencimento',
            'AGENCIA_COD': 'agencia_cod',
            'NOSSO_NUMERO': 'nosso_numero',
            'NRO_BANCO': 'nro_banco',
            'VALOR_DOCUMENTO': 'valor_documento',
            'DEDUCOES': 'deducoes',
            'INSTRUCOES': 'instrucoes',
            'PAGADOR_NOME': 'pagador_nome',
            'PAGADOR_CNPJ': 'pagador_cnpj',
            'PAGADOR_ENDERECO': 'pagador_endereco',
            'PRODUTO': 'produto',
            'QUANTIDADE_BOL': 'quantidade_bol',
            'VIGENCIA_INICIAL': 'vigencia_inicial',
            'VIGENCIA_FINAL': 'vigencia_final',
            'CAMINHO_QRCODE': 'caminho_qrcode',
            'CAMINHO_QRIMAGEM': 'caminho_qrimagem',
        }
        normalized = {field_map.get(k, k): v for k, v in boleto.items()}

        if not normalized.get('pagador_nome'):
            normalized['pagador_nome'] = normalized.get('co-estipulante', '')
        if not normalized.get('pagador_cnpj'):
            normalized['pagador_cnpj'] = normalized.get('cnpj_co-estipulante', '')

        # Garante que os campos obrigatórios do FedHub não sejam null
        campos_obrigatorios_string = [
            'estipulante', 'cnpj_estipulante',
            'pagador_endereco', 'vigencia_inicial', 'vigencia_final',
        ]
        for campo in campos_obrigatorios_string:
            if normalized.get(campo) is None:
                normalized[campo] = ''

        # FedHub espera ambos os campos de QR; caminho_qrimagem é obrigatório
        caminho_qr = normalized.get('caminho_qrcode')
        normalized.setdefault('caminho_qrimagem', caminho_qr or '')
        normalized.setdefault('caminho_qrcode', caminho_qr or '')

        return normalized

    def emitir_segunda_via_boleto(self, fatura: str, boletos: dict) -> Optional[Dict[str, Any]]:
        try:
            if isinstance(boletos, list):
                normalized = [self._normalize_boleto_keys(b) for b in boletos]
            elif isinstance(boletos, dict):
                normalized = [self._normalize_boleto_keys(boletos)]
            else:
                normalized = boletos

            for idx, boleto in enumerate(normalized if isinstance(normalized, list) else [normalized]):
                if not boleto.get('linha_digitavel') or not boleto.get('linha_purificada'):
                    raise ValueError(
                        f"Boleto {idx + 1} da fatura {fatura} não foi gerado corretamente no FINANC. "
                        "Por favor, refaça o processo de faturamento."
                    )

            payload = json.dumps(normalized) if not isinstance(normalized, str) else normalized
                        
            response = requests.post(
                f"{self.base_url}/api/pdf-generator/gerar-boleto/",
                headers=get_headers(),
                data=payload,
                timeout=30.0
            )

            if response.status_code == 422:
                # FedHub conferiu o lote no Firebird e recusou (tudo-ou-nada):
                # item inexistente, cancelado ou nunca enviado ao banco.
                detalhe = _detalhe_fedhub(response)
                rejeitados = detalhe.get("rejeitados") or []
                logger.warning(f"FedHub recusou a 2ª via da fatura {fatura}: {rejeitados}")
                return {"status": "rejeitado", "erro": mensagem_rejeicao(rejeitados), "rejeitados": rejeitados}

            if response.status_code not in [200, 201, 202, 204]:
                logger.error(f"FedHub erro {response.status_code}: {response.text}")
                return None

            nome_arquivo = response.json().get("arquivo")
            if not nome_arquivo:
                logger.error("Nome do arquivo não retornado pelo FedHub")
                return None

            file_response = requests.delete(
                f"{self.base_url}/api/pdf-generator/excluir-boleto/{nome_arquivo}",
                headers=get_headers(),
                timeout=30.0
            )

            if file_response.status_code != 200:
                logger.error(f"Erro ao baixar/excluir boleto {nome_arquivo}: {file_response.status_code}")
                return None

            return {
                "status": "success",
                "content": file_response.content,
                "filename": nome_arquivo,
            }

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar FedHub: {e}")
            return None