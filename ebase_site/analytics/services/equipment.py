"""Расчёты вкладки «Оборудование»: парк, ремонты, надёжность, подменный фонд.

Правила (подробно — в docs/superpowers/specs/2026-10-18-analytics-equipment-design.md):

- прибор — запись «1. Учёт оборудования» (`EquipmentAccounting`); «у клиента» —
  есть активный монтаж, «монтаж снят» — монтажи есть, но все неактивные,
  «нет данных о монтаже» — монтажей нет (данные ещё не внесли);
- работа (`Service`) — ТО, если у вида работ стоит флаг «Плановое ТО», поломка —
  вид указан без флага, вид не указан — ни то ни другое;
- длительность ремонта — дни с граничными датами, только у закрытых.

Данные загружаются один раз на запрос (`EquipmentSet.load()`), виджеты берут
их параметром `source`. Чистые функции без обращения к request; арифметика
дат и медианы — в Python, как в `services/trips.py`.
"""

import statistics
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Prefetch

from analytics.filters import EquipmentFilters, Period
from analytics.services.finance import _bucket_by_month, _delta_pct
from ebase.models import (
    EquipmentAccDepartment,
    EquipmentAccounting,
    ReplacementEquipment,
    Service,
)

STATE_AT_CLIENT = "client"
STATE_REMOVED = "removed"
STATE_NO_INSTALL = "none"

WORK_PLANNED = "planned"
WORK_BREAKDOWN = "breakdown"
WORK_UNKNOWN = "unknown"

NO_MODEL_NAME_LABEL = "Модель без названия"
NO_DIRECTION_LABEL = "Направление не указано"
NO_MANUFACTURER_LABEL = "Производитель не указан"
NO_STATUS_LABEL = "Статус не указан"
NO_ENGINEER_LABEL = "Инженер не указан"
NO_SERVICE_TYPE_LABEL = "Вид работ не указан"
OTHER_SERVICE_TYPES_LABEL = "Прочие виды работ"
NO_CLIENT_LABEL = "Клиент не указан"
NO_CITY_LABEL = "Город не указан"
NO_REGION_SUFFIX = " (регион не указан)"
NO_DEVICE_LABEL = "Прибор не указан"

SUPPLY_OURS = "ours"
SUPPLY_OTHERS = "others"

TENTH = Decimal("0.1")

# Возраст парка: корзины (подпись, от, до) в годах, «до» не включается
AGE_BUCKETS = (
    ("<1", 0, 1),
    ("1–3", 1, 3),
    ("3–5", 3, 5),
    ("5–10", 5, 10),
    ("10+ лет", 10, None),
)
AGE_UNKNOWN_LABEL = "дата неизвестна"
DAYS_IN_AVERAGE_YEAR = 365.25

TOP_MANUFACTURERS = 10
OTHER_MANUFACTURERS_LABEL = "Прочие производители"
TOP_CLIENTS = 15

# Незакрытый ремонт старше стольких дней считается «старым незакрытым»
OPEN_REPAIR_DAYS = 365

# Длительность ремонта: корзины (подпись, от, до) в днях, границы включаются
DURATION_BUCKETS = (
    ("1–3", 1, 3),
    ("4–7", 4, 7),
    ("8–14", 8, 14),
    ("15–30", 15, 30),
    ("31+", 31, None),
)
# Серий на графике «Работы по месяцам» не больше, чем цветов палитры charts.js
MAX_MONTH_SERIES = 6
REPAIR_KPI_KEYS = ("total", "planned", "breakdowns", "median_days", "replacement_share")

# Надёжность: окна повторного ремонта (дни), минимум приборов модели в рейтинге
REPEAT_WINDOWS = (30, 90)
MIN_UNITS_FOR_RELIABILITY = 3
TOP_RELIABILITY = 15
TOP_PROBLEM_DEVICES = 10
DAYS_IN_YEAR = 365
HUNDREDTH = Decimal("0.01")


# --- Правила и подписи ----------------------------------------------------------


def _installs(device) -> list[EquipmentAccDepartment]:
    """Монтажи прибора, загруженные `EquipmentSet.load()`."""
    return device.installs


def active_install(device) -> EquipmentAccDepartment | None:
    """Активный монтаж прибора; из нескольких — с самой поздней датой монтажа.

    Монтаж без даты считается раньше любого датированного, при равенстве
    дат берётся позже созданный.
    """
    active = [install for install in _installs(device) if install.is_active]
    if not active:
        return None
    return max(
        active,
        key=lambda install: (
            install.install_dt is not None,
            install.install_dt or date.min,
            install.create_dt,
        ),
    )


def install_state(device) -> str:
    """«У клиента», «монтаж снят» или «нет данных о монтаже»."""
    installs = _installs(device)
    if not installs:
        return STATE_NO_INSTALL
    if any(install.is_active for install in installs):
        return STATE_AT_CLIENT
    return STATE_REMOVED


def work_kind(service) -> str:
    """ТО (флаг «Плановое ТО» у вида), поломка (вид без флага) или «вид не указан»."""
    if service.service_type is None:
        return WORK_UNKNOWN
    if service.service_type.is_planned_maintenance:
        return WORK_PLANNED
    return WORK_BREAKDOWN


