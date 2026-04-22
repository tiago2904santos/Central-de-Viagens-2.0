from django.apps import AppConfig
from importlib import import_module


class AssinaturasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "assinaturas"
    verbose_name = "Assinaturas eletronicas"

    def ready(self):
        import_module("assinaturas.signals")
