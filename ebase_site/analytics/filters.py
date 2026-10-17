"""Период и формы фильтров раздела «Аналитика»."""

import calendar
from dataclasses import dataclass
from datetime import date

from django import forms

from business_trip.xlsx_report import employee_fio
from clients.models import Client
from users.models import CompanyUser

MONTH_ABBR = [
    "янв",
    "фев",
    "мар",
    "апр",
    "май",
    "июн",
    "июл",
    "авг",
    "сен",
    "окт",
    "ноя",
    "дек",
]

PRESETS = [
    ("year", "Текущий год"),
    ("prev_year", "Прошлый год"),
    ("quarter", "Текущий квартал"),
    ("month", "Текущий месяц"),
    ("custom", "Свой период"),
]

DEFAULT_PRESET = "year"

# Направления вкладки «Командировки»: по городам или по регионам
TRIP_GROUPS = [("city", "Города"), ("region", "Регионы")]
DEFAULT_GROUP = "city"

# Допустимые годы для своего периода: вне границ shift_year/months упадут или раздуются
MIN_YEAR = 1900
MAX_YEAR = 2100


def shift_year(d: date, years: int) -> date:
    """Сдвигает дату на `years` лет. 29 февраля в невисокосном году -> 28 февраля."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def month_label(d: date) -> str:
    """Подпись месяца для осей графиков: «янв 2026»."""
    return f"{MONTH_ABBR[d.month - 1]} {d.year}"


@dataclass(frozen=True)
class Period:
    """Закрытый интервал дат [date_from, date_to]."""

    date_from: date
    date_to: date

    def previous_year(self) -> "Period":
        """Тот же интервал на год раньше (для сравнения с прошлым годом)."""
        return Period(shift_year(self.date_from, -1), shift_year(self.date_to, -1))

    def months(self) -> list[date]:
        """Первые числа месяцев от date_from до date_to включительно."""
        result = []
        current = self.date_from.replace(day=1)
        while current <= self.date_to:
            result.append(current)
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)
        return result


def _month_end(year: int, month: int) -> date:
    """Последний день месяца."""
    return date(year, month, calendar.monthrange(year, month)[1])


def _preset_period(preset: str, today: date) -> Period:
    """Период по пресету (кроме «custom»). Неизвестный пресет -> текущий год."""
    if preset == "prev_year":
        return Period(date(today.year - 1, 1, 1), date(today.year - 1, 12, 31))
    if preset == "quarter":
        first_month = (today.month - 1) // 3 * 3 + 1
        last_month = first_month + 2
        return Period(
            date(today.year, first_month, 1), _month_end(today.year, last_month)
        )
    if preset == "month":
        return Period(
            date(today.year, today.month, 1), _month_end(today.year, today.month)
        )
    return Period(date(today.year, 1, 1), date(today.year, 12, 31))


class PeriodForm(forms.Form):
    """Выбор периода. Создаётся с `data=request.GET`; мусор в параметрах не падает."""

    preset = forms.ChoiceField(choices=PRESETS, required=False, label="Период")
    # format="%Y-%m-%d": в ru-локали DateInput иначе выводит 05.03.2026, а type="date" ждёт ISO
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        label="С",
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        label="По",
    )

    def _cleaned(self) -> dict:
        """Прошедшие очистку значения. Невалидные поля в cleaned_data не попадают."""
        self.is_valid()
        # у несвязанной формы cleaned_data нет
        return getattr(self, "cleaned_data", {})

    def get_period(self, today: date) -> Period:
        """Период по значениям, прошедшим очистку. Любой мусор -> текущий год."""
        cleaned = self._cleaned()
        preset = cleaned.get("preset") or DEFAULT_PRESET
        if preset == "custom":
            date_from = cleaned.get("date_from")
            date_to = cleaned.get("date_to")
            if date_from is None or date_to is None:
                return _preset_period(DEFAULT_PRESET, today)
            if date_from > date_to:
                date_from, date_to = date_to, date_from
            if date_from.year < MIN_YEAR or date_to.year > MAX_YEAR:
                return _preset_period(DEFAULT_PRESET, today)
            return Period(date_from, date_to)
        return _preset_period(preset, today)


class FinanceFilterForm(PeriodForm):
    """Фильтры вкладки «Финансы»: период + клиент (только клиенты с контрактами)."""

    client = forms.ModelChoiceField(
        Client.objects.filter(contract_client__isnull=False)
        .distinct()
        .order_by("name"),
        required=False,
        label="Клиент",
        empty_label="Все клиенты",
    )

    def get_client(self) -> Client | None:
        """Выбранный клиент или None (нет значения / неверный UUID / нет контрактов)."""
        return self._cleaned().get("client")


class EmployeeChoiceField(forms.ModelChoiceField):
    """Сотрудник по ФИО (без ФИО — по логину)."""

    def label_from_instance(self, obj) -> str:
        return employee_fio(obj) or obj.username


class TripsFilterForm(PeriodForm):
    """Фильтры вкладки «Командировки»: период, сотрудник, города или регионы."""

    employee = EmployeeChoiceField(
        CompanyUser.objects.filter(business_trip_employee__isnull=False)
        .distinct()
        .order_by("last_name", "first_name", "patron"),
        required=False,
        label="Сотрудник",
        empty_label="Все сотрудники",
    )
    group = forms.ChoiceField(choices=TRIP_GROUPS, required=False, label="Направления")

    def get_employee(self) -> CompanyUser | None:
        """Выбранный сотрудник или None (нет значения / неверный UUID / нет командировок)."""
        return self._cleaned().get("employee")

    def get_group(self) -> str:
        """«city» или «region»; мусор -> города."""
        return self._cleaned().get("group") or DEFAULT_GROUP