def repair_days(service) -> int | None:
    """Длительность в днях с граничными датами; без даты окончания — None.

    Дата окончания раньше даты начала (админка такое не проверяет) — один день.
    """
    if service.end_dt is None:
        return None
    return max((service.end_dt - service.beg_dt).days + 1, 1)


def model_label(equipment) -> str:
    """Название модели: полное, иначе краткое."""
    return equipment.full_name or equipment.short_name or NO_MODEL_NAME_LABEL


def device_label(device) -> str:
    """«Модель [СЕРИЙНЫЙ НОМЕР]», как `str(EquipmentAccounting)`, но без None."""
    return f"{model_label(device.equipment)} [{device.serial_number.upper()}]"


def replacement_label(replacement) -> str:
    """«Модель [серийный номер]» подменного прибора (без комплектующих и запросов)."""
    return f"{model_label(replacement.equipment)} [{replacement.serial_number}]"


def department_label(department) -> str:
    """«Название (Город)»; `str(Department)` не годится — падает без города."""
    if department.city is None:
        return department.name
    return f"{department.name} ({department.city.name})"


def client_label(department) -> str:
    """Клиент подразделения."""
    if department.client is None:
        return NO_CLIENT_LABEL
    return department.client.name


def region_label(department) -> str:
    """Регион подразделения, как направления «Регионы» во вкладке «Командировки»."""
    city = department.city
    if city is None:
        return NO_CITY_LABEL
    if not city.region:
        return f"{city.name}{NO_REGION_SUFFIX}"
    return city.region


# --- Набор данных ---------------------------------------------------------------


def _model_matches(equipment, filters: EquipmentFilters) -> bool:
    """Модель проходит фильтры направления и производителя."""
    if (
        filters.direction is not None
        and equipment.med_direction_id != filters.direction.pk
    ):
        return False
    if (
        filters.manufacturer is not None
        and equipment.manufacturer_id != filters.manufacturer.pk
    ):
        return False
    return True


def _device_matches(device, filters: EquipmentFilters) -> bool:
    """Прибор проходит все фильтры: модель и «Поставка»."""
    if filters.supply == SUPPLY_OURS and not device.is_our_supply:
        return False
    if filters.supply == SUPPLY_OTHERS and device.is_our_supply:
        return False
    return _model_matches(device.equipment, filters)


class EquipmentSet:
    """Приборы, ремонты и подменный фонд, загруженные один раз на запрос.

    Виджеты вкладки принимают набор параметром `source`; без него виджет
    загружает данные сам. Ремонт без прибора (поле nullable) входит в выборки
    только без фильтров: его модель и поставка неизвестны.
    """

    def __init__(self, devices, services, replacements):
        self.devices = devices
        self.services = services
        self.replacements = replacements
        self.device_by_id = {device.pk: device for device in devices}
        self._issues = {}
        for service in sorted(services, key=lambda s: (s.beg_dt, s.create_dt)):
            if service.replacement_equipment_id is not None:
                self._issues.setdefault(service.replacement_equipment_id, []).append(
                    service
                )

    @classmethod
    def load(cls) -> "EquipmentSet":
        """Все приборы с монтажами, ремонты и подменный фонд — четыре запроса."""
        devices = list(
            EquipmentAccounting.objects.select_related(
                "equipment__med_direction",
                "equipment__manufacturer",
                "equipment_status",
            ).prefetch_related(
                Prefetch(
                    "equipment_acc_department_equipment_accounting",
                    queryset=EquipmentAccDepartment.objects.select_related(
                        "department__city", "department__client", "engineer"
                    ),
                    to_attr="installs",
                )
            )
        )
        services = list(
            Service.objects.select_related(
                "service_type", "engineer", "replacement_equipment__equipment"
            )
        )
        replacements = list(
            ReplacementEquipment.objects.select_related(
                "equipment__med_direction", "equipment__manufacturer"
            )
        )
        return cls(devices, services, replacements)

    def device_of(self, service) -> EquipmentAccounting | None:
        """Прибор ремонта (из загруженных) или None."""
        return self.device_by_id.get(service.equipment_accounting_id)

    def devices_of(self, filters: EquipmentFilters) -> list[EquipmentAccounting]:
        """Приборы, прошедшие фильтры."""
        return [device for device in self.devices if _device_matches(device, filters)]

    def services_of(self, filters: EquipmentFilters) -> list[Service]:
        """Ремонты приборов, прошедших фильтры; ремонт без прибора — только без фильтров."""
        result = []
        for service in self.services:
            device = self.device_of(service)
            if device is None:
                if filters.is_empty:
                    result.append(service)
            elif _device_matches(device, filters):
                result.append(service)
        return result

    def services_in(self, period: Period, filters: EquipmentFilters) -> list[Service]:
        """Ремонты с датой начала в периоде (границы включительно)."""
        return [
            service
            for service in self.services_of(filters)
            if period.date_from <= service.beg_dt <= period.date_to
        ]

    def replacements_of(self, filters: EquipmentFilters) -> list[ReplacementEquipment]:
        """Подменный фонд по направлению и производителю модели; «Поставка» не действует."""
        return [
            replacement
            for replacement in self.replacements
            if _model_matches(replacement.equipment, filters)
        ]

    def issues_of(self, replacement) -> list[Service]:
        """Ремонты, в которые выдавался подменный прибор, по дате начала."""
        return list(self._issues.get(replacement.pk, []))


