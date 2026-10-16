from django.db import models

STATISTICS_GROUP_NAME = "Статистика"


class AnalyticsAccess(models.Model):
    """Модель-носитель прав доступа к вкладкам раздела «Статистика».

    Таблицы в БД нет (`managed = False`): модель нужна только затем, чтобы
    Django создал для неё `ContentType` и четыре права по вкладкам.
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("view_finance", "Статистика: Деньги"),
            ("view_warehouse_trips", "Статистика: Склад и командировки"),
            ("view_service", "Статистика: Сервис и надёжность"),
            ("view_park", "Статистика: Парк и продажи"),
        )
        verbose_name = "Доступ к статистике"
        verbose_name_plural = "Доступ к статистике"
