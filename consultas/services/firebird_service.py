# consultas/services/firebird.py

from datetime import timedelta
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

logger = logging.getLogger(__name__)

class FirebirdService:
    def __init__(self):
        self.base_url = "https://fedhub-api-local.ngrok.app"
        # self.base_url = "http://localhost:8090"

    # Faturas
    def buscar_fatura_por_numero(self, numero_fatura: str):
        try:
            response = requests.get(
                f"{self.base_url}/api/faturas/fatura/{numero_fatura}",
                headers=get_headers(),
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
                headers=get_headers(),
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

    def buscar_faturamento(self, filtros: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Busca faturas com boletos associados - usa a rota /faturamento do FedHub
        """
        try:
            # Remove filtros vazios
            params = {k: v for k, v in filtros.items() if v not in [None, "", []]}

            # IMPORTANTE: Garantir que page e page_size sejam inteiros
            if 'page' in params:
                params['page'] = int(params['page'])
            if 'page_size' in params:
                params['page_size'] = int(params['page_size'])

            logger.info(f"Chamando FedHub - faturamento com params: {params}")

            response = requests.get(
                f"{self.base_url}/api/faturas/faturamento",
                params=params,
                headers=get_headers(),
                timeout=30
            )

            if response.status_code != 200:
                logger.error(
                    f"Erro ao consultar FedHub - FATURAMENTO - {response.status_code} | {response.text}"
                )
                return None

            data = response.json()
            # logger.info(f"Resposta do FedHub DADOS COMPLETOS - FATURAMENTO: {data}")
            # logger.info(f"Resposta do FedHub: {data.get('status')}")
            
            logger.info(f"Quantidade de faturas retornadas: {len(data.get('data', [])) if data.get('status') == 'success' else 'N/A'}")

            if data.get("status") != "success":
                return None

            return data

        except requests.RequestException as e:
            logger.error(f"Erro comunicação com o FedHub - FATURAMENTO: {e}")
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
                headers=get_headers(),
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

    def buscar_faturas_com_boletos_e_segurados(self, filtros: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Busca faturas com boletos associados
        """
        try:
            # Remove filtros vazios
            params = {k: v for k, v in filtros.items() if v not in [None, "", []]}

            response = requests.get(
                f"{self.base_url}/api/faturas/faturas-com-boletos-e-segurados",
                params=params,
                headers=get_headers(),
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
                headers=get_headers(),
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
                headers=get_headers(),
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

    async def buscar_fatura_por_nosso_numero(self, nosso_numero: str):
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    f"{self.base_url}/api/boletos/buscar/por-nosso-numero/{nosso_numero}/",
                    headers=get_headers()
                )

                if response.status_code != 200:
                    logger.error(f"Fedhub erro {response.status_code}: {response.text}")
                    return None

                data = response.json()
                return data.get("data") if data.get("status") == "success" else None

        except httpx.RequestError as e:
            logger.error(f"Erro ao chamar Fedhub: {e}")
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


    # Empresas
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
                f"{self.base_url}/api/empresas/",
                headers=get_headers(),
            )

        if response.status_code != 200:
            logger.error(f"Firebird erro {response.status_code}")
            return None

        data = response.json()

        if data.get("status") != "success":
            return None

        return data.get("data")


    # Administradoras
    def buscar_administradora_por_nome(self, nome: str):
            try:
                response = requests.get(
                    f"{self.base_url}/api/administradoras/por-nome/{nome}",
                    timeout=30,
                    headers=get_headers()
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
                headers=get_headers(),
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
                headers=get_headers(),
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

    # Corretores
    def buscar_corretor_por_codigo(self, codigo: str):
        try:
            response = requests.get(
                f"{self.base_url}/api/corretores/corretor/{codigo}",
                headers=get_headers(),
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if not data.get("encontrado"):
                return None

            return data.get("dados")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Firebird: {e}")
            return None
        
    # Cedentes
    def buscar_cedente_por_codigo(self, codigo: str):
        try:
            response = requests.get(
                f"{self.base_url}/api/cedentes/cedente/{codigo}",
                headers=get_headers(),
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Firebird erro {response.status_code}")
                return None

            data = response.json()

            if not data.get("encontrado"):
                return None

            return data.get("dados")

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar Firebird: {e}")
            return None

    # Nota Fiscal
    def buscar_nfse_por_boleto(self, documento: str):
        try:
            # 1. Buscar ID da NFSE no Firebird
            response = requests.get(
                f"{self.base_url}/api/nfse/consultar-nfse-por-boleto/{documento}/",
                headers=get_headers(),
                timeout=30
            )
            
            logger.info(f"Buscando NFSE por boleto - URL: {response.url} | Dados: {response.text}")

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

            response_nfse = requests.get(
                url_nfse,
                headers=get_headers(),
                timeout=30
            )
            
            logger.info(f"Buscando NFSE completa - URL: {url_nfse} | Dados: {response_nfse.text}")

            if response_nfse.status_code != 200:
                logger.error(f"Erro ao buscar NFSE completa: {response_nfse.status_code}")
                return None

            nfse_data = response_nfse.json()

            return nfse_data

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar serviços: {e}")
            return None
    
    
    def enviar_email_recuperacao_senha(self, email: str, user: Any) -> bool:
        try:
            with httpx.Client() as client:
                
                # 🔐 Gerar NOVO token (sobrescreve o anterior)
                reset_token = secrets.token_urlsafe(32)
                expires_at = timezone.now() + timedelta(hours=24)
                
                # SOBRESCREVE o token anterior (se existir)
                user.reset_password_token = reset_token
                user.reset_password_token_created_at = timezone.now()
                user.reset_password_token_expires_at = expires_at
                # Não precisa limpar antes, apenas sobrescreve
                user.save(update_fields=[
                    'reset_password_token', 
                    'reset_password_token_created_at', 
                    'reset_password_token_expires_at'
                ])
                
                logger.info(f"Novo token gerado (sobrescreveu anterior) para: {user.email}")
                logger.info(f"Token expira em: {expires_at}")
                
                frontend_url = settings.FRONTEND_URL
                
                # Construir link de reset
                reset_url = f"{frontend_url}/resetar-senha/{reset_token}"
                
                logger.info(f"Link de reset gerado: {reset_url}")
                
                html_body = render_to_string('email/resetar_senha.html', {
                    'nome_usuario': user.nome_completo or user.email,
                    'reset_url': reset_url,
                })
                
                response = client.post(
                    f"{self.base_url}/api/email/send/gmail",
                    json={
                        "to_email": email,
                        "subject": "Redefinição de Senha - FedConnect",
                        "body": html_body,
                        "is_html": True
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    logger.info(f"Email enviado com sucesso via Gateway para: {email}")
                else:
                    logger.error(f"Gateway retornou erro {response.status_code}: {response.text}")

            return True

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar serviço de email: {e}")
            return False
    
    # Processamento de pagamento de boleto via webhook do Santander
    async def processar_pagamento_boleto(self, documento: str, fatura: str, dados_pagamento: dict):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/santander/webhook/processar-pagamento/{documento}/{fatura}",
                    headers=get_headers(),
                    json=dados_pagamento
                )

                if response.status_code != 200:
                    logger.error(f"Fedhub erro {response.status_code}: {response.text}")
                    return None

                data = response.json()
                return data.get("data") if data.get("status") == "success" else None

        except httpx.RequestError as e:
            logger.error(f"Erro ao chamar Fedhub: {e}")
            return None