def _source(source: EquipmentSet | None) -> EquipmentSet:
    """Переданный набор или свежая загрузка."""
    return source if source is not None else EquipmentSet.load()


# --- Блок А: парк оборудования (на сегодня) ----------------------------------------


def _at_client(devices) -> list[tuple]:
    """Пары (прибор, активный монтаж) для приборов у клиента."""
    pairs = []
    for device in devices:
        install = active_install(device)
        if install is not None:
            pairs.append((device, install))
    return pairs


def _age_years(install_dt: date, today: date) -> float:
    """Возраст прибора в годах от даты монтажа (дробный)."""
    return (today - install_dt).days / DAYS_IN_AVERAGE_YEAR


def park_kpis(today: date, filters: EquipmentFilters, source=None) -> dict:
    """Плитки парка: учтено (нами/не нами), у клиентов, без монтажа, клиенты, возраст."""
    source = _source(source)
    devices = source.devices_of(filters)
    states = [install_state(device) for device in devices]
    at_client = _at_client(devices)
    ages = [
        _age_years(install.install_dt, today)
        for _, install in at_client
        if install.install_dt is not None
    ]
    avg_age = None
    if ages:
        avg_age = Decimal(sum(ages) / len(ages)).quantize(TENTH, ROUND_HALF_UP)
    ours = sum(1 for device in devices if device.is_our_supply)
    return {
        "total": len(devices),
        "ours": ours,
        "others": len(devices) - ours,
        "at_client": len(at_client),
        "no_install": states.count(STATE_NO_INSTALL),
        "removed": states.count(STATE_REMOVED),
        "clients": len(
            {
                install.department.client_id
                for _, install in at_client
                if install.department.client_id is not None
            }
        ),
        "avg_age": avg_age,
        "our_service": sum(1 for device in devices if device.is_our_service),
    }


def installs_by_year(filters: EquipmentFilters, source=None) -> dict:
    """Монтажи по годам (все, включая снятые): нами / не нами и накопительный итог."""
    source = _source(source)
    ours, others = {}, {}
    no_date = 0
    for device in source.devices_of(filters):
        for install in _installs(device):
            if install.install_dt is None:
                no_date += 1
                continue
            bucket = ours if device.is_our_supply else others
            year = install.install_dt.year
            bucket[year] = bucket.get(year, 0) + 1
    years_seen = set(ours) | set(others)
    if not years_seen:
        return {
            "years": [],
            "ours": [],
            "others": [],
            "cumulative": [],
            "no_date": no_date,
        }
    years = list(range(min(years_seen), max(years_seen) + 1))
    cumulative, total = [], 0
    for year in years:
        total += ours.get(year, 0) + others.get(year, 0)
        cumulative.append(total)
    return {
        "years": years,
        "ours": [ours.get(year, 0) for year in years],
        "others": [others.get(year, 0) for year in years],
        "cumulative": cumulative,
        "no_date": no_date,
    }


def _structure_rows(items) -> list[dict]:
    """Строки структуры по тройкам (ключ, подпись, прибор), по убыванию числа."""
    rows = {}
    for key, label, device in items:
        row = rows.setdefault(
            (key, label),
            {"label": label, "key": key, "ours": 0, "others": 0, "total": 0, "ids": []},
        )
        row["ours" if device.is_our_supply else "others"] += 1
        row["total"] += 1
        row["ids"].append(str(device.pk))
    return sorted(rows.values(), key=lambda row: (-row["total"], row["label"]))


def _merge_rest(rows: list[dict], limit: int, label: str) -> list[dict]:
    """Первые `limit` строк и строка-остаток (без ключа) из остальных."""
    if len(rows) <= limit:
        return rows
    rest = {"label": label, "key": None, "ours": 0, "others": 0, "total": 0, "ids": []}
    for row in rows[limit:]:
        for field in ("ours", "others", "total"):
            rest[field] += row[field]
        rest["ids"].extend(row["ids"])
    return rows[:limit] + [rest]


def park_structure(filters: EquipmentFilters, source=None) -> dict:
    """Приборы у клиентов по направлениям, производителям, статусам и регионам."""
    source = _source(source)
    at_client = _at_client(source.devices_of(filters))
    directions, manufacturers, statuses, regions = [], [], [], []
    for device, install in at_client:
        equipment = device.equipment
        direction = equipment.med_direction
        directions.append(
            (
                equipment.med_direction_id,
                direction.name if direction else NO_DIRECTION_LABEL,
                device,
            )
        )
        maker = equipment.manufacturer
        manufacturers.append(
            (
                equipment.manufacturer_id,
                maker.name if maker else NO_MANUFACTURER_LABEL,
                device,
            )
        )
        status = device.equipment_status
        statuses.append(
            (
                status.name if status else None,
                status.name if status else NO_STATUS_LABEL,
                device,
            )
        )
        regions.append((None, region_label(install.department), device))
    return {
        "directions": _structure_rows(directions),
        "manufacturers": _merge_rest(
            _structure_rows(manufacturers), TOP_MANUFACTURERS, OTHER_MANUFACTURERS_LABEL
        ),
        "statuses": _structure_rows(statuses),
        "regions": _structure_rows(regions),
    }


