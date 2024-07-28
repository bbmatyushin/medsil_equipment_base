from django.apps import AppConfig


class SparePartConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "spare_part"
    verbose_name = "Запчасти"

    def ready(self):
        import spare_part.signals
