import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-key")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "usuarios",
    "cadastros",
    "roteiros",
    "eventos",
    "documentos",
    "oficios",
    "termos",
    "justificativas",
    "planos_trabalho",
    "ordens_servico",
    "prestacoes_contas",
    "diario_bordo",
    "assinaturas",
    "integracoes.google_drive",
]

_MIDDLEWARE_CORE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
_MIDDLEWARE_TAIL = [
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Exige login em todas as rotas (exceto as isentas pelo Django) quando True.
# Em desenvolvimento, `config.settings.dev` define LOGIN_ENFORCED=false por padrao para facilitar testes.
_LOGIN_ENFORCED = os.getenv("LOGIN_ENFORCED", "true").lower() in ("1", "true", "yes")

MIDDLEWARE = list(_MIDDLEWARE_CORE)
if _LOGIN_ENFORCED:
    MIDDLEWARE.append("core.middleware.AjaxAwareLoginRequiredMiddleware")
MIDDLEWARE.extend(_MIDDLEWARE_TAIL)

LOGIN_URL = "core:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "core:login"

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.navigation",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "pt-br")
TIME_ZONE = os.getenv("TIME_ZONE", "America/Sao_Paulo")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Rotas (OpenRouteService via backend — nunca expor OPENROUTESERVICE_API_KEY ao navegador)
ROUTE_PROVIDER = (os.getenv("ROUTE_PROVIDER") or "openrouteservice").strip().lower()
OPENROUTESERVICE_API_KEY = (os.getenv("OPENROUTESERVICE_API_KEY") or "").strip()
ROUTE_CACHE_ENABLED = os.getenv("ROUTE_CACHE_ENABLED", "true").lower() in ("1", "true", "yes")
ROUTE_REQUEST_TIMEOUT_SECONDS = int(os.getenv("ROUTE_REQUEST_TIMEOUT_SECONDS", "12"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