def _age_bucket(age: float) -> str:
    """Корзина возраста; дата монтажа в будущем (возраст < 0) — «<1»."""
    for label, _, high in AGE_BUCKETS:
        if high is None or age < high:
            return label


def park_age(today: date, filters: EquipmentFilters, source=None) -> list[dict]:
    """Приборы у клиентов по возрасту от даты монтажа; без даты — последняя корзина."""
    source = _source(source)
    rows = {
        label: {"label": label, "count": 0, "ids": []} for label, _, _ in AGE_BUCKETS
    }
    rows[AGE_UNKNOWN_LABEL] = {"label": AGE_UNKNOWN_LABEL, "count": 0, "ids": []}
    for device, install in _at_client(source.devices_of(filters)):
        if install.install_dt is None:
            label = AGE_UNKNOWN_LABEL
        else:
            label = _age_bucket(_age_years(install.install_dt, today))
        rows[label]["count"] += 1
        rows[label]["ids"].append(str(device.pk))
    return list(rows.values())


def top_clients(filters: EquipmentFilters, source=None) -> list[dict]:
    """Клиенты с наибольшим числом приборов у них (не больше `TOP_CLIENTS`)."""
    source = _source(source)
    rows = {}
    for device, install in _at_client(source.devices_of(filters)):
        department = install.department
        row = rows.setdefault(
            department.client_id,
            {
                "name": client_label(department),
                "devices": 0,
                "ours": 0,
                "models": set(),
                "ids": [],
            },
        )
        row["devices"] += 1
        row["ours"] += 1 if device.is_our_supply else 0
        row["models"].add(device.equipment_id)
        row["ids"].append(str(device.pk))
    result = [{**row, "models": len(row["models"])} for row in rows.values()]
    result.sort(key=lambda row: (-row["devices"], row["name"]))
    return result[:TOP_CLIENTS]


def _gap(key: str, label: str, items, target: str) -> dict:
    ids = [str(item.pk) for item in items]
    return {"key": key, "label": label, "count": len(ids), "ids": ids, "target": target}


def data_gaps(today: date, filters: EquipmentFilters, source=None) -> list[dict]:
    """Полнота данных: что не внесено в учёт и ремонты (на сегодня, вся история)."""
    source = _source(source)
    devices = source.devices_of(filters)
    at_client = _at_client(devices)
    services = source.services_of(filters)
    old_before = today - timedelta(days=OPEN_REPAIR_DAYS)
    return [
        _gap(
            "no_install",
            "Нет данных о монтаже",
            [d for d in devices if install_state(d) == STATE_NO_INSTALL],
            "accounting",
        ),
        _gap(
            "no_install_date",
            "У клиента, без даты монтажа",
            [d for d, install in at_client if install.install_dt is None],
            "accounting",
        ),
        _gap(
            "no_status",
            "Без статуса",
            [d for d in devices if d.equipment_status_id is None],
            "accounting",
        ),
        _gap(
            "no_engineer",
            "Монтаж без инженера",
            [d for d, install in at_client if install.engineer_id is None],
            "accounting",
        ),
        _gap(
            "no_service_type",
            "Ремонты без вида работ",
            [s for s in services if s.service_type_id is None],
            "service",
        ),
        _gap(
            "old_open",
            "Ремонты без даты окончания старше 365 дней",
            [s for s in services if s.end_dt is None and s.beg_dt < old_before],
            "service",
        ),
    ]


# --- Блок Б: ремонты (за период) -------------------------------------------------


def _median(values) -> Decimal | None:
    """Медиана с шагом 0,1; пусто — None."""
    if not values:
        return None
    return Decimal(str(statistics.median(values))).quantize(TENTH, ROUND_HALF_UP)


def _share_pct(part: int, whole: int) -> Decimal | None:
    """Доля в процентах с шагом 0,1; при нулевом целом — None."""
    if not whole:
        return None
    return (Decimal(part) * 100 / whole).quantize(TENTH, ROUND_HALF_UP)


def _count_by_month(days, months: list[date]) -> list[int]:
    """Число дат по месяцам (`months` — первые числа), вне месяцев — не считаются."""
    return [int(value) for value in _bucket_by_month(((d, 1) for d in days), months)]


def service_type_label(service) -> str:
    """Вид работ ремонта."""
    if service.service_type is None:
        return NO_SERVICE_TYPE_LABEL
    return service.service_type.name


def _repair_values(services) -> dict:
    """Показатели плиток по ремонтам одного периода."""
    kinds = [work_kind(service) for service in services]
    breakdowns = [s for s, kind in zip(services, kinds) if kind == WORK_BREAKDOWN]
    durations = [repair_days(s) for s in breakdowns if s.end_dt is not None]
    with_replacement = sum(1 for s in breakdowns if s.replacement_equipment_id)
    return {
        "total": len(services),
        "planned": kinds.count(WORK_PLANNED),
        "breakdowns": len(breakdowns),
        "median_days": _median(durations),
        "replacement_share": _share_pct(with_replacement, len(breakdowns)),
    }


