"""Фильтры шаблонов раздела «Статистика»: деньги, проценты, дельты."""

from django import template

from contracts.admin import format_money

register = template.Library()

EMPTY = "—"
MINUS = "\u2212"  # типографский минус для дельт


def _number(value, digits: int) -> str:
    """Число по-русски: пробел между разрядами, запятая перед дробной частью."""
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


@register.filter
def money(value) -> str:
    """20000 -> «20 000,00 ₽», None -> «—»."""
    if value is None:
        return EMPTY
    return f"{format_money(value)} ₽"


@register.filter
def pct(value) -> str:
    """12.5 -> «12,5 %», None -> «—»."""
    if value is None:
        return EMPTY
    return f"{_number(value, 1)} %"


@register.filter
def delta(value, unit: str = "") -> str:
    """Изменение к прошлому периоду: «+12,5 %», «−3,0 %», None -> «—».

    `{{ value|delta:"pp" }}` — в процентных пунктах: «+1,5 п.п.» (для маржи).
    """
    if value is None:
        return EMPTY
    suffix = "п.п." if unit == "pp" else "%"
    number = _number(abs(value), 1)
    sign = ""
    if number != "0,0":
        sign = "+" if value > 0 else MINUS
    return f"{sign}{number} {suffix}"


@register.filter
def delta_class(value) -> str:
    """CSS-класс дельты по знаку: рост, падение или «без изменений» (и None)."""
    if value is None or value == 0:
        return "an-delta--flat"
    return "an-delta--up" if value > 0 else "an-delta--down"
