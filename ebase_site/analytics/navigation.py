"""Вкладки раздела «Аналитика», права на них и пункт раздела в меню админки."""

from dataclasses import dataclass

from django.apps import apps
from django.urls import reverse


@dataclass(frozen=True)
class Tab:
    """Вкладка раздела: ключ, заголовок, право доступа и имя URL."""

    key: str
    title: str
    perm: str
    url_name: str


# Следующие этапы дописывают сюда свои вкладки
TABS = [
    Tab("finance", "Финансы", "analytics.view_finance", "analytics:finance"),
]


def visible_tabs(user) -> list[Tab]:
    """Вкладки, на которые у пользователя есть право."""
    return [tab for tab in TABS if user.has_perm(tab.perm)]


def admin_app_entry(request) -> dict | None:
    """Раздел «Аналитика» в формате списка приложений админки.

    Список выводится и в боковой панели, и на главной странице админки
    (на телефоне боковая панель скрыта). Пункты — доступные пользователю
    вкладки; без прав раздел не показывается.
    """
    tabs = visible_tabs(request.user)
    if not tabs:
        return None
    return {
        "name": apps.get_app_config("analytics").verbose_name,
        "app_label": "analytics",
        "app_url": reverse("analytics:index"),
        "has_module_perms": True,
        "models": [
            {
                "name": tab.title,
                "object_name": tab.key,
                "perms": {"add": False, "change": False, "delete": False, "view": True},
                "admin_url": reverse(tab.url_name),
                "add_url": None,
                "view_only": True,
            }
            for tab in tabs
        ],
    }
