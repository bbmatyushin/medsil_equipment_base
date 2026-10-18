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

from datetime import date

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
