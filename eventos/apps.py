from django.apps import AppConfig


class EventosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'eventos'
    verbose_name = 'Eventos'

    def ready(self):
        # Signals de resgate documento → evento
        import eventos.signals  # noqa: F401
