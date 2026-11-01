from datetime import date, timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from analytics.filters import Period, SparePartFilters
from analytics.services import spare_parts as sp
from analytics.tests.factories import (
    make_device,
    make_equipment,
    make_part_shipment,
    make_service,
    make_spare_part,
    make_stock,
    make_supply,
)
from spare_part.models import SparePartShipment, SparePartSupply

TODAY = date(2026, 10, 16)


class SparePartSetTests(TestCase):
    def test_load_normalizes_v2_and_archive(self):
        part = make_spare_part()
        equipment = make_equipment("BC-5000")
        service = make_service(make_device(equipment, "SN-1"), TODAY)
        supply = make_supply(part, TODAY, 5, price=120)
        archive_supply = make_supply(part, TODAY, 2, archive=True)
        shipment = make_part_shipment(part, TODAY, 1, price=110, service=service)
        archive_shipment = make_part_shipment(part, TODAY, 1, archive=True)

        source = sp.SparePartSet.load()
        supply_row = next(
            row for row in source.supplies if row.document_id == supply.supply_id
        )
        old_supply_row = next(
            row for row in source.supplies if row.document_id == archive_supply.pk
        )
        shipment_row = next(
            row for row in source.shipments if row.document_id == shipment.shipment_id
        )
        old_shipment_row = next(
            row for row in source.shipments if row.document_id == archive_shipment.pk
        )

        self.assertEqual(supply_row.quantity, Decimal("5"))
        self.assertEqual(supply_row.amount, Decimal("600.00"))
        self.assertEqual(supply_row.price, Decimal("120.00"))
        self.assertFalse(supply_row.is_archive)
        self.assertEqual(old_supply_row.quantity, Decimal("2"))
        self.assertIsNone(old_supply_row.amount)
        self.assertIsNone(old_supply_row.price)
        self.assertTrue(old_supply_row.is_archive)
        self.assertEqual(shipment_row.cost, Decimal("110.00"))
        self.assertEqual(shipment_row.equipment_id, equipment.pk)
        self.assertEqual(shipment_row.equipment_label, "BC-5000")
        self.assertEqual(old_shipment_row.quantity, Decimal("1"))
        self.assertIsNone(old_shipment_row.cost)
        self.assertIsNone(old_shipment_row.equipment_id)
        self.assertTrue(old_shipment_row.is_archive)

    def test_load_ignores_movements_without_part(self):
        old_supply = make_supply(make_spare_part(), TODAY, 1, archive=True)
        old_supply.spare_part = None
        old_supply.save(update_fields=["spare_part"])
        old_shipment = make_part_shipment(
            make_spare_part(name="Другая"), TODAY, 1, archive=True
        )
        old_shipment.spare_part_count = None
        old_shipment.save(update_fields=["spare_part_count"])

        source = sp.SparePartSet.load()

        self.assertNotIn(old_supply.pk, {row.document_id for row in source.supplies})
        self.assertNotIn(
            old_shipment.pk, {row.document_id for row in source.shipments}
        )

    def test_stock_total_without_count_is_zero(self):
        part = make_spare_part()
        source = sp.SparePartSet.load()
        self.assertEqual(source.stock_total(part.pk), Decimal("0"))

    def test_last_shipment_uses_history_but_not_future(self):
        part = make_spare_part()
        old = make_part_shipment(part, TODAY - timedelta(days=10), 1, archive=True)
        current = make_part_shipment(part, TODAY, 1)
        make_part_shipment(part, TODAY + timedelta(days=1), 1)
        same_day = make_part_shipment(part, TODAY, 1, archive=True)
        source = sp.SparePartSet.load()

        first = source.last_shipment(part.pk, TODAY)
        second = source.last_shipment(part.pk, TODAY)

        self.assertEqual(first, second)
        self.assertIn(first.document_id, {current.shipment_id, same_day.pk})
        self.assertNotEqual(first.document_id, old.pk)

    def test_period_movements_include_boundaries_and_both_versions(self):
        part = make_spare_part()
        period = Period(date(2026, 2, 1), date(2026, 2, 28))
        supply_days = [date(2026, 1, 31), *period_month_edges(period), date(2026, 3, 1)]
        supplies = [make_supply(part, day, 1) for day in supply_days]
        old_supply = make_supply(part, period.date_from, 1, archive=True)
        shipments = [make_part_shipment(part, day, 1) for day in supply_days]
        old_shipment = make_part_shipment(part, period.date_to, 1, archive=True)
        source = sp.SparePartSet.load()

        supply_ids = {
            row.document_id for row in source.supplies_in([part.pk], period)
        }
        shipment_ids = {
            row.document_id for row in source.shipments_in([part.pk], period)
        }

        self.assertEqual(
            supply_ids,
            {
                supplies[1].supply_id,
                supplies[2].supply_id,
                old_supply.pk,
            },
        )
        self.assertEqual(
            shipment_ids,
            {
                shipments[1].shipment_id,
                shipments[2].shipment_id,
                old_shipment.pk,
            },
        )

    def test_load_makes_constant_number_of_queries(self):
        part = make_spare_part()
        make_supply(part, TODAY, 2)
        make_supply(part, TODAY, 1, archive=True)
        make_part_shipment(part, TODAY, 1)
        make_part_shipment(part, TODAY, 1, archive=True)

        with CaptureQueriesContext(connection) as queries:
            sp.SparePartSet.load()

        self.assertEqual(len(queries.captured_queries), 7)


