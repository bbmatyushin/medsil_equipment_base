from django.apps import AppConfig


class EbaseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ebase"

    def ready(self):
        import ebase.signals
