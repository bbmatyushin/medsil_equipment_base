from django.apps import AppConfig


class BusinessTripConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "business_trip"
    verbose_name = "Командировки"

    def ready(self):
        import business_trip.signals
