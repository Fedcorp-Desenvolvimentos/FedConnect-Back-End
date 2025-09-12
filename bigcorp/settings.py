import os
from pathlib import Path
from datetime import timedelta
from decouple import config  # type: ignore
from dotenv import load_dotenv
import logging

# Configuração de logger para debug
logger = logging.getLogger(__name__)

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: don't run with debug turned on in production!
# Make sure DEBUG=True in your .env file for development
DEBUG = config("DEBUG", default=False, cast=bool)

# Imprime o valor de DEBUG no console do servidor ao iniciar, para verificar
logger.info(f"DEBUG está definido como: {DEBUG}")




STATIC_URL = '/static/'

# This is the line you need to add or correct:
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')


# --- AJUSTE CRÍTICO AQUI ---
# Em produção, você DEVE listar os hosts reais do seu servidor.
# Em desenvolvimento, 'localhost' e '127.0.0.1' são comuns.
# Se sua amiga acessa o seu IP local (ex: http://192.168.x.x:8000), adicione-o aqui.
ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "bigcorp-backend.onrender.com",
    ".render.com",
    "bigcorp-react-aj3a.vercel.app"
]
if (
    not DEBUG
):  # Permite "*" apenas em desenvolvimento (se CORS não estiver estritamente configurado, o que não é o caso aqui)
    # Em produção, adicione os domínios do seu servidor aqui. Ex: "api.seusite.com.br"
    pass
else:
    # Em DEBUG, para fins de desenvolvimento local com IPs, podemos ser mais flexíveis,
    # mas o CORS_ALLOWED_ORIGINS já lida com o frontend.
    # Se você está acessando o backend pelo IP na sua rede local para debug,
    # adicione seu IP aqui: ALLOWED_HOSTS += ["<seu_ip_na_rede_local>"]
    ALLOWED_HOSTS += [
        "*"
    ]  # Em desenvolvimento, permite todos os hosts para acesso direto ao backend, mas o CORS ainda controla o frontend.


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps instalados
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",  # MUITO IMPORTANTE: Garanta que 'corsheaders' está aqui!
    "drf_spectacular",
    # Apps do projeto
    "users",
    "consultas",
    "planilha",
    "empresas",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # MUITO IMPORTANTE: Deve ser a primeira ou uma das primeiras!
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",  # Ordem crucial: DEPOIS de CommonMiddleware
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "bigcorp.urls"

# Configurações do Supabase (Corrigido para refletir o uso real)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'FedConnect',
        'USER': 'postgres',
        'PASSWORD': 'masterkey',
        'HOST': 'db',
        'PORT': '5432',
    }
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "bigcorp.wsgi.application"

DJANGO_SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
LANGUAGE_CODE = "pt-br"

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Configuração do modelo de usuário personalizado
AUTH_USER_MODEL = "users.Usuario"

# Configurações do Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "users.authentication.JWTCookieAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "PAGINATE_BY_PARAM": "page_size",
    "MAX_PAGE_SIZE": 100,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# Configurações do JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=120),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": os.environ.get("DJANGO_SECRET_KEY"),
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "JTI_CLAIM": "jti",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
    # --- CRITICAL ADDITIONS FOR COOKIE AUTH ---
    "AUTH_COOKIE": "access_token",
    "AUTH_COOKIE_DOMAIN": None,
    "AUTH_COOKIE_SECURE": True,  # True para HTTPS em produção, False para HTTP em dev
    "AUTH_COOKIE_HTTP_ONLY": True,
    "AUTH_COOKIE_SAMESITE": "None",  
}


# --- Configurações do CORS - SOLUÇÃO FINAL PARA O ERRO ---
# É CRUCIAL que CORS_ALLOW_ALL_ORIGINS seja False quando CORS_ALLOW_CREDENTIALS é True
# Isso porque navegadores PROÍBEM 'Access-Control-Allow-Origin: *' com credenciais.

CORS_ALLOW_CREDENTIALS = True  # PERMITE ENVIO/RECEBIMENTO DE COOKIES

# Lista explícita de origens permitidas.
# Mesmo em desenvolvimento, liste as origens para garantir o funcionamento com credenciais.
CORS_ALLOWED_ORIGINS = [
    "https://bigcorp-backend.onrender.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://bigcorp-react-aj3a.vercel.app",
    
]

# FORÇAMOS CORS_ALLOW_ALL_ORIGINS para FALSE para que CORS_ALLOWED_ORIGINS seja sempre respeitado
CORS_ALLOW_ALL_ORIGINS = False

# Headers que o frontend tem permissão para enviar em requisições cross-origin
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",  # Essencial para proteção CSRF do Django
    "x-requested-with",
]

# URLs de APIs externas
CEP_URL = "https://brasilapi.com.br/api/cep/v1/"
CNPJ_URL = "https://brasilapi.com.br/api/cnpj/v1/"
CPF_URL = "https://plataforma.bigdatacorp.com.br/pessoas"
ALT_CNPJ_URL = "https://plataforma.bigdatacorp.com.br/empresas"
ALT_CEP_URL = "viacep.com.br/ws"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")





# Configurações do DRF Spectacular
SPECTACULAR_SETTINGS = {
    "TITLE": "API BigCorp",
    "DESCRIPTION": "Documentação da API do sistema BigCorp, incluindo gerenciamento de usuários e consultas.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "filter": True,
        "displayRequestDuration": True,
        "defaultModelsExpandDepth": 2,
        "defaultModelExpandDepth": 2,
    },
    "ENUM_NAME_OVERRIDES": {
        "HistoricoConsultaTipoConsultaEnum": "TipoConsultaEnum",
    },
}

# --- Ferramentas de Debug Adicionais ---

# 1. Configuração do Logging (para ver mais detalhes no console do Django)
# Isso mostrará informações do seu logger.info acima e outros logs do Django.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",  # Mudei para INFO para ver mais logs por padrão
        "propagate": False,
    },
    "loggers": {
        "django.db.backends": {
            "level": "INFO",  # Para ver queries SQL (muito verboso, use com cautela)
            "handlers": ["console"],
            "propagate": False,
        },
        "corsheaders": {
            "level": "DEBUG",  # Para ver logs DETALHADOS da biblioteca CORS (MUITO ÚTIL para depuração de CORS)
            "handlers": ["console"],
            "propagate": False,
        },
    },
}

# 2. Verificar o URL do ROOT_URLCONF
# Apenas para garantir que o Django está carregando as URLs corretas
logger.info(f"ROOT_URLCONF está definido como: {ROOT_URLCONF}")


API_CONSULTA_TIMEOUT = 200

CONSULTA_API_URL ="https://bigcorp-backend.onrender.com/consultas/realizar/"

# Para permitir que cookies sejam enviados em requisições POST cross-site, use 'None'
# E SEMPRE junto com SECURE=True
SESSION_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SAMESITE = 'None' # Importante para o x-csrftoken que você está enviando

# Certifique-se de que o cookie é enviado APENAS por HTTPS
# Essencial para deploy no Render, que usa HTTPS
SESSION_COOKIE_SECURE = True 
CSRF_COOKIE_SECURE = True