def _open_split(services, today: date) -> tuple[list, list, date]:
    """Незакрытые ремонты: открытые (не старше года, не в будущем) и старые."""
    old_before = today - timedelta(days=OPEN_REPAIR_DAYS)
    unclosed = [s for s in services if s.end_dt is None]
    opened = [s for s in unclosed if old_before <= s.beg_dt <= today]
    old = [s for s in unclosed if s.beg_dt < old_before]
    return opened, old, old_before


def repairs_kpis(
    period: Period, today: date, filters: EquipmentFilters, source=None
) -> dict:
    """Плитки ремонтов за период и тот же период год назад.

    Дельта доли поломок с подменой — в процентных пунктах, остальные — в %.
    «В работе сейчас» (`open_now`) — на сегодня, период не учитывается.
    """
    source = _source(source)
    services = source.services_in(period, filters)
    current = _repair_values(services)
    previous = _repair_values(source.services_in(period.previous_year(), filters))
    delta = {
        key: _delta_pct(current[key], previous[key])
        for key in REPAIR_KPI_KEYS
        if key != "replacement_share"
    }
    share, previous_share = current["replacement_share"], previous["replacement_share"]
    delta["replacement_share"] = (
        None if share is None or previous_share is None else share - previous_share
    )
    opened, _, _ = _open_split(source.services_of(filters), today)
    return {
        "current": current,
        "previous": previous,
        "delta_pct": delta,
        "open_now": len(opened),
        "unknown_type": sum(1 for s in services if work_kind(s) == WORK_UNKNOWN),
    }


def _department_of(source, service) -> str | None:
    """Подразделение активного монтажа прибора ремонта."""
    device = source.device_of(service)
    install = active_install(device) if device is not None else None
    return department_label(install.department) if install is not None else None


def open_repairs(today: date, filters: EquipmentFilters, source=None) -> dict:
    """Открытые ремонты (на сегодня) и число старых незакрытых."""
    source = _source(source)
    opened, old, old_before = _open_split(source.services_of(filters), today)
    rows = []
    for service in opened:
        device = source.device_of(service)
        replacement = service.replacement_equipment
        rows.append(
            {
                "id": service.pk,
                "device": device_label(device) if device else NO_DEVICE_LABEL,
                "department": _department_of(source, service),
                "service_type": service_type_label(service),
                "beg_dt": service.beg_dt,
                "days": (today - service.beg_dt).days + 1,
                "replacement": replacement_label(replacement) if replacement else None,
            }
        )
    rows.sort(key=lambda row: (-row["days"], row["device"]))
    return {
        "rows": rows,
        "old_count": len(old),
        "old_ids": [str(service.pk) for service in old],
        "old_before": old_before,
    }


def works_by_month(period: Period, filters: EquipmentFilters, source=None) -> dict:
    """Работы периода по месяцам и видам работ (не больше `MAX_MONTH_SERIES` серий)."""
    source = _source(source)
    months = period.months()
    by_type = {}
    for service in source.services_in(period, filters):
        by_type.setdefault(service_type_label(service), []).append(service.beg_dt)
    labels = sorted(by_type, key=lambda label: (-len(by_type[label]), label))
    if len(labels) > MAX_MONTH_SERIES:
        rest = [
            day for label in labels[MAX_MONTH_SERIES - 1 :] for day in by_type[label]
        ]
        labels = labels[: MAX_MONTH_SERIES - 1]
        by_type = {label: by_type[label] for label in labels}
        by_type[OTHER_SERVICE_TYPES_LABEL] = rest
        labels.append(OTHER_SERVICE_TYPES_LABEL)
    return {
        "months": months,
        "series": [
            {"label": label, "data": _count_by_month(by_type[label], months)}
            for label in labels
        ],
    }


def planned_by_month(period: Period, filters: EquipmentFilters, source=None) -> dict:
    """ТО по месяцам: нами / не нами / без прибора и ТО того же месяца год назад."""
    source = _source(source)
    months = period.months()
    groups = {"ours": [], "others": [], "no_device": []}
    for service in source.services_in(period, filters):
        if work_kind(service) != WORK_PLANNED:
            continue
        device = source.device_of(service)
        if device is None:
            key = "no_device"
        else:
            key = "ours" if device.is_our_supply else "others"
        groups[key].append(service.beg_dt)
    previous_period = period.previous_year()
    previous = [
        service.beg_dt
        for service in source.services_in(previous_period, filters)
        if work_kind(service) == WORK_PLANNED
    ]
    return {
        "months": months,
        **{key: _count_by_month(days, months) for key, days in groups.items()},
        "previous": _count_by_month(previous, previous_period.months()),
    }


def _duration_bucket(days: int) -> str:
    for label, _, high in DURATION_BUCKETS:
        if high is None or days <= high:
            return label


