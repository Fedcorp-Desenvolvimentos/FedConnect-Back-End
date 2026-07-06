# users/models.py - Adicione estes campos

from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from empresas.models import Empresa


class UsuarioManager(BaseUserManager):
    """Define um gerenciador de modelo para usuário personalizado sem username."""

    def create_user(self, email, password=None, **extra_fields):
        """Cria e salva um usuário com o email e senha fornecidos."""
        if not email:
            raise ValueError(_("O email é obrigatório"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Cria e salva um superusuário com o email e senha fornecidos."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("nivel_acesso", "admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superusuário precisa ter is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superusuário precisa ter is_superuser=True."))
        return self.create_user(email, password, **extra_fields)


class Usuario(AbstractUser):
    """Modelo de usuário personalizado que usa email como identificador único."""

    NIVEL_ACESSO_CHOICES = [
        ("admin", "Administrador"),
        ("usuario", "Usuário Comum"),
        ("comercial", "Comercial"),
        ("moderador", "Moderador"),
        ("recepcionista", "Recepcionista"),
        ("ti", "TI"),
        ("faturamento", "Faturista"),
        ("financeiro", "Financeiro")
    ]

    username = None
    email = models.EmailField(_("endereço de email"), unique=True)
    cpf = models.CharField(_("CPF"), max_length=14, unique=True, null=True, blank=True)
    nome_completo = models.CharField(_("nome completo"), max_length=150, blank=True)
    nivel_acesso = models.CharField(
        _("nível de acesso"),
        max_length=20,
        choices=NIVEL_ACESSO_CHOICES,
        default="usuario",
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios",
    )
    is_fed = models.BooleanField(default=True)
    
    # 🔐 Campos para recuperação de senha
    reset_password_token = models.CharField(
        _("token de recuperação"),
        max_length=255,
        null=True,
        blank=True,
        help_text="Token gerado para recuperação de senha"
    )
    reset_password_token_created_at = models.DateTimeField(
        _("data de criação do token"),
        null=True,
        blank=True,
        help_text="Data e hora em que o token de recuperação foi gerado"
    )
    reset_password_token_expires_at = models.DateTimeField(
        _("data de expiração do token"),
        null=True,
        blank=True,
        help_text="Data e hora em que o token de recuperação expira"
    )
    last_password_reset = models.DateTimeField(
        _("última redefinição de senha"),
        null=True,
        blank=True,
        help_text="Data da última vez que a senha foi redefinida"
    )
    password_reset_count = models.IntegerField(
        _("contador de redefinições"),
        default=0,
        help_text="Número de vezes que a senha foi redefinida"
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UsuarioManager()

    class Meta:
        verbose_name = _("usuário")
        verbose_name_plural = _("usuários")

    def __str__(self):
        return self.email

    @property
    def is_admin(self):
        """Verifica se o usuário é administrador."""
        return self.nivel_acesso == "admin"
    
    def is_reset_token_valid(self, token):
        """Verifica se o token de recuperação é válido."""
        from django.utils import timezone
        
        if not self.reset_password_token or not self.reset_password_token_expires_at:
            return False
        
        return (
            self.reset_password_token == token and 
            self.reset_password_token_expires_at > timezone.now()
        )
    
    def clear_reset_token(self):
        """Limpa o token de recuperação após uso."""
        self.reset_password_token = None
        self.reset_password_token_created_at = None
        self.reset_password_token_expires_at = None
        self.save(update_fields=[
            'reset_password_token', 
            'reset_password_token_created_at', 
            'reset_password_token_expires_at'
        ])