"""Сайт админки проекта.

Подключается через `ebase_site.apps.EbaseAdminConfig` (`default_site`), поэтому
`django.contrib.admin.site` во всех приложениях — это `EbaseAdminSite`.
"""

from django.contrib import admin

from analytics.navigation import admin_app_entry


class EbaseAdminSite(admin.AdminSite):
    """Добавляет раздел «Аналитика» в список приложений админки.

    У раздела нет моделей в админке, поэтому стандартный список его не видит.
    Список выводится в боковой панели и на главной странице.
    """

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        if app_label in (None, "analytics"):
            entry = admin_app_entry(request)
            if entry is not None:
                app_list = sorted(
                    [*app_list, entry], key=lambda app: app["name"].lower()
                )
        return app_list
