from django.db import models

ANALYTICS_GROUP_NAME = "Аналитика"


class AnalyticsAccess(models.Model):
    """Модель-носитель прав доступа к вкладкам раздела «Аналитика».

    Таблицы в БД нет (`managed = False`): модель нужна только затем, чтобы
    Django создал для неё `ContentType` и права по вкладкам: по одному праву
    на каждую существующую вкладку. Новая вкладка добавляет своё право.
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("view_finance", "Аналитика: Финансы"),
            ("view_trips", "Аналитика: Командировки"),
            ("view_equipment", "Аналитика: Оборудование"),
        )
        verbose_name = "Доступ к аналитике"
        verbose_name_plural = "Доступ к аналитике"