def duration_stats(period: Period, filters: EquipmentFilters, source=None) -> dict:
    """Длительность: корзины по закрытым поломкам, таблица по видам работ."""
    source = _source(source)
    services = source.services_in(period, filters)
    buckets = {
        label: {"label": label, "count": 0, "ids": []}
        for label, _, _ in DURATION_BUCKETS
    }
    by_type = {}
    for service in services:
        days = repair_days(service)
        if days is None:
            continue
        by_type.setdefault(service_type_label(service), []).append(days)
        if work_kind(service) == WORK_BREAKDOWN:
            bucket = buckets[_duration_bucket(days)]
            bucket["count"] += 1
            bucket["ids"].append(str(service.pk))
    rows = [
        {
            "label": label,
            "count": len(values),
            "median": _median(values),
            "max": max(values),
        }
        for label, values in by_type.items()
    ]
    rows.sort(key=lambda row: (-row["count"], row["label"]))
    return {
        "buckets": list(buckets.values()),
        "by_type": rows,
        "open": sum(1 for service in services if service.end_dt is None),
    }


def engineer_load(period: Period, filters: EquipmentFilters, source=None) -> dict:
    """Число работ «инженер × месяц» периода.

    Ключ `days` в строках — число работ: так строки подходят к
    `_with_load_shades` из вкладки «Командировки».
    """
    source = _source(source)
    months = period.months()
    by_engineer = {}
    for service in source.services_in(period, filters):
        name = service.engineer.name if service.engineer else NO_ENGINEER_LABEL
        by_engineer.setdefault(name, []).append(service.beg_dt)
    rows = [
        {"name": name, "days": _count_by_month(days, months), "total": len(days)}
        for name, days in by_engineer.items()
    ]
    rows.sort(key=lambda row: (-row["total"], row["name"]))
    return {
        "months": months,
        "rows": rows,
        "max": max((count for row in rows for count in row["days"]), default=0),
    }


# --- Блок В: надёжность моделей (только поломки) -------------------------------


def effective_days(period: Period, today: date) -> int:
    """Дни периода до сегодняшнего дня включительно; период в будущем — 0."""
    end = min(period.date_to, today)
    return max((end - period.date_from).days + 1, 0)


def _per_unit_year(breakdowns: int, units: int, days: int) -> Decimal | None:
    """Поломок на прибор в год: поломки / приборы × 365 / дни периода."""
    if not units or not days:
        return None
    return (Decimal(breakdowns) / units * DAYS_IN_YEAR / days).quantize(
        HUNDREDTH, ROUND_HALF_UP
    )


def _period_breakdowns(source, period, today, filters) -> list:
    """Поломки периода с прибором, начатые не позже сегодня (для частоты в год)."""
    return [
        service
        for service in source.services_in(period, filters)
        if work_kind(service) == WORK_BREAKDOWN
        and service.beg_dt <= today
        and source.device_of(service) is not None
    ]


def _units_by_model(source, filters) -> dict:
    """Приборы у клиентов по модели: {equipment_id: [прибор, ...]}."""
    units = {}
    for device, _ in _at_client(source.devices_of(filters)):
        units.setdefault(device.equipment_id, []).append(device)
    return units


def reliability(
    period: Period, today: date, filters: EquipmentFilters, source=None
) -> list[dict]:
    """Поломок на прибор в год по моделям с `MIN_UNITS_FOR_RELIABILITY`+ приборами.

    Знаменатель — приборы модели у клиентов сейчас: истории парка нет.
    """
    source = _source(source)
    days = effective_days(period, today)
    if not days:
        return []
    units = _units_by_model(source, filters)
    by_model = {}
    for service in _period_breakdowns(source, period, today, filters):
        by_model.setdefault(source.device_of(service).equipment_id, []).append(service)
    rows = []
    for equipment_id, services in by_model.items():
        devices = units.get(equipment_id, [])
        if len(devices) < MIN_UNITS_FOR_RELIABILITY:
            continue
        rows.append(
            {
                "equipment_id": equipment_id,
                "label": model_label(devices[0].equipment),
                "units": len(devices),
                "breakdowns": len(services),
                "per_unit_year": _per_unit_year(len(services), len(devices), days),
                "service_ids": [str(service.pk) for service in services],
            }
        )
    rows.sort(key=lambda row: (-row["per_unit_year"], -row["breakdowns"], row["label"]))
    return rows[:TOP_RELIABILITY]


def _breakdown_history(source, filters) -> dict:
    """Все поломки приборов (вся история): {id прибора: [ремонт, ...]} по дате начала."""
    history = {}
    for service in source.services_of(filters):
        if work_kind(service) != WORK_BREAKDOWN:
            continue
        device = source.device_of(service)
        if device is not None:
            history.setdefault(device.pk, []).append(service)
    for services in history.values():
        services.sort(key=lambda service: (service.beg_dt, service.create_dt))
    return history


def _device_department(device) -> str | None:
    install = active_install(device)
    return department_label(install.department) if install is not None else None


def repeat_repairs(period: Period, filters: EquipmentFilters, source=None) -> dict:
    """Поломки периода, у которых прошлая поломка прибора закончилась ≤ 30 / 90 дней назад.

    Прошлая поломка ищется по всей истории; её дата — окончание, без него — начало.
    """
    source = _source(source)
    window = max(REPEAT_WINDOWS)
    rows = []
    for device_id, services in _breakdown_history(source, filters).items():
        device = source.device_by_id[device_id]
        for previous, current in zip(services, services[1:]):
            if not period.date_from <= current.beg_dt <= period.date_to:
                continue
            previous_date = previous.end_dt or previous.beg_dt
            gap = max((current.beg_dt - previous_date).days, 0)
            if gap > window:
                continue
            rows.append(
                {
                    "device": device_label(device),
                    "department": _device_department(device),
                    "previous_id": previous.pk,
                    "previous_date": previous_date,
                    "current_id": current.pk,
                    "current_date": current.beg_dt,
                    "gap_days": gap,
                }
            )
    rows.sort(key=lambda row: (row["gap_days"], -row["current_date"].toordinal()))
    return {
        "counts": {
            days: sum(1 for row in rows if row["gap_days"] <= days)
            for days in REPEAT_WINDOWS
        },
        "rows": rows,
    }


