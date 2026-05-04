from .base import BASE_DIR
from .base import *


DEBUG = True
SECRET_KEY = "django-insecure-central-viagens-3-dev-key"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
