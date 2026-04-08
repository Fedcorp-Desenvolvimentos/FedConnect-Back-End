import os
from pathlib import Path
from datetime import timedelta
from decouple import config
from dotenv import load_dotenv
import logging
from corsheaders.defaults import default_headers

logger = logging.getLogger(__name__)
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = config("DEBUG", default=False, cast=bool)
logger.info(f"DEBUG está definido como: {DEBUG}")
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Configurações de Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@seusite.com')
EMAIL_FROM_NAME = os.getenv('EMAIL_FROM_NAME', 'Sistema')

# FEDHUB_X_API_KEY = os.getenv('FEDHUB_X_API_KEY', '')

# Configurações do Site
SITE_NAME = os.getenv('SITE_NAME', 'Grupo FedCorp')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
FEDHUB_URL = os.getenv('FEDHUB_URL', 'http://localhost:8090')
SUPPORT_EMAIL = os.getenv('SUPPORT_EMAIL', 'suporte@fedcorp.com')
LOGO_URL = os.getenv('LOGO_URL', 'https://i.postimg.cc/SsPmTvDM/logo-fedcorp.png')

# Configurações de Recuperação de Senha
PASSWORD_RESET_TIMEOUT = 3600  # 1 hora em segundos

##### Configurações de Segurança

SECRET_KEY = config(
    "DJANGO_SECRET_KEY",
    default="59189659c050c968f50c01d04d3634bced76415cce6738402d9e101478129efa",
)

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "fedconnect-backend-d6kgr.ondigitalocean.app",
    "fedconnect.com.br",
    "front-fedconnect-ebhjt.ondigitalocean.app",
    "fedconnect-hml.vercel.app",
    "fedcorp-pay.com.br"
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    "users",
    "consultas",
    "planilha",
    "empresas",
    "agenda",
    "agenda_comercial",
    "cotacao",
    "bank",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "bigcorp.urls"

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_DATABASE', default='placeholder_db'),
        'USER': config('DB_USERNAME', default='placeholder_user'),
        'PASSWORD': config('DB_PASSWORD', default='placeholder_pass'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'sslmode': config('DB_SSLMODE', default='require')
        }
    }
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "bigcorp" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "bigcorp.wsgi.application"


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

LANGUAGE_CODE = "pt-br"

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True

USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "users.Usuario"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        # "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
    "PAGINATE_BY_PARAM": "page_size",
    "MAX_PAGE_SIZE": 200,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=120),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
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
}

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "https://front-fedconnect-98i8n.ondigitalocean.app",
    "https://fedconnect.com.br",

    "https://goldfish-app-nk5x6.ondigitalocean.app",
    "https://front-fedconnect-ebhjt.ondigitalocean.app",
    "https://fedconnect-hml.vercel.app",

]


CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = list(default_headers)

CORS_PREFLIGHT_MAX_AGE = 86400

CEP_URL = "https://brasilapi.com.br/api/cep/v1/"
CNPJ_URL = "https://brasilapi.com.br/api/cnpj/v1/"
CPF_URL = "https://plataforma.bigdatacorp.com.br/pessoas"
ALT_CNPJ_URL = "https://plataforma.bigdatacorp.com.br/empresas"
ALT_CEP_URL = "https://viacep.com.br/ws"
REGIAO_URL = "https://minhareceita.org/"


WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "AIzaSyCmVm2yu5jo-9793-4CSs78e4L9c-U6kNQ")


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

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} :: {message}',
            'style': '{',
        },
    },

    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },

    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },

    'loggers': {
        'nfse': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

logger.info(f"ROOT_URLCONF está definido como: {ROOT_URLCONF}")


API_CONSULTA_TIMEOUT = 600

CONSULTA_API_URL = "https://back-fedconnect-y46st.ondigitalocean.app/consultas/realizar"