def problem_devices(
    period: Period, filters: EquipmentFilters, source=None
) -> list[dict]:
    """Приборы с двумя и более поломками за всю историю (`TOP_PROBLEM_DEVICES` строк)."""
    source = _source(source)
    rows = []
    for device_id, services in _breakdown_history(source, filters).items():
        if len(services) < 2:
            continue
        device = source.device_by_id[device_id]
        rows.append(
            {
                "device_id": device_id,
                "device": device_label(device),
                "department": _device_department(device),
                "total": len(services),
                "in_period": sum(
                    1
                    for service in services
                    if period.date_from <= service.beg_dt <= period.date_to
                ),
                "last_date": max(service.beg_dt for service in services),
            }
        )
    rows.sort(key=lambda row: (-row["total"], -row["last_date"].toordinal()))
    return rows[:TOP_PROBLEM_DEVICES]


def _directory_name(item, empty_label: str) -> str:
    return item.name if item is not None else empty_label


def models_summary(
    period: Period, today: date, filters: EquipmentFilters, source=None
) -> list[dict]:
    """Сводная по моделям: парк, ТО и поломки периода, частота, ремонт, подменный фонд."""
    source = _source(source)
    days = effective_days(period, today)
    models = {}

    def row_of(equipment) -> dict:
        return models.setdefault(
            equipment.pk,
            {
                "equipment_id": equipment.pk,
                "label": model_label(equipment),
                "manufacturer": _directory_name(
                    equipment.manufacturer, NO_MANUFACTURER_LABEL
                ),
                "direction": _directory_name(
                    equipment.med_direction, NO_DIRECTION_LABEL
                ),
                "at_client": 0,
                "ours": 0,
                "others": 0,
                "planned": 0,
                "breakdowns": 0,
                "durations": [],
                "fund_working": 0,
                "fund_total": 0,
            },
        )

    for device, _ in _at_client(source.devices_of(filters)):
        row = row_of(device.equipment)
        row["at_client"] += 1
        row["ours" if device.is_our_supply else "others"] += 1
    for service in source.services_in(period, filters):
        device = source.device_of(service)
        if device is not None and work_kind(service) == WORK_PLANNED:
            row_of(device.equipment)["planned"] += 1
    for service in _period_breakdowns(source, period, today, filters):
        row = row_of(source.device_of(service).equipment)
        row["breakdowns"] += 1
        if service.end_dt is not None:
            row["durations"].append(repair_days(service))
    for replacement in source.replacements_of(filters):
        row = row_of(replacement.equipment)
        row["fund_total"] += 1
        row["fund_working"] += 1 if replacement.state == "working" else 0
    result = []
    for row in models.values():
        durations = row.pop("durations")
        result.append(
            {
                **row,
                "per_unit_year": _per_unit_year(
                    row["breakdowns"], row["at_client"], days
                ),
                "median_days": _median(durations),
            }
        )
    result.sort(key=lambda row: (-row["breakdowns"], -row["at_client"], row["label"]))
    return result


# --- Блок Г: подменный фонд ---------------------------------------------------

REPLACEMENT_WORKING = "working"


def replacement_location(replacement, source: EquipmentSet) -> dict:
    """Где подменный прибор сейчас — как колонка «Передано» в админке.

    Берётся последняя выдача (по дате начала ремонта и дате создания): прибор
    у клиента, если в ней нет отметки «Вернули в офис» и у ремонтируемого
    прибора есть активный монтаж; иначе — в офисе.
    """
    issues = source.issues_of(replacement)
    if not issues:
        return {"at_client": False, "service": None, "department": None}
    last = issues[-1]
    device = source.device_of(last)
    install = active_install(device) if device is not None else None
    at_client = not last.returned_to_office and install is not None
    return {
        "at_client": at_client,
        "service": last,
        "department": department_label(install.department) if at_client else None,
    }


def _issues_in(source, replacements, period: Period) -> int:
    """Выдачи подменных `replacements` в ремонты с датой начала в периоде."""
    ids = {replacement.pk for replacement in replacements}
    return sum(
        1
        for service in source.services
        if service.replacement_equipment_id in ids
        and period.date_from <= service.beg_dt <= period.date_to
    )


