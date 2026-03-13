"""
Configurações do projeto Central de Viagens.
PostgreSQL é o banco padrão em desenvolvimento (variáveis POSTGRES_* no .env).
SQLite é usado apenas ao rodar testes (manage.py test), quando POSTGRES_DB não estiver definido.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
_env_path = BASE_DIR / ".env"
load_dotenv(_env_path)
if not _env_path.exists():
    import warnings
    warnings.warn(
        "Arquivo .env não encontrado na raiz do projeto. "
        "Copie .env.example para .env e preencha as variáveis (ex.: POSTGRES_*)."
    )

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-key-change-in-production')
DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'cadastros',
    'documentos',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.navigation.get_sidebar_menu',
            ],
        },
    },
]

def _get_db_config():
    # Em testes, usar SQLite se POSTGRES_DB não estiver definido (evita exigir PG no CI).
    if 'test' in sys.argv and not os.getenv('POSTGRES_DB'):
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    db = os.getenv('POSTGRES_DB')
    if not db:
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': db,
        'USER': os.getenv('POSTGRES_USER', ''),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
        'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
        'OPTIONS': {'connect_timeout': 10},
    }


DATABASES = {'default': _get_db_config()}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True
DEFAULT_CHARSET = 'utf-8'

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'core:login'
LOGIN_REDIRECT_URL = 'documentos:hub'
LOGOUT_REDIRECT_URL = 'core:login'

# OSRM local (Docker). Sem OSRM = fallback Haversine/corredor.
# OSRM_ENABLED=true  OSRM_BASE_URL=http://localhost:5000  OSRM_TIMEOUT_SECONDS=5
OSRM_ENABLED = os.getenv('OSRM_ENABLED', 'false').strip().lower() in ('true', '1', 'yes')
OSRM_BASE_URL = os.getenv('OSRM_BASE_URL', '').strip() or ''
def _osrm_timeout():
    try:
        return max(1, min(30, int(os.getenv('OSRM_TIMEOUT_SECONDS', '5') or '5')))
    except (TypeError, ValueError):
        return 5


OSRM_TIMEOUT_SECONDS = _osrm_timeout()