def period_month_edges(period):
    return [period.date_from, period.date_to]


class SparePartSetFilterTests(TestCase):
    def test_parts_of_spare_part_and_compatible_equipment(self):
        equipment = make_equipment()
        first = make_spare_part(name="Первая", equipment=[equipment])
        second = make_spare_part(name="Вторая")
        source = sp.SparePartSet.load()

        self.assertEqual(
            sp.parts_of(SparePartFilters(spare_part=second), TODAY, source),
            [second],
        )
        self.assertEqual(
            sp.parts_of(SparePartFilters(equipment=equipment), TODAY, source),
            [first],
        )

    def test_parts_of_stock_states(self):
        positive = make_spare_part(name="Положительный")
        make_stock(positive, 5)
        make_stock(positive, -2, date(2027, 1, 1))
        zero = make_spare_part(name="Нулевой")
        explicit_zero = make_spare_part(name="Явный ноль")
        make_stock(explicit_zero, 0)
        negative = make_spare_part(name="Отрицательный")
        make_stock(negative, -1)
        source = sp.SparePartSet.load()

        for state, expected in (
            ("positive", {positive}),
            ("zero", {zero, explicit_zero}),
            ("negative", {negative}),
        ):
            with self.subTest(state=state):
                self.assertEqual(
                    set(sp.parts_of(SparePartFilters(stock=state), TODAY, source)),
                    expected,
                )

    def test_parts_of_expiration_selects_whole_part(self):
        matching = make_spare_part(name="Подходит")
        make_stock(matching, 2, TODAY + timedelta(days=10))
        make_stock(matching, 3, TODAY + timedelta(days=200))
        expired = make_spare_part(name="Просрочено")
        make_stock(expired, 1, TODAY - timedelta(days=1))
        zero = make_spare_part(name="Нулевой в окне")
        make_stock(zero, 0, TODAY + timedelta(days=10))
        source = sp.SparePartSet.load()

        selected = sp.parts_of(SparePartFilters(expiration="30"), TODAY, source)

        self.assertEqual(selected, [matching])

    def test_parts_of_nonmoving_boundaries(self):
        recent = make_spare_part(name="Недавняя")
        old = make_spare_part(name="Старая")
        never = make_spare_part(name="Без отгрузок")
        empty = make_spare_part(name="Пустая")
        for part in (recent, old, never):
            make_stock(part, 1)
        make_part_shipment(recent, TODAY - timedelta(days=179), 1)
        make_part_shipment(old, TODAY - timedelta(days=180), 1)
        make_stock(recent, 1)
        make_stock(old, 1)
        source = sp.SparePartSet.load()

        selected = sp.parts_of(SparePartFilters(nonmoving="180"), TODAY, source)

        self.assertEqual(set(selected), {old, never})
        self.assertNotIn(empty, selected)

    def test_parts_of_combines_filters(self):
        equipment = make_equipment()
        matching = make_spare_part(name="Подходит", equipment=[equipment])
        make_stock(matching, 2, TODAY + timedelta(days=10))
        make_part_shipment(matching, TODAY - timedelta(days=180), 1)
        negative = make_spare_part(name="Отрицательная", equipment=[equipment])
        make_stock(negative, -1, TODAY + timedelta(days=10))
        source = sp.SparePartSet.load()
        filters = SparePartFilters(
            equipment=equipment, expiration="30", stock="positive", nonmoving="180"
        )

        self.assertEqual(sp.parts_of(filters, TODAY, source), [matching])