def fund_kpis(
    period: Period, today: date, filters: EquipmentFilters, source=None
) -> dict:
    """Плитки фонда: всего, рабочих, нерабочих, у клиентов, в офисе (на сегодня)
    и выдачи за период с дельтой к прошлому году. «Поставка» не действует."""
    source = _source(source)
    replacements = source.replacements_of(filters)
    at_client = sum(
        1
        for replacement in replacements
        if replacement_location(replacement, source)["at_client"]
    )
    working = sum(1 for r in replacements if r.state == REPLACEMENT_WORKING)
    current = _issues_in(source, replacements, period)
    previous = _issues_in(source, replacements, period.previous_year())
    return {
        "total": len(replacements),
        "working": working,
        "not_working": len(replacements) - working,
        "at_client": at_client,
        "in_office": len(replacements) - at_client,
        "issues": {
            "current": current,
            "previous": previous,
            "delta_pct": _delta_pct(current, previous),
        },
    }


def replacements_at_clients(
    today: date, filters: EquipmentFilters, source=None
) -> list[dict]:
    """Подменные приборы у клиентов: сверху — ремонт закрыт, а прибор не вернули."""
    source = _source(source)
    rows = []
    for replacement in source.replacements_of(filters):
        location = replacement_location(replacement, source)
        if not location["at_client"]:
            continue
        service = location["service"]
        rows.append(
            {
                "replacement_id": replacement.pk,
                "label": replacement_label(replacement),
                "department": location["department"],
                "since": service.beg_dt,
                "days": max((today - service.beg_dt).days + 1, 1),
                "service_id": service.pk,
                "repair_closed": service.end_dt is not None,
                "end_dt": service.end_dt,
                "overdue": service.end_dt is not None,
            }
        )
    rows.sort(key=lambda row: (not row["overdue"], -row["days"], row["label"]))
    return rows


def issue_interval(service, next_issue, today: date) -> tuple[date, date]:
    """Даты выдачи подменного прибора в ремонт `service`.

    Последняя выдача: не вернули или ремонт не закрыт — до сегодня, иначе до end_dt.
    Ранняя выдача: до end_dt, но не позже дня перед следующей выдачей (старые
    ремонты без отметки «Вернули в офис» не тянутся до сегодня).
    """
    start = service.beg_dt
    if next_issue is None:
        closed = service.end_dt is not None and service.returned_to_office
        end = service.end_dt if closed else today
    else:
        cap = next_issue.beg_dt - timedelta(days=1)
        end = min(service.end_dt or cap, cap)
    return start, max(end, start)


def issue_timeline(
    period: Period, today: date, filters: EquipmentFilters, source=None
) -> dict:
    """Выдачи каждого подменного прибора в ремонты, видимые в периоде (до сегодня).

    Полоса — часть выдачи внутри периода: `left_pct` и `width_pct` — её начало
    и длина в процентах периода; `days` — дни на выдаче в периоде без повторов.
    """
    source = _source(source)
    period_days = (period.date_to - period.date_from).days + 1
    visible_until = min(period.date_to, today)
    rows = []
    for replacement in source.replacements_of(filters):
        issues = source.issues_of(replacement)
        bars, days = [], set()
        for index, service in enumerate(issues):
            next_issue = issues[index + 1] if index + 1 < len(issues) else None
            start, end = issue_interval(service, next_issue, today)
            visible_start = max(start, period.date_from)
            visible_end = min(end, visible_until)
            if visible_end < visible_start:
                continue
            length = (visible_end - visible_start).days + 1
            bars.append(
                {
                    "service_id": service.pk,
                    "start": start,
                    "end": end,
                    "left_pct": round(
                        (visible_start - period.date_from).days / period_days * 100, 2
                    ),
                    "width_pct": round(length / period_days * 100, 2),
                }
            )
            days.update(visible_start + timedelta(days=n) for n in range(length))
        rows.append(
            {
                "replacement_id": replacement.pk,
                "label": replacement_label(replacement),
                "bars": bars,
                "days": len(days),
            }
        )
    rows.sort(key=lambda row: row["label"])
    return {"months": period.months(), "rows": rows}


def replacement_shortage(
    period: Period, filters: EquipmentFilters, source=None
) -> list[dict]:
    """Поломки периода по моделям: без подмены и с подменой, сколько подменных есть.

    Подменные считаются рабочие, без фильтров: этой модели и того же направления.
    """
    source = _source(source)
    working = [r for r in source.replacements if r.state == REPLACEMENT_WORKING]
    rows = {}
    for service in source.services_in(period, filters):
        device = source.device_of(service)
        if device is None or work_kind(service) != WORK_BREAKDOWN:
            continue
        equipment = device.equipment
        row = rows.setdefault(
            equipment.pk,
            {
                "equipment_id": equipment.pk,
                "label": model_label(equipment),
                "direction_id": equipment.med_direction_id,
                "without": 0,
                "with": 0,
                "durations": [],
            },
        )
        row["with" if service.replacement_equipment_id else "without"] += 1
        if service.end_dt is not None:
            row["durations"].append(repair_days(service))
    result = []
    for row in rows.values():
        direction_id = row.pop("direction_id")
        durations = row.pop("durations")
        result.append(
            {
                **row,
                "median_days": _median(durations),
                "fund_model": sum(
                    1 for r in working if r.equipment_id == row["equipment_id"]
                ),
                "fund_direction": (
                    None
                    if direction_id is None
                    else sum(
                        1
                        for r in working
                        if r.equipment.med_direction_id == direction_id
                    )
                ),
            }
        )
    result.sort(key=lambda row: (-row["without"], -row["with"], row["label"]))
    return result
