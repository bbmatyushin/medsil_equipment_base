"""Ссылки из статистики в списки и карточки админки (drill-down)."""

from urllib.parse import urlencode

from django.urls import reverse


def _query_value(value) -> str:
    """Значение GET-параметра: списки склеиваются запятой (для `__in`)."""
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return str(value)


def changelist_url(admin_name: str, **params) -> str:
    """Список модели в админке с GET-фильтрами.

    `admin_name` — «<app>_<model>», например "contracts_contract".
    Параметры со значением None отбрасываются.
    """
    url = reverse(f"admin:{admin_name}_changelist")
    query = {
        key: _query_value(value) for key, value in params.items() if value is not None
    }
    return f"{url}?{urlencode(query)}" if query else url


def change_url(admin_name: str, pk) -> str:
    """Карточка объекта в админке."""
    return reverse(f"admin:{admin_name}_change", args=[pk])