class StockValuationTests(TestCase):
    def test_known_price_weighted_by_expiration_then_part_fallback(self):
        part = make_spare_part()
        expiration = date(2027, 1, 1)
        make_supply(part, TODAY, 5, price=100, expiration_dt=expiration)
        make_supply(part, TODAY, 5, price=200, expiration_dt=expiration)
        make_supply(part, TODAY, 10, price=0, expiration_dt=expiration)
        make_supply(part, TODAY, 0, price=999, expiration_dt=expiration)
        source = sp.SparePartSet.load()

        self.assertEqual(
            sp.known_price(part.pk, expiration, source), Decimal("150.00")
        )
        self.assertEqual(
            sp.known_price(part.pk, date(2028, 1, 1), source), Decimal("150.00")
        )

    def test_stock_value_positive_only(self):
        part = make_spare_part()
        make_supply(part, TODAY, 2, price=100)
        positive = make_stock(part, 3)
        zero = make_stock(part, 0, date(2027, 1, 1))
        negative = make_stock(part, -2, date(2028, 1, 1))
        source = sp.SparePartSet.load()

        self.assertEqual(sp.stock_value(positive, source), Decimal("300.00"))
        self.assertIsNone(sp.stock_value(zero, source))
        self.assertIsNone(sp.stock_value(negative, source))

    def test_overview_kpis_and_price_coverage(self):
        complete = make_spare_part(name="Полная")
        make_supply(complete, TODAY, 1, price=100)
        make_stock(complete, 2)
        unknown = make_spare_part(name="Неизвестная")
        make_stock(unknown, 1)
        partial = make_spare_part(name="Частичная")
        expiration = date(2027, 1, 1)
        make_supply(partial, TODAY, 1, price=50, expiration_dt=expiration)
        make_stock(partial, 1, expiration)
        make_stock(partial, 2, date(2028, 1, 1))
        source = sp.SparePartSet.load()

        kpis = sp.overview_kpis(
            Period(date(2026, 1, 1), date(2026, 12, 31)),
            TODAY,
            SparePartFilters(),
            source,
        )

        self.assertEqual(kpis["positive_count"], 3)
        self.assertEqual(kpis["priced_count"], 2)
        self.assertEqual(kpis["priced_total"], 3)
        self.assertEqual(kpis["stock_value"], Decimal("350.00"))

    def test_overview_money_uses_v2_and_all_shipments(self):
        part = make_spare_part()
        period = Period(date(2026, 2, 1), date(2026, 2, 28))
        make_supply(part, period.date_from, 1, price=100)
        make_supply(part, period.date_to, 2, price=100)
        make_supply(part, period.date_from, 5, price=500, archive=True)
        make_supply(part, date(2026, 3, 1), 10, price=100)
        make_part_shipment(part, period.date_from, 1, price=50)
        make_part_shipment(part, period.date_to, 2, price=100)
        make_part_shipment(part, period.date_to, 5, price=500, archive=True)
        source = sp.SparePartSet.load()

        kpis = sp.overview_kpis(period, TODAY, SparePartFilters(), source)

        self.assertEqual(kpis["purchase_amount"], Decimal("300.00"))
        self.assertEqual(kpis["shipment_cost"], Decimal("250.00"))

    def test_stock_value_does_not_depend_on_period(self):
        part = make_spare_part()
        make_supply(part, date(2020, 1, 1), 1, price=100)
        make_stock(part, 3)
        source = sp.SparePartSet.load()

        first = sp.overview_kpis(
            Period(date(2025, 1, 1), date(2025, 12, 31)),
            TODAY,
            SparePartFilters(),
            source,
        )
        second = sp.overview_kpis(
            Period(date(2026, 1, 1), date(2026, 12, 31)),
            TODAY,
            SparePartFilters(),
            source,
        )

        self.assertEqual(first["stock_value"], second["stock_value"])
        self.assertEqual(first["stock_value"], Decimal("300.00"))


