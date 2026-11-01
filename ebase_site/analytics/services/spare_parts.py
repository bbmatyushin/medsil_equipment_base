"""Загрузка и отбор данных вкладки «Запчасти»."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from analytics.filters import Period, SparePartFilters
from analytics.services.finance import _bucket_by_month
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
            for item in SparePartSupply.objects.filter(spare_part__isnull=False).values(
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
                        (
                            equipment.full_name
                            or equipment.short_name
                            or "Модель без названия"
                        )
                        if equipment
                        else None
                    ),
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


def parts_of(filters: SparePartFilters, today: date, source=None) -> list[SparePart]:
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


def _price_indexes(source):
    """Суммы и количества известных цен по сроку и по запчасти."""
    exact = {}
    overall = {}
    for row in source.supplies:
        if row.is_archive or row.quantity <= 0 or row.price is None or row.price <= 0:
            continue
        amount = row.quantity * row.price
        for index, key in (
            (exact, (row.part_id, row.expiration_dt)),
            (overall, row.part_id),
        ):
            total_amount, total_quantity = index.get(key, (ZERO, ZERO))
            index[key] = (total_amount + amount, total_quantity + row.quantity)
    return exact, overall


def _indexed_price(part_id, expiration_dt, indexes) -> Decimal | None:
    exact, overall = indexes
    amount, quantity = exact.get((part_id, expiration_dt), (ZERO, ZERO))
    if quantity <= 0:
        amount, quantity = overall.get(part_id, (ZERO, ZERO))
    return amount / quantity if quantity > 0 else None


def known_price(part_id, expiration_dt, source=None) -> Decimal | None:
    """Средняя известная цена сначала по сроку, затем по всей запчасти."""
    source = _source(source)
    return _indexed_price(part_id, expiration_dt, _price_indexes(source))


def stock_value(count, source=None) -> Decimal | None:
    """Оценка положительной складской записи при известной цене."""
    source = _source(source)
    amount = _decimal(count.amount)
    if amount <= 0:
        return None
    price = known_price(count.spare_part_id, count.expiration_dt, source)
    return amount * price if price is not None else None


def _part_valuation(part_id, counts, indexes):
    """Известная стоимость и полнота оценки всех положительных записей."""
    value = ZERO
    positive = False
    complete = True
    for count in counts:
        amount = _decimal(count.amount)
        if amount <= 0:
            continue
        positive = True
        price = _indexed_price(part_id, count.expiration_dt, indexes)
        if price is None:
            complete = False
        else:
            value += amount * price
    return (value if positive and value > 0 else None), positive and complete


def _sums_by_part(rows, date_field, value_field):
    result = {}
    for row in rows:
        result[row.part_id] = result.get(row.part_id, ZERO) + getattr(row, value_field)
    return result


def stock_rows(period, today, filters, source=None) -> list[dict]:
    """Строки склада: снимок, движение периода и спрос за 365 дней."""
    source = _source(source)
    parts = parts_of(filters, today, source)
    part_ids = [part.pk for part in parts]
    received = _sums_by_part(
        source.supplies_in(part_ids, period), "supply_dt", "quantity"
    )
    shipped = _sums_by_part(
        source.shipments_in(part_ids, period), "shipment_dt", "quantity"
    )
    demand_start = window_start(today, DEMAND_DAYS)
    demand_rows = [
        row
        for row in source.shipments
        if row.part_id in set(part_ids) and demand_start <= row.shipment_dt <= today
    ]
    demand = _sums_by_part(demand_rows, "shipment_dt", "quantity")
    indexes = _price_indexes(source)
    result = []
    for part in parts:
        counts = [count for count in source.counts if count.spare_part_id == part.pk]
        stock = source.stock_total(part.pk)
        value, complete = _part_valuation(part.pk, counts, indexes)
        part_demand = demand.get(part.pk, ZERO)
        average_monthly = (part_demand / Decimal("12")).quantize(Decimal("0.01"))
        days_stock = None
        if stock > 0 and part_demand > 0:
            exact_days = stock * Decimal(DEMAND_DAYS) / part_demand
            days_stock = int(exact_days)
            if Decimal(days_stock) < exact_days:
                days_stock += 1
        last = source.last_shipment(part.pk, today)
        result.append(
            {
                "id": part.pk,
                "label": part.name,
                "article": part.article,
                "unit": str(part.unit),
                "stock": stock,
                "average_price": _indexed_price(part.pk, None, indexes),
                "stock_value": value,
                "value_complete": complete,
                "received": received.get(part.pk, ZERO),
                "shipped": shipped.get(part.pk, ZERO),
                "average_monthly": average_monthly,
                "days_stock": days_stock,
                "last_shipment": last.shipment_dt if last else None,
                "nonmoving_180": stock > 0
                and (last is None or last.shipment_dt < window_start(today, 180)),
                "nonmoving_365": stock > 0
                and (
                    last is None or last.shipment_dt < window_start(today, DEMAND_DAYS)
                ),
            }
        )
    result.sort(
        key=lambda row: (
            row["stock_value"] is None,
            -(row["stock_value"] or ZERO),
            row["label"],
            row["article"] or "",
        )
    )
    return result


def overview_kpis(period, today, filters, source=None) -> dict:
    """Плитки склада и денежные итоги V2 за период."""
    source = _source(source)
    rows = stock_rows(period, today, filters, source)
    part_ids = [row["id"] for row in rows]
    supplies = source.supplies_in(part_ids, period)
    shipments = source.shipments_in(part_ids, period)
    return {
        "positive_count": sum(row["stock"] > 0 for row in rows),
        "stock_value": sum((row["stock_value"] or ZERO for row in rows), ZERO),
        "priced_count": sum(row["value_complete"] for row in rows),
        "priced_total": sum(row["stock"] > 0 for row in rows),
        "purchase_amount": sum(
            (row.amount or ZERO for row in supplies if not row.is_archive), ZERO
        ),
        "shipment_cost": sum(
            (row.cost or ZERO for row in shipments if not row.is_archive), ZERO
        ),
    }


def _period_v2_rows(period, filters, source):
    """Движения V2 отобранных позиций за период."""
    source = _source(source)
    part_ids = [part.pk for part in parts_of(filters, timezone.localdate(), source)]
    supplies = [
        row for row in source.supplies_in(part_ids, period) if not row.is_archive
    ]
    shipments = [
        row for row in source.shipments_in(part_ids, period) if not row.is_archive
    ]
    return source, supplies, shipments


def money_by_month(period, filters, source=None) -> dict:
    """Закупки, себестоимость отгрузок и их сальдо по месяцам периода."""
    _, supplies, shipments = _period_v2_rows(period, filters, source)
    months = period.months()
    purchases = _bucket_by_month(
        ((row.supply_dt, row.amount or ZERO) for row in supplies),
        months,
    )
    shipped = _bucket_by_month(
        ((row.shipment_dt, row.cost or ZERO) for row in shipments),
        months,
    )
    return {
        "months": months,
        "purchases": purchases,
        "shipments": shipped,
        "balance": [purchase - cost for purchase, cost in zip(purchases, shipped)],
    }


def top_parts(period, filters, source=None, limit=15) -> list[dict]:
    """Запчасти с наибольшей себестоимостью отгрузок V2."""
    source, _, shipments = _period_v2_rows(period, filters, source)
    groups = {}
    for row in shipments:
        group = groups.setdefault(
            row.part_id,
            {
                "id": row.part_id,
                "label": source.part_by_id[row.part_id].name,
                "cost": ZERO,
                "shipment_ids": set(),
            },
        )
        group["cost"] += row.cost or ZERO
        group["shipment_ids"].add(row.document_id)
    rows = [row for row in groups.values() if row["cost"] != 0]
    for row in rows:
        row["shipment_ids"] = sorted(row["shipment_ids"], key=str)
    rows.sort(key=lambda row: (-row["cost"], row["label"]))
    return rows[:limit]


def top_equipment(period, filters, source=None, limit=15) -> dict:
    """Расход запчастей по фактическим моделям из связанных ремонтов."""
    _, _, shipments = _period_v2_rows(period, filters, source)
    groups = {}
    without_equipment_cost = ZERO
    for row in shipments:
        cost = row.cost or ZERO
        if row.equipment_id is None:
            without_equipment_cost += cost
            continue
        group = groups.setdefault(
            row.equipment_id,
            {
                "equipment_id": row.equipment_id,
                "label": row.equipment_label or "Модель без названия",
                "cost": ZERO,
                "shipment_ids": set(),
            },
        )
        group["cost"] += cost
        group["shipment_ids"].add(row.document_id)
    rows = [row for row in groups.values() if row["cost"] != 0]
    for row in rows:
        row["shipment_ids"] = sorted(row["shipment_ids"], key=str)
    rows.sort(key=lambda row: (-row["cost"], row["label"]))
    return {
        "rows": rows[:limit],
        "without_equipment_cost": without_equipment_cost,
    }
