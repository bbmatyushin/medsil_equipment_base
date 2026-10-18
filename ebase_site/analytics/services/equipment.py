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

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Prefetch

from analytics.filters import EquipmentFilters, Period
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
