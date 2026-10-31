"""Загрузка и отбор данных вкладки «Запчасти»."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from analytics.filters import Period, SparePartFilters
from spare_part.models import (
    SparePart,
    SparePartCount,
    SparePartShipment,
    SparePartShipmentM2M,
    SparePartSupply,
    SparePartSupplyItem,
)

DEMAND_DAYS = 365
ZERO = Decimal("0")


def window_start(today: date, days: int) -> date:
    """Первый день закрытого окна из `days` календарных дней."""
    return today - timedelta(days=days - 1)


def _decimal(value) -> Decimal:
    return Decimal(str(value))


@dataclass(frozen=True)
class SupplyRow:
    document_id: object
    part_id: object
    supply_dt: date
    quantity: Decimal
    amount: Decimal | None
    price: Decimal | None
    expiration_dt: date | None
    is_archive: bool


@dataclass(frozen=True)
class ShipmentRow:
    document_id: object
    part_id: object
    shipment_dt: date
    quantity: Decimal
    cost: Decimal | None
    price: Decimal | None
    expiration_dt: date | None
    equipment_id: object | None
    equipment_label: str | None
    is_archive: bool


@dataclass(frozen=True)
class SparePartSet:
    """Единый набор справочника, остатков и движений V1/V2."""

    parts: list[SparePart]
    counts: list[SparePartCount]
    supplies: list[SupplyRow]
    shipments: list[ShipmentRow]
    part_by_id: dict

    @classmethod
    def load(cls) -> "SparePartSet":
        """Загружает все исходные данные семью запросами."""
        parts = list(
            SparePart.objects.select_related("unit")
            .prefetch_related("equipment")
            .order_by("name", "article")
        )
        part_by_id = {part.pk: part for part in parts}
        counts = list(SparePartCount.objects.all())
        supplies = [
            SupplyRow(
                document_id=item.supply_id,
                part_id=item.spare_part_id,
                supply_dt=item.supply.supply_dt,
                quantity=_decimal(item.quantity),
                amount=item.sum,
                price=item.price,
                expiration_dt=item.expiration_dt,
                is_archive=False,
            )
            for item in SparePartSupplyItem.objects.select_related("supply")
        ]
        supplies.extend(
            SupplyRow(
                document_id=item["id"],
                part_id=item["spare_part_id"],
                supply_dt=item["supply_dt"],
                quantity=_decimal(item["count_supply"]),
                amount=None,
                price=None,
                expiration_dt=item["expiration_dt"],
                is_archive=True,
            )
            for item in SparePartSupply.objects.filter(
                spare_part__isnull=False
            ).values(
                "id",
                "spare_part_id",
                "supply_dt",
                "count_supply",
                "expiration_dt",
            )
        )
        shipments = []
        shipment_items = SparePartShipmentM2M.objects.select_related(
            "shipment__service__equipment_accounting__equipment"
        )
        for item in shipment_items:
            service = item.shipment.service
            accounting = service.equipment_accounting if service else None
            equipment = accounting.equipment if accounting else None
            shipments.append(
                ShipmentRow(
                    document_id=item.shipment_id,
                    part_id=item.spare_part_id,
                    shipment_dt=item.shipment.shipment_dt,
                    quantity=_decimal(item.quantity),
                    cost=item.sum,
                    price=item.price,
                    expiration_dt=item.expiration_dt,
                    equipment_id=equipment.pk if equipment else None,
                    equipment_label=(
                        equipment.full_name
                        or equipment.short_name
                        or "Модель без названия"
                    )
                    if equipment
                    else None,
                    is_archive=False,
                )
            )
        for item in SparePartShipment.objects.select_related("spare_part_count"):
            if item.spare_part_count is None:
                continue
            shipments.append(
                ShipmentRow(
                    document_id=item.pk,
                    part_id=item.spare_part_count.spare_part_id,
                    shipment_dt=item.shipment_dt,
                    quantity=_decimal(item.count_shipment),
                    cost=None,
                    price=None,
                    expiration_dt=item.spare_part_count.expiration_dt,
                    equipment_id=None,
                    equipment_label=None,
                    is_archive=True,
                )
            )
        return cls(parts, counts, supplies, shipments, part_by_id)

    def stock_total(self, part_id) -> Decimal:
        """Суммарный остаток; отсутствие записей означает ноль."""
        return sum(
            (
                _decimal(count.amount)
                for count in self.counts
                if count.spare_part_id == part_id
            ),
            ZERO,
        )

    def last_shipment(self, part_id, today: date) -> ShipmentRow | None:
        """Последняя отгрузка не позже сегодняшнего дня."""
        rows = [
            row
            for row in self.shipments
            if row.part_id == part_id and row.shipment_dt <= today
        ]
        if not rows:
            return None
        return max(
            rows,
            key=lambda row: (
                row.shipment_dt,
                str(row.document_id),
                not row.is_archive,
            ),
        )

    def supplies_in(self, part_ids, period: Period) -> list[SupplyRow]:
        """Поставки выбранных запчастей в закрытом периоде."""
        selected = set(part_ids)
        return [
            row
            for row in self.supplies
            if row.part_id in selected
            and period.date_from <= row.supply_dt <= period.date_to
        ]

    def shipments_in(self, part_ids, period: Period) -> list[ShipmentRow]:
        """Отгрузки выбранных запчастей в закрытом периоде."""
        selected = set(part_ids)
        return [
            row
            for row in self.shipments
            if row.part_id in selected
            and period.date_from <= row.shipment_dt <= period.date_to
        ]


def _source(source) -> SparePartSet:
    return source if source is not None else SparePartSet.load()


def _matches_expiration(part, counts, choice: str, today: date) -> bool:
    if choice == "all":
        return True
    for count in counts:
        if _decimal(count.amount) <= 0:
            continue
        expiration = count.expiration_dt
        if choice == "missing":
            if part.is_expiration and expiration is None:
                return True
        elif expiration is not None:
            if choice == "overdue" and expiration < today:
                return True
            if choice.isdigit() and today <= expiration <= today + timedelta(
                days=int(choice)
            ):
                return True
    return False


def parts_of(
    filters: SparePartFilters, today: date, source=None
) -> list[SparePart]:
    """Отбирает запчасти целиком по уже загруженным данным."""
    source = _source(source)
    result = []
    for part in source.parts:
        if filters.spare_part is not None and part.pk != filters.spare_part.pk:
            continue
        if filters.equipment is not None and all(
            equipment.pk != filters.equipment.pk for equipment in part.equipment.all()
        ):
            continue
        counts = [count for count in source.counts if count.spare_part_id == part.pk]
        stock = source.stock_total(part.pk)
        if filters.stock == "positive" and stock <= 0:
            continue
        if filters.stock == "zero" and stock != 0:
            continue
        if filters.stock == "negative" and stock >= 0:
            continue
        if not _matches_expiration(part, counts, filters.expiration, today):
            continue
        if filters.nonmoving != "all":
            if stock <= 0:
                continue
            last = source.last_shipment(part.pk, today)
            start = window_start(today, int(filters.nonmoving))
            if last is not None and last.shipment_dt >= start:
                continue
        result.append(part)
    return result
