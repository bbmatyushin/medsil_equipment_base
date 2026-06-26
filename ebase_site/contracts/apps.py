from django.apps import AppConfig


class ContractsConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'contracts'
    verbose_name = 'Реестр контрактов'

    def ready(self):
        import contracts.signals
