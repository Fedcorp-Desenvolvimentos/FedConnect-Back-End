# services/email_service.py
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from django.conf import settings
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

class EmailService:
    """Serviço para envio de e-mails no Django"""
    
    def __init__(self):
        self.smtp_config = {
            'host': settings.EMAIL_HOST,
            'port': settings.EMAIL_PORT,
            'username': settings.EMAIL_HOST_USER,
            'password': settings.EMAIL_HOST_PASSWORD,
            'use_tls': settings.EMAIL_USE_TLS,
            'from_email': settings.DEFAULT_FROM_EMAIL,
            'from_name': getattr(settings, 'EMAIL_FROM_NAME', 'Sistema')
        }
        
        logger.info(f"📧 EmailService inicializado com host: {self.smtp_config['host']}")
    
    def _criar_mensagem(self, para: List[str], assunto: str, template_html: str, 
                        template_texto: Optional[str] = None, cc: Optional[List[str]] = None,
                        bcc: Optional[List[str]] = None) -> MIMEMultipart:
        """Cria a mensagem de e-mail no formato MIME"""
        msg = MIMEMultipart('alternative')
        
        # Configura remetente
        from_header = f"{self.smtp_config['from_name']} <{self.smtp_config['from_email']}>"
        msg['From'] = from_header
        msg['To'] = ', '.join(para)
        msg['Subject'] = assunto
        
        if cc:
            msg['Cc'] = ', '.join(cc)
        
        # Adiciona versão HTML
        msg.attach(MIMEText(template_html, 'html', 'utf-8'))
        
        # Adiciona versão texto se fornecida
        if template_texto:
            msg.attach(MIMEText(template_texto, 'plain', 'utf-8'))
        else:
            # Gera versão texto do HTML
            texto_plano = strip_tags(template_html)
            msg.attach(MIMEText(texto_plano, 'plain', 'utf-8'))
        
        return msg
    
    def enviar_email(self, para: List[str], assunto: str, template_html: str,
                     template_texto: Optional[str] = None, cc: Optional[List[str]] = None,
                     bcc: Optional[List[str]] = None) -> bool:
        """
        Envia e-mail de forma síncrona
        """
        try:
            msg = self._criar_mensagem(para, assunto, template_html, template_texto, cc, bcc)
            
            # Lista todos os destinatários
            todos_destinatarios = para.copy()
            if cc:
                todos_destinatarios.extend(cc)
            if bcc:
                todos_destinatarios.extend(bcc)
            
            # Conecta ao servidor SMTP
            with smtplib.SMTP(self.smtp_config['host'], self.smtp_config['port']) as server:
                server.ehlo()
                
                if self.smtp_config['use_tls']:
                    server.starttls()
                    server.ehlo()
                
                server.login(self.smtp_config['username'], self.smtp_config['password'])
                server.send_message(msg, to_addrs=todos_destinatarios)
            
            logger.info(f"✅ E-mail enviado com sucesso para {para}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar e-mail: {str(e)}")
            return False