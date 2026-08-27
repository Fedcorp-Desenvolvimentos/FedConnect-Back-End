# fedhub/services/envio_porto_service.py
#
# Proxy das rotas /api/envio-porto/* do FedHub (spec FedHub-Backend/specs/
# envio-porto, v2) para a tela Envio Porto do FedConnect. Mesmo padrão do
# fedpay_service.py: credenciais do FedHub via get_headers() (Bearer +
# chave legada), resposta normalizada {"http_status", "body"}, túnel fora
# vira 503 legível. O `operador` (e-mail do usuário logado) é injetado pela
# VIEW a partir do JWT — nunca vem do cliente.

import logging
from typing import Any, Dict, Optional

import requests
from decouple import config

from consultas.utils.get_headers import get_auth_headers, get_headers

logger = logging.getLogger(__name__)

TIMEOUT_CURTO = 30      # criar job, status, listas
TIMEOUT_DOWNLOAD = 300  # planilhas de até alguns MB
TIMEOUT_SFTP = 300      # upload à Porto é síncrono no FedHub

_INDISPONIVEL = {"status": "error", "message": "FedHub indisponível no momento — tente novamente em instantes."}


class EnvioPortoService:
    def __init__(self):
        self.base_url = config("FEDHUB_URL", default="http://localhost:8090").rstrip("/")

    # ---------- infra ----------
    def _url(self, rota: str) -> str:
        return f"{self.base_url}/api/envio-porto/{rota.lstrip('/')}"

    def _resposta(self, response: requests.Response) -> Dict[str, Any]:
        try:
            body = response.json()
        except ValueError:
            logger.error(f"EnvioPorto: resposta não-JSON do FedHub ({response.status_code}): {response.text[:300]}")
            return {"http_status": 503, "body": dict(_INDISPONIVEL)}
        if isinstance(body, dict) and isinstance(body.get("detail"), dict):
            body = body["detail"]
        elif isinstance(body, dict) and isinstance(body.get("detail"), str):
            body = {"status": "error", "message": body["detail"]}
        elif isinstance(body, dict) and isinstance(body.get("detail"), list):  # 422 do FastAPI
            campos = "; ".join(f"{'.'.join(str(x) for x in e.get('loc', [])[1:])}: {e.get('msg')}" for e in body["detail"])
            body = {"status": "error", "message": f"Dados inválidos — {campos}", "detail": body["detail"]}
        return {"http_status": response.status_code, "body": body}

    def _chamar(self, metodo: str, rota: str, *, json: Optional[dict] = None, params: Optional[dict] = None, timeout: int = TIMEOUT_CURTO) -> Dict[str, Any]:
        try:
            response = requests.request(metodo, self._url(rota), headers=get_headers(), json=json, params=params, timeout=timeout)
            return self._resposta(response)
        except requests.RequestException as e:
            logger.error(f"EnvioPorto: erro de comunicação em {metodo} {rota}: {e}")
            return {"http_status": 503, "body": {"status": "error", "message": "Falha de comunicação com o FedHub — tente novamente em instantes."}}

    # ---------- Porto Assistência ----------
    def gerar_assistencia(self, inivig: str, produtos: dict, operador: str) -> Dict[str, Any]:
        """POST /assistencia/gerar → 202 {job_id, status} | 409 | 422."""
        return self._chamar("POST", "assistencia/gerar", json={"inivig": inivig, "produtos": produtos, "operador": operador})

    # ---------- Jobs ----------
    def listar_jobs(self, tipo: Optional[str] = None, limite: int = 20) -> Dict[str, Any]:
        params = {"limite": limite}
        if tipo:
            params["tipo"] = tipo
        return self._chamar("GET", "jobs", params=params)

    def job(self, job_id: str) -> Dict[str, Any]:
        return self._chamar("GET", f"jobs/{job_id}")

    def download(self, job_id: str) -> Dict[str, Any]:
        """Planilha do job: {"http_status": 200, "conteudo": bytes, "nome": str}
        ou {"http_status", "body"} nos erros (409/410/404/503)."""
        try:
            response = requests.get(self._url(f"jobs/{job_id}/download"), headers=get_auth_headers(), timeout=TIMEOUT_DOWNLOAD, stream=True)
        except requests.RequestException as e:
            logger.error(f"EnvioPorto: erro de comunicação no download do job {job_id}: {e}")
            return {"http_status": 503, "body": {"status": "error", "message": "Falha de comunicação com o FedHub — tente novamente em instantes."}}
        if response.status_code != 200:
            return self._resposta(response)
        nome = f"envio-porto-{job_id}.xlsx"
        disposicao = response.headers.get("Content-Disposition") or ""
        if "filename=" in disposicao:
            nome = disposicao.split("filename=")[-1].strip().strip('"').strip("'") or nome
        return {"http_status": 200, "conteudo": response.content, "nome": nome}

    def enviar_sftp(self, job_id: str, operador: str, reenviar: bool = False) -> Dict[str, Any]:
        """POST /jobs/{id}/enviar-sftp — a confirmação explícita é obrigatória
        no FedHub (RF-EPO-004); a view só chama este método após a confirmação
        digitada na tela."""
        payload = {"confirmar": True, "operador": operador}
        if reenviar:
            payload["reenviar"] = True
        return self._chamar("POST", f"jobs/{job_id}/enviar-sftp", json=payload, timeout=TIMEOUT_SFTP)

    # ---------- Subgrupos Vida ----------
    def vida_subgrupos(self) -> Dict[str, Any]:
        return self._chamar("GET", "vida/subgrupos")

    def vida_gerar(self, vigencia: str, subgrupos: list, operador: str) -> Dict[str, Any]:
        return self._chamar("POST", "vida/gerar", json={"vigencia": vigencia, "subgrupos": subgrupos, "operador": operador})

    def vida_inconsistencias(self, vigencia: str) -> Dict[str, Any]:
        return self._chamar("GET", "vida/inconsistencias", params={"vigencia": vigencia})

    # ---------- Dental (placeholders: o FedHub responde 501) ----------
    def dental(self, rota: str) -> Dict[str, Any]:
        return self._chamar("GET", f"dental/{rota}")
