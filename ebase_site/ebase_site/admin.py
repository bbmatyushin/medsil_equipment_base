"""Сайт админки проекта.

Подключается через `ebase_site.apps.EbaseAdminConfig` (`default_site`), поэтому
`django.contrib.admin.site` во всех приложениях — это `EbaseAdminSite`.
"""

from django.contrib import admin

from analytics.navigation import admin_app_entry

# Пользователи (`users`) выводятся в блоке групп (`auth`) — «Пользователи и группы»
USERS_APP = "users"
AUTH_APP = "auth"


def _merge_users_into_auth(app_list: list[dict]) -> list[dict]:
    """Переносит модели блока `users` в блок `auth` и убирает блок `users`.

    Если одного из блоков нет (например, нет прав на группы), список не меняется.
    """
    by_label = {app["app_label"]: app for app in app_list}
    users, auth = by_label.get(USERS_APP), by_label.get(AUTH_APP)
    if users is None or auth is None:
        return app_list
    auth["models"] = sorted(
        [*auth["models"], *users["models"]], key=lambda model: model["name"]
    )
    return [app for app in app_list if app is not users]


class EbaseAdminSite(admin.AdminSite):
    """Список приложений админки с правками проекта.

    - Пользователи выводятся в блоке «Пользователи и группы» вместе с группами.
    - Добавляется раздел «Аналитика»: у него нет моделей в админке, поэтому
      стандартный список его не видит.

    Список выводится в боковой панели и на главной странице.
    """

    def get_app_list(self, request, app_label=None):
        if app_label in (USERS_APP, AUTH_APP):
            # страницы /admin/users/ и /admin/auth/ показывают общий блок
            app_list = _merge_users_into_auth(super().get_app_list(request))
            return [
                app for app in app_list if app["app_label"] in (USERS_APP, AUTH_APP)
            ]
        app_list = super().get_app_list(request, app_label)
        if app_label is None:
            app_list = _merge_users_into_auth(app_list)
        if app_label in (None, "analytics"):
            entry = admin_app_entry(request)
            if entry is not None:
                app_list = sorted(
                    [*app_list, entry], key=lambda app: app["name"].lower()
                )
        return app_list
