# templates/email/password_reset_email.py
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

class PasswordResetTemplates:
    """Gerenciador de templates para recuperação de senha"""
    
    @staticmethod
    def get_reset_html(usuario, reset_link):
        """Template HTML para email de recuperação"""
        context = {
            'usuario': usuario,
            'reset_link': reset_link,
            'site_name': settings.SITE_NAME,
            'support_email': settings.SUPPORT_EMAIL,
            'logo_url': settings.LOGO_URL,
            'expiration_hours': settings.PASSWORD_RESET_TIMEOUT // 3600
        }
        
        return render_to_string('email/password_reset.html', context)
    
    @staticmethod
    def get_reset_texto(usuario, reset_link):
        """Versão texto do template"""
        context = {
            'usuario': usuario,
            'reset_link': reset_link,
            'site_name': settings.SITE_NAME,
            'support_email': settings.SUPPORT_EMAIL,
            'expiration_hours': settings.PASSWORD_RESET_TIMEOUT // 3600
        }
        
        return render_to_string('email/password_reset.txt', context)