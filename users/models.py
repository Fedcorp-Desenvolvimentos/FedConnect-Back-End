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
        ("faturamento", "Faturista")
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
        on_delete=models.SET_NULL,  # Define como NULL se a empresa for deletada
        null=True,  # Permite que o campo seja NULL no banco de dados
        blank=True,  # Permite que o campo seja em branco no formulário
        related_name="usuarios",  # Permite acessar 'empresa.usuarios.all()'
    )
    is_fed = models.BooleanField(default=True)

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
