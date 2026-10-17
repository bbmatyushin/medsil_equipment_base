from django.db import models

ANALYTICS_GROUP_NAME = "Аналитика"


class AnalyticsAccess(models.Model):
    """Модель-носитель прав доступа к вкладкам раздела «Аналитика».

    Таблицы в БД нет (`managed = False`): модель нужна только затем, чтобы
    Django создал для неё `ContentType` и права по вкладкам.
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("view_finance", "Аналитика: Финансы"),
            ("view_trips", "Аналитика: Командировки"),
            ("view_warehouse", "Аналитика: Склад"),
            ("view_service", "Аналитика: Сервис и надёжность"),
            ("view_park", "Аналитика: Парк и продажи"),
        )
        verbose_name = "Доступ к аналитике"
        verbose_name_plural = "Доступ к аналитике"