class StockRowsTests(TestCase):
    def test_stock_rows_quantities_demand_and_days(self):
        part = make_spare_part()
        period = Period(date(2026, 2, 1), date(2026, 2, 28))
        make_supply(part, period.date_from, 2)
        make_supply(part, period.date_to, 3, archive=True)
        make_supply(part, date(2026, 3, 1), 10)
        make_part_shipment(part, period.date_from, 4)
        make_part_shipment(part, period.date_to, 2, archive=True)
        make_part_shipment(part, TODAY + timedelta(days=1), 100)
        make_stock(part, 20)
        source = sp.SparePartSet.load()

        (row,) = sp.stock_rows(period, TODAY, SparePartFilters(), source)

        self.assertEqual(row["received"], Decimal("5"))
        self.assertEqual(row["shipped"], Decimal("6"))
        self.assertEqual(row["average_monthly"], Decimal("0.50"))
        self.assertEqual(row["days_stock"], 1217)
        self.assertEqual(row["last_shipment"], period.date_to)
        self.assertTrue(row["nonmoving_180"])
        self.assertFalse(row["nonmoving_365"])

    def test_stock_rows_without_demand_or_with_zero_stock(self):
        empty = make_spare_part(name="Пустая")
        full = make_spare_part(name="Полная")
        make_stock(empty, 0)
        make_stock(full, 2)
        source = sp.SparePartSet.load()

        rows = {
            row["id"]: row
            for row in sp.stock_rows(
                Period(date(2026, 1, 1), date(2026, 12, 31)),
                TODAY,
                SparePartFilters(),
                source,
            )
        }

        self.assertEqual(rows[empty.pk]["average_monthly"], Decimal("0.00"))
        self.assertIsNone(rows[empty.pk]["days_stock"])
        self.assertFalse(rows[empty.pk]["nonmoving_180"])
        self.assertIsNone(rows[full.pk]["days_stock"])
        self.assertTrue(rows[full.pk]["nonmoving_365"])

    def test_stock_rows_partial_price_is_marked(self):
        part = make_spare_part(name="С fallback")
        expiration = date(2027, 1, 1)
        make_supply(part, TODAY, 1, price=50, expiration_dt=expiration)
        make_stock(part, 1, expiration)
        make_stock(part, 2, date(2028, 1, 1))
        unknown = make_spare_part(name="Без цены")
        make_stock(unknown, 2)
        source = sp.SparePartSet.load()

        rows = {
            row["id"]: row
            for row in sp.stock_rows(
                Period(date(2026, 1, 1), date(2026, 12, 31)),
                TODAY,
                SparePartFilters(),
                source,
            )
        }

        # Любая известная поставка даёт fallback для всех сроков этой запчасти.
        self.assertTrue(rows[part.pk]["value_complete"])
        self.assertEqual(rows[part.pk]["stock_value"], Decimal("150.00"))
        self.assertEqual(rows[part.pk]["average_price"], Decimal("50.00"))
        self.assertFalse(rows[unknown.pk]["value_complete"])
        self.assertIsNone(rows[unknown.pk]["stock_value"])

    def test_stock_rows_sorting(self):
        expensive = make_spare_part(name="Дорогая")
        make_supply(expensive, TODAY, 1, price=200)
        make_stock(expensive, 2)
        cheap = make_spare_part(name="Дешёвая")
        make_supply(cheap, TODAY, 1, price=100)
        make_stock(cheap, 1)
        unknown_a = make_spare_part(name="Альфа")
        unknown_b = make_spare_part(name="Бета")
        make_stock(unknown_a, 10)
        make_stock(unknown_b, 10)
        source = sp.SparePartSet.load()

        rows = sp.stock_rows(
            Period(date(2026, 1, 1), date(2026, 12, 31)),
            TODAY,
            SparePartFilters(),
            source,
        )

        self.assertEqual(
            [row["label"] for row in rows],
            ["Дорогая", "Дешёвая", "Альфа", "Бета"],
        )

    def test_stock_rows_respect_selected_parts(self):
        selected = make_spare_part(name="Выбранная")
        make_spare_part(name="Другая")
        source = sp.SparePartSet.load()

        rows = sp.stock_rows(
            Period(date(2026, 1, 1), date(2026, 12, 31)),
            TODAY,
            SparePartFilters(spare_part=selected),
            source,
        )

        self.assertEqual([row["id"] for row in rows], [selected.pk])
