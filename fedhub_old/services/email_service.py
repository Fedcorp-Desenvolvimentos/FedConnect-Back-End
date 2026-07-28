# consultas/services/firebird.py

from datetime import timedelta
from datetime import timedelta
import secrets
from django.utils import timezone
from typing import Any
import httpx
import requests
import logging

from rest_framework import settings

from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

class FedhubService:
    def __init__(self):
        pass

    # Email
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
                user.save(
                    update_fields=[
                        "reset_password_token",
                        "reset_password_token_created_at",
                        "reset_password_token_expires_at",
                    ]
                )

                logger.info(
                    f"Novo token gerado (sobrescreveu anterior) para: {user.email}"
                )
                logger.info(f"Token expira em: {expires_at}")

                frontend_url = settings.FRONTEND_URL

                # Construir link de reset
                reset_url = f"{frontend_url}/resetar-senha/{reset_token}"

                logger.info(f"Link de reset gerado: {reset_url}")

                html_body = render_to_string(
                    "email/resetar_senha.html",
                    {
                        "nome_usuario": user.nome_completo or user.email,
                        "reset_url": reset_url,
                    },
                )

                response = client.post(
                    f"{self.base_url}/api/email/send/gmail",
                    json={
                        "to_email": email,
                        "subject": "Redefinição de Senha - FedConnect",
                        "body": html_body,
                        "is_html": True,
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    logger.info(f"Email enviado com sucesso via Gateway para: {email}")
                else:
                    logger.error(
                        f"Gateway retornou erro {response.status_code}: {response.text}"
                    )

            return True

        except requests.RequestException as e:
            logger.error(f"Erro ao chamar serviço de email: {e}")
            return False

    def enviar_email_fatura_mensal(
        self, email: str, nome_usuario: str, data_fatura: str
    ) -> bool:
        try:
            pass
        except requests.RequestException as e:
            logger.error(f"Erro ao chamar serviço de email: {e}")
            return False

    def enviar_email_segunda_via(
        self, email: str, nome_usuario: str, data_fatura: str
    ) -> bool:
        try:
            pass
        except requests.RequestException as e:
            logger.error(f"Erro ao chamar serviço de email: {e}")
            return False

    def enviar_email_aviso_vencimento(
        self, email: str, nome_usuario: str, data_vencimento: str
    ) -> bool:
        try:
            pass
        except requests.RequestException as e:
            logger.error(f"Erro ao chamar serviço de email: {e}")
            return False

    