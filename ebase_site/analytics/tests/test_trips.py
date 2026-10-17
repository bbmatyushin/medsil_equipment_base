from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from analytics.filters import Period
from analytics.services.trips import (
    TripSet,
    accountable,
    annual_by_direction,
    clients_trips_vs_payments,
    contract_trip_shares,
    employee_days,
    employee_month_load,
    by_service_type,
    direction_norms,
    directions,
    client_of,
    cost_structure,
    costs_by_month,
    direction_of,
    expensive_trips,
    load_trips,
    merge_candidates,
    repeat_visits,
    unallocated_trips,
    split_proportional,
    trip_shares,
    trip_total,
    trips_in_period,
    trips_kpis,
    trips_until,
)
from analytics.tests.factories import (
    make_city,
    make_client,
    make_contract,
    make_department,
    make_employee,
    make_payment,
    make_receipt,
    make_trip,
)
from business_trip.models import BusinessTrip, MoneyReceipt
from business_trip.xlsx_report import build_money_report

D = Decimal

TODAY = date(2026, 10, 16)
YEAR_2026 = Period(date(2026, 1, 1), date(2026, 12, 31))


def _by_destination(shares):
    """Сумма долей по пункту: {pk пункта или None: Decimal}."""
    result = {}
    for share in shares:
        key = share.destination.pk if share.destination else None
        result[key] = result.get(key, D("0")) + share.amount
    return result


def _loaded(trip):
    """Командировка после load_trips (как её получают функции расчёта)."""
    return load_trips(BusinessTrip.objects.filter(pk=trip.pk))[0]


class AttributionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = make_employee()
        cls.kazan = make_department("Больница Казани")
        cls.samara = make_department(
            "Больница Самары", city=make_city("Самара", "Самарская область")
        )

    def test_split_proportional_kopecks(self):
        self.assertEqual(
            split_proportional(D("100.00"), [1, 2]), [D("33.34"), D("66.66")]
        )
        self.assertEqual(split_proportional(D("0"), [3, 1]), [D("0"), D("0")])

    def test_split_proportional_sum_is_exact(self):
        parts = split_proportional(D("1000.01"), [3, 3, 1])
        self.assertEqual(sum(parts), D("1000.01"))
        self.assertEqual(len(parts), 3)

    def test_single_city_gets_everything(self):
        trip = make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 3),
            destinations=[(self.kazan, date(2026, 3, 1), date(2026, 3, 3))],
            expenses=[
                ("Такси", date(2026, 3, 1), 1000),
                ("Гостиница", date(2026, 3, 2), 500),
            ],
        )
        shares = trip_shares(_loaded(trip))
        expenses = sum(s.amount for s in shares if s.kind != "Суточные")
        allowance = sum(s.amount for s in shares if s.kind == "Суточные")
        self.assertEqual(expenses, D("1500"))
        self.assertEqual(allowance, D("2100"))
        self.assertEqual({s.destination.department_id for s in shares}, {self.kazan.pk})

    def test_expense_goes_to_destination_by_date(self):
        trip = make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 5),
            destinations=[
                (self.kazan, date(2026, 3, 1), date(2026, 3, 2)),
                (self.samara, date(2026, 3, 3), date(2026, 3, 5)),
            ],
            expenses=[("Такси", date(2026, 3, 2), 900)],
        )
        taxi = [s for s in trip_shares(_loaded(trip)) if s.kind == "Такси"]
        self.assertEqual(len(taxi), 1)
        self.assertEqual(taxi[0].destination.department_id, self.kazan.pk)
        self.assertEqual(taxi[0].amount, D("900"))

    def test_overlapping_destinations_pick_earliest(self):
        trip = make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 5),
            destinations=[
                (self.samara, date(2026, 3, 2), date(2026, 3, 5)),
                (self.kazan, date(2026, 3, 1), date(2026, 3, 3)),
            ],
            expenses=[("Такси", date(2026, 3, 2), 900)],
        )
        taxi = [s for s in trip_shares(_loaded(trip)) if s.kind == "Такси"]
        self.assertEqual([s.destination.department_id for s in taxi], [self.kazan.pk])

    def _two_city_trip(self, expenses):
        return make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 5),
            destinations=[
                (self.kazan, date(2026, 3, 1), date(2026, 3, 2)),
                (self.samara, date(2026, 3, 3), date(2026, 3, 5)),
            ],
            expenses=expenses,
        )

    def test_ticket_before_departure_split_by_days(self):
        trip = self._two_city_trip([("Билеты", date(2026, 2, 28), 5000)])
        loaded = _loaded(trip)
        tickets = _by_destination(s for s in trip_shares(loaded) if s.kind == "Билеты")
        kazan, samara = sorted(loaded.destinations.all(), key=lambda d: d.beg_dt)
        self.assertEqual(tickets, {kazan.pk: D("2000"), samara.pk: D("3000")})

    def test_allowance_split_by_days(self):
        trip = self._two_city_trip([])
        loaded = _loaded(trip)
        allowance = _by_destination(
            s for s in trip_shares(loaded) if s.kind == "Суточные"
        )
        kazan, samara = sorted(loaded.destinations.all(), key=lambda d: d.beg_dt)
        self.assertEqual(allowance, {kazan.pk: D("1400"), samara.pk: D("2100")})

    def test_trip_without_destinations(self):
        trip = make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 2),
            expenses=[("Такси", date(2026, 3, 1), 300)],
        )
        shares = trip_shares(_loaded(trip))
        self.assertTrue(shares)
        self.assertTrue(all(s.destination is None for s in shares))
        self.assertEqual(sum(s.amount for s in shares), D("1700"))
        self.assertEqual(direction_of(None, "city"), ("none", "Пункты не указаны"))

    def test_trip_shares_sum_equals_trip_total(self):
        third = make_department(
            "Больница Тольятти", city=make_city("Тольятти", "Самарская область")
        )
        trip = make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 7),
            destinations=[
                (self.kazan, date(2026, 3, 1), date(2026, 3, 2)),
                (self.samara, date(2026, 3, 3), date(2026, 3, 4)),
                (third, date(2026, 3, 5), date(2026, 3, 7)),
            ],
            expenses=[
                ("Билеты", date(2026, 2, 27), D("1000.01")),
                ("Такси", date(2026, 3, 4), D("333.33")),
                ("Прочее", date(2026, 3, 9), D("0.05")),
            ],
        )
        loaded = _loaded(trip)
        self.assertEqual(sum(s.amount for s in trip_shares(loaded)), trip_total(loaded))
        self.assertEqual(trip_total(loaded), D("1333.39") + 7 * 700)

    def test_direction_city_and_region_keys(self):
        chelny = make_department(
            "Больница Челнов", city=make_city("Набережные Челны", "Татарстан")
        )
        trip = make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 4),
            destinations=[
                (self.kazan, date(2026, 3, 1), date(2026, 3, 2)),
                (chelny, date(2026, 3, 3), date(2026, 3, 4)),
            ],
        )
        kazan, chelny_dest = sorted(
            _loaded(trip).destinations.all(), key=lambda d: d.beg_dt
        )
        key, label = direction_of(kazan, "city")
        self.assertEqual(label, "Казань (Татарстан)")
        self.assertTrue(key.startswith("city:"))
        self.assertNotEqual(direction_of(chelny_dest, "city")[0], key)
        self.assertEqual(
            direction_of(kazan, "region"), ("region:Татарстан", "Татарстан")
        )
        self.assertEqual(
            direction_of(chelny_dest, "region"), ("region:Татарстан", "Татарстан")
        )

    def test_direction_city_without_region(self):
        city = make_city("Набережные Челны", None)
        department = make_department("Без региона", city=city)
        trip = make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 1),
            destinations=[(department, date(2026, 3, 1), date(2026, 3, 1))],
        )
        dest = _loaded(trip).destinations.all()[0]
        self.assertEqual(
            direction_of(dest, "region"),
            (f"city:{city.pk}", "Набережные Челны (регион не указан)"),
        )
        self.assertEqual(direction_of(dest, "city")[1], "Набережные Челны")

    def test_direction_department_without_city(self):
        department = make_department("Без города", city=None)
        trip = make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 1),
            destinations=[(department, date(2026, 3, 1), date(2026, 3, 1))],
        )
        dest = _loaded(trip).destinations.all()[0]
        for group in ("city", "region"):
            self.assertEqual(direction_of(dest, group), ("no_city", "Город не указан"))

    def test_client_of_buckets(self):
        alpha = make_client("Альфа")
        with_client = make_department("С клиентом", client=alpha)
        trip = make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 2),
            destinations=[
                (with_client, date(2026, 3, 1), date(2026, 3, 1)),
                (self.kazan, date(2026, 3, 2), date(2026, 3, 2)),
            ],
        )
        first, second = sorted(_loaded(trip).destinations.all(), key=lambda d: d.beg_dt)
        self.assertEqual(client_of(first), (str(alpha.pk), "Альфа"))
        self.assertEqual(client_of(second), ("no_client", "Клиент не указан"))
        self.assertEqual(client_of(None), ("none", "Пункты не указаны"))

    def test_load_trips_makes_no_queries_in_loop(self):
        for day in (1, 10):
            make_trip(
                self.employee,
                date(2026, 3, day),
                date(2026, 3, day + 2),
                destinations=[(self.kazan, date(2026, 3, day), date(2026, 3, day + 2))],
                expenses=[("Такси", date(2026, 3, day), 100)],
            )
        trips = load_trips(BusinessTrip.objects.all())
        with self.assertNumQueries(0):
            for trip in trips:
                for share in trip_shares(trip):
                    direction_of(share.destination, "region")
                    client_of(share.destination)
                trip_total(trip)


class KpiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = make_employee()
        cls.other = make_employee("petrov", "Петров", "Пётр", "Петрович")
        cls.kazan = make_department("Больница Казани")

    def _trip(self, employee, beg, days, expense):
        end = beg + timedelta(days=days - 1)
        return make_trip(
            employee,
            beg,
            end,
            destinations=[(self.kazan, beg, end)],
            expenses=[("Такси", beg, expense)] if expense else [],
        )

    def test_kpis_empty_period(self):
        kpis = trips_kpis(YEAR_2026)
        current = kpis["current"]
        self.assertEqual(current["total"], D("0"))
        self.assertEqual(current["count"], 0)
        self.assertEqual(current["person_days"], 0)
        self.assertIsNone(current["avg_trip"])
        self.assertIsNone(current["avg_day"])
        self.assertTrue(all(value is None for value in kpis["delta_pct"].values()))
        self.assertEqual(
            set(kpis["delta_pct"]),
            {"total", "count", "person_days", "avg_trip", "avg_day"},
        )

    def test_kpis_values_and_delta(self):
        self._trip(self.employee, date(2026, 3, 1), 3, 1000)
        self._trip(self.employee, date(2026, 5, 1), 2, 500)
        self._trip(self.employee, date(2025, 5, 1), 2, 1100)

        kpis = trips_kpis(YEAR_2026)

        current = kpis["current"]
        self.assertEqual(current["total"], D("5000"))
        self.assertEqual(current["count"], 2)
        self.assertEqual(current["person_days"], 5)
        self.assertEqual(current["avg_trip"], D("2500.00"))
        self.assertEqual(current["avg_day"], D("1000.00"))
        self.assertEqual(kpis["previous"]["total"], D("2500"))
        self.assertEqual(kpis["delta_pct"]["total"], D("100.0"))

    def test_kpis_employee_filter(self):
        self._trip(self.employee, date(2026, 3, 1), 3, 1000)
        self._trip(self.other, date(2026, 3, 1), 2, 500)

        current = trips_kpis(YEAR_2026, self.other)["current"]

        self.assertEqual(current["count"], 1)
        self.assertEqual(current["total"], D("1900"))


class MonthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = make_employee()
        cls.kazan = make_department("Больница Казани")

    def test_months_use_trip_start_month(self):
        make_trip(
            self.employee,
            date(2026, 3, 30),
            date(2026, 4, 2),
            destinations=[(self.kazan, date(2026, 3, 30), date(2026, 4, 2))],
            expenses=[("Такси", date(2026, 4, 2), 400)],
        )
        result = costs_by_month(YEAR_2026)
        self.assertEqual(len(result["months"]), 12)
        by_label = {series["label"]: series["data"] for series in result["series"]}
        self.assertEqual(by_label["Такси"][2], D("400"))
        self.assertEqual(by_label["Такси"][3], D("0"))
        self.assertEqual(by_label["Суточные"][2], D("2800"))
        self.assertEqual(result["series"][-1]["label"], "Суточные")

    def test_month_sum_equals_total_tile(self):
        for month in (2, 6, 11):
            make_trip(
                self.employee,
                date(2026, month, 3),
                date(2026, month, 5),
                destinations=[(self.kazan, date(2026, month, 3), date(2026, month, 5))],
                expenses=[
                    ("Такси", date(2026, month, 3), D("123.45")),
                    ("Гостиница", date(2026, month, 4), 3000),
                ],
            )
        result = costs_by_month(YEAR_2026)
        total = sum(sum(series["data"]) for series in result["series"])
        self.assertEqual(total, trips_kpis(YEAR_2026)["current"]["total"])

    def test_month_series_collapse_to_six(self):
        kinds = ["А", "Б", "В", "Г", "Д", "Е", "Ж"]
        make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 1),
            destinations=[(self.kazan, date(2026, 3, 1), date(2026, 3, 1))],
            expenses=[
                (kind, date(2026, 3, 1), (len(kinds) - index) * 100)
                for index, kind in enumerate(kinds)
            ],
        )
        series = costs_by_month(YEAR_2026)["series"]
        self.assertEqual(
            [item["label"] for item in series],
            ["А", "Б", "В", "Г", "Прочие виды", "Суточные"],
        )
        others = next(item for item in series if item["label"] == "Прочие виды")
        self.assertEqual(others["data"][2], D("600"))

    def test_structure_shares(self):
        make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 3),
            destinations=[(self.kazan, date(2026, 3, 1), date(2026, 3, 3))],
            expenses=[
                ("Гостиница", date(2026, 3, 1), 6000),
                ("Такси", date(2026, 3, 2), 900),
            ],
        )
        rows = cost_structure(YEAR_2026)
        self.assertEqual(
            [(row["label"], row["amount"]) for row in rows],
            [("Гостиница", D("6000")), ("Суточные", D("2100")), ("Такси", D("900"))],
        )
        self.assertEqual(rows[0]["share_pct"], D("66.7"))
        self.assertAlmostEqual(
            float(sum(row["share_pct"] for row in rows)), 100.0, delta=0.1
        )


class DirectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = make_employee()
        cls.kazan = make_department("Больница Казани")
        cls.kazan2 = make_department("Поликлиника Казани")
        cls.chelny = make_department(
            "Больница Челнов", city=make_city("Набережные Челны", "Татарстан")
        )
        cls.samara = make_department(
            "Больница Самары", city=make_city("Самара", "Самарская область")
        )

    def test_directions_sum_equals_total(self):
        make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 5),
            destinations=[
                (self.kazan, date(2026, 3, 1), date(2026, 3, 2)),
                (self.samara, date(2026, 3, 3), date(2026, 3, 5)),
            ],
            expenses=[("Билеты", date(2026, 2, 27), D("1000.01"))],
        )
        make_trip(
            self.employee,
            date(2026, 4, 1),
            date(2026, 4, 2),
            expenses=[("Такси", date(2026, 4, 1), 300)],
        )
        rows = directions(YEAR_2026)
        self.assertEqual(
            sum(row["amount"] for row in rows),
            trips_kpis(YEAR_2026)["current"]["total"],
        )
        self.assertIn("Пункты не указаны", [row["label"] for row in rows])
        self.assertEqual(rows[0]["amount"], max(row["amount"] for row in rows))

    def test_directions_count_trip_once_per_direction(self):
        trip = make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 4),
            destinations=[
                (self.kazan, date(2026, 3, 1), date(2026, 3, 2)),
                (self.kazan2, date(2026, 3, 3), date(2026, 3, 4)),
            ],
        )
        rows = directions(YEAR_2026)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["trips"], 1)
        self.assertEqual(rows[0]["days"], 4)
        self.assertEqual(rows[0]["trip_ids"], [str(trip.pk)])

    def test_directions_region_group_merges_cities(self):
        for department, day in ((self.kazan, 1), (self.chelny, 10)):
            make_trip(
                self.employee,
                date(2026, 3, day),
                date(2026, 3, day + 1),
                destinations=[(department, date(2026, 3, day), date(2026, 3, day + 1))],
            )
        self.assertEqual(len(directions(YEAR_2026, group="city")), 2)
        rows = directions(YEAR_2026, group="region")
        self.assertEqual([row["label"] for row in rows], ["Татарстан"])
        self.assertEqual(rows[0]["trips"], 2)
        self.assertEqual(rows[0]["amount"], D("2800"))


class AnnualTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = make_employee()
        cls.other = make_employee("petrov", "Петров", "Пётр", "Петрович")
        cls.kazan = make_department("Больница Казани")

    def _one_day_trip(self, employee, day, total):
        return make_trip(
            employee,
            day,
            day,
            destinations=[(self.kazan, day, day)],
            expenses=[("Такси", day, D(total) - 700)],
        )

    def test_annual_window_estimate(self):
        start = TODAY - timedelta(days=99)
        self._one_day_trip(self.employee, start, 10000)

        annual = annual_by_direction(TODAY)

        self.assertEqual(annual["start"], start)
        self.assertEqual(annual["window_days"], 100)
        self.assertTrue(annual["is_estimate"])
        self.assertEqual(annual["months"], 3)
        self.assertEqual(annual["years"], [2026])
        row = annual["rows"][0]
        self.assertEqual(row["label"], "Казань (Татарстан)")
        self.assertEqual(row["total"], D("10000"))
        self.assertEqual(row["per_year"], D("36500.00"))
        self.assertEqual(row["trips_per_year"], D("3.7"))
        self.assertEqual(row["by_year"], [D("10000")])

    def test_annual_by_year_columns(self):
        self._one_day_trip(self.employee, date(2025, 6, 1), 1000)
        self._one_day_trip(self.employee, date(2026, 6, 1), 3000)

        annual = annual_by_direction(TODAY)

        self.assertEqual(annual["years"], [2025, 2026])
        self.assertFalse(annual["is_estimate"])
        row = annual["rows"][0]
        self.assertEqual(row["by_year"], [D("1000"), D("3000")])
        self.assertEqual(row["total"], D("4000"))

    def test_annual_window_ignores_employee_filter(self):
        earliest = date(2026, 1, 1)
        self._one_day_trip(self.other, earliest, 1000)
        self._one_day_trip(self.employee, date(2026, 9, 1), 2000)

        annual = annual_by_direction(TODAY, self.employee)

        self.assertEqual(annual["start"], earliest)
        self.assertEqual(annual["rows"][0]["total"], D("2000"))

    def test_annual_ignores_future_trips(self):
        self._one_day_trip(self.employee, date(2026, 9, 1), 2000)
        self._one_day_trip(self.employee, TODAY + timedelta(days=1), 5000)
        make_trip(self.other, date(2026, 12, 1), date(2026, 12, 3))

        annual = annual_by_direction(TODAY)

        self.assertEqual(annual["start"], date(2026, 9, 1))
        self.assertEqual(sum(row["total"] for row in annual["rows"]), D("2000"))

    def test_annual_empty(self):
        annual = annual_by_direction(TODAY)
        self.assertIsNone(annual["start"])
        self.assertEqual(annual["rows"], [])
        self.assertEqual(annual["years"], [])


class NormsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = make_employee()
        cls.kazan = make_department("Больница Казани")

    def test_norms_per_day_by_kind(self):
        make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 2),
            destinations=[(self.kazan, date(2026, 3, 1), date(2026, 3, 2))],
            expenses=[("Гостиница", date(2026, 3, 1), 4000)],
        )
        make_trip(
            self.employee,
            date(2026, 4, 1),
            date(2026, 4, 3),
            destinations=[(self.kazan, date(2026, 4, 1), date(2026, 4, 3))],
            expenses=[
                ("Гостиница", date(2026, 4, 1), 6000),
                ("Такси", date(2026, 4, 2), D("100.01")),
            ],
        )

        norms = direction_norms(TODAY)

        self.assertEqual(norms["kinds"], ["Гостиница", "Такси", "Суточные"])
        row = norms["rows"][0]
        self.assertEqual(row["trips"], 2)
        self.assertEqual(row["avg_days"], D("2.5"))
        hotel = row["per_day_by_kind"][norms["kinds"].index("Гостиница")]
        self.assertEqual(hotel, D("2000.00"))
        self.assertEqual(row["per_day_by_kind"][-1], D("700.00"))
        self.assertAlmostEqual(
            float(sum(row["per_day_by_kind"])), float(row["per_day"]), delta=0.011
        )
        self.assertEqual(row["avg_trip"], D("6800.01"))

    def test_norms_skip_trips_without_destinations(self):
        make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 2),
            expenses=[("Такси", date(2026, 3, 1), 300)],
        )
        self.assertEqual(direction_norms(TODAY)["rows"], [])


class ServiceTypeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = make_employee()
        cls.kazan = make_department("Больница Казани")

    def test_service_type_counts_trip_in_each_type(self):
        make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 2),
            destinations=[(self.kazan, date(2026, 3, 1), date(2026, 3, 2))],
            expenses=[("Такси", date(2026, 3, 1), 4600)],
            service_types=["ТО", "ремонт"],
        )
        make_trip(self.employee, date(2026, 5, 1), date(2026, 5, 1))

        rows = {row["label"]: row for row in by_service_type(YEAR_2026)}

        for name in ("ТО", "ремонт"):
            self.assertEqual(rows[name]["trips"], 1)
            self.assertEqual(rows[name]["avg_trip"], D("6000.00"))
            self.assertEqual(rows[name]["avg_days"], D("2.0"))
            self.assertEqual(rows[name]["per_day"], D("3000.00"))
            self.assertIsNotNone(rows[name]["id"])
        self.assertIsNone(rows["Вид работ не указан"]["id"])
        self.assertEqual(rows["Вид работ не указан"]["avg_trip"], D("700.00"))


class EmployeeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = make_employee()
        cls.kazan = make_department("Больница Казани")

    def test_employee_days(self):
        for day in (1, 10):
            make_trip(
                self.employee,
                date(2026, 3, day),
                date(2026, 3, day + 2),
                destinations=[(self.kazan, date(2026, 3, day), date(2026, 3, day + 2))],
            )
        rows = employee_days(YEAR_2026)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["name"], "Иванов Иван Иванович")
        self.assertEqual((row["trips"], row["days"]), (2, 6))
        self.assertEqual(row["amount"], D("4200"))
        self.assertEqual(row["per_day"], D("700.00"))

    def test_month_load_splits_and_clips(self):
        make_trip(self.employee, date(2026, 3, 29), date(2026, 4, 2))
        make_trip(self.employee, date(2026, 2, 27), date(2026, 3, 1))

        load = employee_month_load(YEAR_2026)
        row = load["rows"][0]
        self.assertEqual(row["days"][1], 2)  # февраль: 27–28
        self.assertEqual(row["days"][2], 4)  # март: 1, 29–31
        self.assertEqual(row["days"][3], 2)  # апрель: 1–2
        self.assertEqual(row["total"], 8)
        self.assertEqual(load["max"], 4)

        march = employee_month_load(Period(date(2026, 3, 1), date(2026, 3, 31)))
        self.assertEqual(march["rows"][0]["days"], [4])

    def test_month_load_empty(self):
        load = employee_month_load(YEAR_2026)
        self.assertEqual(load["rows"], [])
        self.assertEqual(load["max"], 0)


class AccountableTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = make_employee()
        cls.kazan = make_department("Больница Казани")

    def _trip(self, beg, days, expenses):
        end = beg + timedelta(days=days - 1)
        return make_trip(
            self.employee,
            beg,
            end,
            destinations=[(self.kazan, beg, end)],
            expenses=[(kind, beg, amount) for kind, amount in expenses],
        )

    def test_accountable_user_example(self):
        make_receipt(self.employee, date(2026, 3, 1), 10000)
        self._trip(date(2026, 3, 2), 3, [("Гостиница", 4000), ("Такси", 2000)])

        row = accountable(YEAR_2026, TODAY)[0]

        self.assertEqual(row["received"], D("10000"))
        self.assertEqual(row["spent"], D("8100"))
        self.assertEqual(row["diff"], D("1900"))
        self.assertEqual(row["balance"], D("1900"))
        self.assertEqual(row["name"], "Иванов Иван Иванович")

    def test_accountable_excludes_yandex_trips(self):
        self._trip(date(2026, 3, 2), 1, [("Я.командировки", 5000), ("Такси", 300)])

        row = accountable(YEAR_2026, TODAY)[0]

        self.assertEqual(row["spent"], D("1000"))
        self.assertEqual(row["balance"], D("-1000"))

    def test_balance_is_cumulative(self):
        make_receipt(self.employee, date(2025, 12, 1), 5000)
        self._trip(date(2025, 12, 2), 1, [("Такси", 300)])
        make_receipt(self.employee, date(2026, 2, 1), 2000)

        row = accountable(YEAR_2026, TODAY)[0]

        self.assertEqual(row["received"], D("2000"))
        self.assertEqual(row["spent"], D("0"))
        self.assertEqual(row["balance"], D("6000"))

    def test_balance_ignores_future_trips(self):
        make_receipt(self.employee, date(2026, 3, 1), 5000)
        self._trip(TODAY + timedelta(days=10), 2, [("Такси", 100)])

        row = accountable(YEAR_2026, TODAY)[0]

        self.assertEqual(row["spent"], D("1500"))
        self.assertEqual(row["balance"], D("5000"))

    def test_accountable_skips_empty_rows(self):
        make_employee("petrov", "Петров", "Пётр", "Петрович")
        self.assertEqual(accountable(YEAR_2026, TODAY), [])

    def test_accountable_matches_money_report(self):
        make_receipt(self.employee, date(2026, 3, 1), 7000)
        make_receipt(self.employee, date(2026, 3, 15), D("1234.56"))
        self._trip(date(2026, 3, 2), 2, [("Гостиница", 3000), ("Я.командировки", 9000)])
        self._trip(date(2026, 3, 20), 1, [("Такси", D("456.78"))])
        march = Period(date(2026, 3, 1), date(2026, 3, 31))

        trips = BusinessTrip.objects.filter(
            employee=self.employee, beg_dt__range=(march.date_from, march.date_to)
        ).prefetch_related("destinations__department__city", "expenses__expense_type")
        receipts = MoneyReceipt.objects.filter(
            employee=self.employee,
            receipt_date__range=(march.date_from, march.date_to),
        )
        ws = build_money_report(self.employee, 2026, 3, trips, receipts).active

        def numbers(column, first, last):
            values = (ws[f"{column}{row}"].value for row in range(first, last + 1))
            return sum(
                (D(str(v)) for v in values if isinstance(v, (int, float, D))), D("0")
            )

        row = accountable(march, TODAY)[0]
        self.assertEqual(numbers("D", 7, 18), row["received"])
        self.assertEqual(numbers("G", 7, 44) + numbers("D", 24, 34), row["spent"])
        self.assertEqual(row["spent"], D("3000") + D("456.78") + 3 * 700)


class MoneyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = make_employee()
        cls.alpha = make_client("Альфа")
        cls.alpha_dept = make_department("Больница Альфы", client=cls.alpha)
        cls.contract = make_contract(cls.alpha, "К-1", date(2026, 1, 10), 100000)

    def _trip(self, beg, days, expense, contracts=(), department=None):
        end = beg + timedelta(days=days - 1)
        return make_trip(
            self.employee,
            beg,
            end,
            destinations=[(department or self.alpha_dept, beg, end)],
            expenses=[("Такси", beg, expense)],
            contracts=contracts,
        )

    def test_contract_share_pct(self):
        self._trip(date(2026, 3, 1), 3, 3000, contracts=[self.contract])

        rows = contract_trip_shares(YEAR_2026)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], self.contract.pk)
        self.assertEqual(row["number"], "К-1")
        self.assertEqual(row["client"], "Альфа")
        self.assertEqual(row["contract_amount"], D("100000"))
        self.assertEqual(row["trips_amount"], D("5100"))
        self.assertEqual(row["share_pct"], D("5.1"))

    def test_contract_trips_amount_includes_all_trips(self):
        self._trip(date(2025, 12, 1), 1, 300, contracts=[self.contract])
        self._trip(date(2026, 3, 1), 3, 3000, contracts=[self.contract])
        other = make_contract(self.alpha, "К-2", date(2025, 1, 10), 50000)
        self._trip(date(2025, 6, 1), 1, 300, contracts=[other])

        rows = contract_trip_shares(YEAR_2026)

        self.assertEqual([row["number"] for row in rows], ["К-1"])
        self.assertEqual(rows[0]["trips_amount"], D("6100"))

    def test_clients_per_100(self):
        make_payment(self.contract, date(2026, 2, 1), 100000)
        make_payment(self.contract, date(2025, 2, 1), 7777)
        self._trip(date(2026, 3, 1), 2, 3600)

        rows = clients_trips_vs_payments(YEAR_2026)

        row = next(row for row in rows if row["name"] == "Альфа")
        self.assertEqual(row["trips_amount"], D("5000"))
        self.assertEqual(row["payments"], D("100000"))
        self.assertEqual(row["per_100"], D("5.00"))

    def test_clients_without_payments(self):
        self._trip(date(2026, 3, 1), 2, 3600)
        self._trip(date(2026, 4, 1), 1, 100, department=make_department("Ничья"))

        rows = {row["name"]: row for row in clients_trips_vs_payments(YEAR_2026)}

        self.assertEqual(rows["Альфа"]["payments"], D("0"))
        self.assertIsNone(rows["Альфа"]["per_100"])
        self.assertIsNone(rows["Клиент не указан"]["payments"])
        self.assertIsNone(rows["Клиент не указан"]["per_100"])

    def test_unallocated_trips(self):
        bare = self._trip(date(2026, 3, 1), 1, 300)
        beta_contract = make_contract(
            make_client("Бета"), "Б-1", date(2026, 1, 1), 1000
        )
        mismatched = self._trip(date(2026, 4, 1), 1, 500, contracts=[beta_contract])
        self._trip(date(2026, 5, 1), 1, 100, contracts=[self.contract])

        result = unallocated_trips(YEAR_2026)

        rows = {row["id"]: row for row in result["rows"]}
        self.assertEqual(set(rows), {bare.pk, mismatched.pk})
        self.assertFalse(rows[bare.pk]["has_contracts"])
        self.assertTrue(rows[mismatched.pk]["has_contracts"])
        self.assertEqual(rows[bare.pk]["employee"], "Иванов Иван Иванович")
        self.assertEqual(result["total"], D("1000") + D("1200"))
        self.assertEqual(set(result["ids"]), {str(bare.pk), str(mismatched.pk)})


class ControlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = make_employee()
        cls.other = make_employee("petrov", "Петров", "Пётр", "Петрович")
        cls.alpha = make_client("Альфа")
        cls.kazan = make_department("Больница Казани", client=cls.alpha)
        cls.chelny = make_department(
            "Больница Челнов", city=make_city("Набережные Челны", "Татарстан")
        )
        cls.samara = make_department(
            "Больница Самары", city=make_city("Самара", "Самарская область")
        )

    def _trip(self, department, beg, end, expense=0, employee=None, **kwargs):
        return make_trip(
            employee or self.employee,
            beg,
            end,
            destinations=[(department, beg, end)],
            expenses=[("Такси", beg, expense)] if expense else [],
            **kwargs,
        )

    def test_repeat_visit_within_30_days(self):
        first = self._trip(self.kazan, date(2026, 2, 27), date(2026, 3, 1))
        second = self._trip(
            self.kazan,
            date(2026, 3, 31),
            date(2026, 4, 1),
            employee=self.other,
            service_types=["ремонт"],
        )

        rows = repeat_visits(YEAR_2026)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["gap"], 30)
        self.assertEqual(row["trip_id"], second.pk)
        self.assertEqual(row["previous_trip_id"], first.pk)
        self.assertEqual(row["department"], "Больница Казани")
        self.assertEqual(row["client"], "Альфа")
        self.assertEqual(row["city"], "Казань")
        self.assertEqual(row["service_types"], "ремонт")
        self.assertEqual(row["amount"], D("1400"))

    def test_repeat_visit_31_days_is_not_repeat(self):
        self._trip(self.kazan, date(2026, 2, 27), date(2026, 3, 1))
        self._trip(self.kazan, date(2026, 4, 1), date(2026, 4, 2))
        self.assertEqual(repeat_visits(YEAR_2026), [])

    def test_repeat_ignores_same_trip(self):
        make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 5),
            destinations=[
                (self.kazan, date(2026, 3, 1), date(2026, 3, 1)),
                (self.chelny, date(2026, 3, 2), date(2026, 3, 3)),
                (self.kazan, date(2026, 3, 5), date(2026, 3, 5)),
            ],
        )
        self.assertEqual(repeat_visits(YEAR_2026), [])

    def test_repeat_previous_may_be_before_period(self):
        self._trip(self.kazan, date(2025, 12, 18), date(2025, 12, 20))
        self._trip(self.kazan, date(2026, 1, 10), date(2026, 1, 11))

        rows = repeat_visits(YEAR_2026)

        self.assertEqual([row["gap"] for row in rows], [21])
        self.assertEqual(rows[0]["previous_end"], date(2025, 12, 20))

    def test_merge_candidates_gap(self):
        first = self._trip(self.kazan, date(2026, 3, 1), date(2026, 3, 1))
        second = self._trip(
            self.chelny, date(2026, 3, 15), date(2026, 3, 16), employee=self.other
        )

        rows = merge_candidates(YEAR_2026)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["gap"], 14)
        self.assertEqual(row["region"], "Татарстан")
        self.assertEqual(row["first"]["id"], first.pk)
        self.assertEqual(row["second"]["id"], second.pk)
        self.assertEqual(row["second"]["employee"], "Петров Пётр Петрович")
        self.assertEqual(row["amount"], D("700") + D("1400"))

    def test_merge_candidates_15_days_overlap_and_other_region(self):
        self._trip(self.kazan, date(2026, 3, 1), date(2026, 3, 1))
        self._trip(self.chelny, date(2026, 3, 16), date(2026, 3, 17))
        self._trip(self.kazan, date(2026, 5, 1), date(2026, 5, 5))
        self._trip(self.chelny, date(2026, 5, 3), date(2026, 5, 4), employee=self.other)
        self._trip(self.samara, date(2026, 7, 1), date(2026, 7, 1))
        self._trip(self.kazan, date(2026, 7, 3), date(2026, 7, 3))

        self.assertEqual(merge_candidates(YEAR_2026), [])

    def _region_baseline(self):
        for day in (1, 5, 9):
            self._trip(self.chelny, date(2026, 2, day), date(2026, 2, day), 1000)

    def test_expensive_trip_against_region_median(self):
        self._region_baseline()
        expensive = self._trip(self.kazan, date(2026, 6, 1), date(2026, 6, 1), 2000)
        self._trip(self.kazan, date(2026, 6, 10), date(2026, 6, 10), 1400)

        rows = expensive_trips(YEAR_2026, TODAY)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], expensive.pk)
        self.assertEqual(row["ratio"], D("2.0"))
        self.assertEqual(row["baseline_kind"], "region")
        self.assertEqual(row["baseline"], D("1000.00"))
        self.assertEqual(row["per_day"], D("2000.00"))
        self.assertEqual(row["region"], "Татарстан")

    def test_expensive_trip_falls_back_to_overall_median(self):
        self._region_baseline()
        self._trip(self.samara, date(2026, 6, 1), date(2026, 6, 1), 3000)

        rows = expensive_trips(YEAR_2026, TODAY)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["baseline_kind"], "all")
        self.assertEqual(rows[0]["ratio"], D("3.0"))

    def test_expensive_per_day_excludes_allowance(self):
        self._region_baseline()
        self._trip(self.kazan, date(2026, 6, 1), date(2026, 6, 2), 4000)

        row = expensive_trips(YEAR_2026, TODAY)[0]

        self.assertEqual(row["per_day"], D("2000.00"))


class ReviewFixTests(TestCase):
    """Исправления по итогам ревью ветки."""

    @classmethod
    def setUpTestData(cls):
        cls.employee = make_employee()
        cls.kazan = make_department("Больница Казани")
        cls.kazan2 = make_department("Поликлиника Казани")
        cls.chelny = make_department(
            "Больница Челнов", city=make_city("Набережные Челны", "Татарстан")
        )

    def test_norms_count_overlapping_destinations_once(self):
        make_trip(
            self.employee,
            date(2026, 3, 10),
            date(2026, 3, 12),
            destinations=[
                (self.kazan, date(2026, 3, 10), date(2026, 3, 12)),
                (self.kazan2, date(2026, 3, 10), date(2026, 3, 12)),
            ],
            expenses=[("Гостиница", date(2026, 3, 10), 3000)],
        )
        row = direction_norms(TODAY)["rows"][0]
        self.assertEqual(row["avg_days"], D("3.0"))
        self.assertEqual(row["per_day"], D("1700.00"))
        self.assertEqual(directions(YEAR_2026)[0]["days"], 3)

    def test_expensive_ignores_trips_without_expenses_in_baseline(self):
        # поездок без затрат больше половины: с ними медиана была бы нулевой
        for day in (1, 3, 5, 7, 9):
            make_trip(
                self.employee,
                date(2026, 2, day),
                date(2026, 2, day),
                destinations=[(self.chelny, date(2026, 2, day), date(2026, 2, day))],
            )
        for day in (12, 16, 20):
            make_trip(
                self.employee,
                date(2026, 2, day),
                date(2026, 2, day),
                destinations=[(self.chelny, date(2026, 2, day), date(2026, 2, day))],
                expenses=[("Такси", date(2026, 2, day), 1000)],
            )
        make_trip(
            self.employee,
            date(2026, 6, 1),
            date(2026, 6, 1),
            destinations=[(self.kazan, date(2026, 6, 1), date(2026, 6, 1))],
            expenses=[("Такси", date(2026, 6, 1), 3000)],
        )
        rows = expensive_trips(YEAR_2026, TODAY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["baseline"], D("1000.00"))
        self.assertEqual(rows[0]["ratio"], D("3.0"))

    def test_destination_with_inverted_dates_does_not_crash(self):
        trip = make_trip(
            self.employee,
            date(2026, 3, 1),
            date(2026, 3, 2),
            destinations=[(self.kazan, date(2026, 3, 2), date(2026, 3, 1))],
            expenses=[("Такси", date(2026, 2, 28), 500)],
        )
        loaded = _loaded(trip)
        self.assertEqual(sum(s.amount for s in trip_shares(loaded)), trip_total(loaded))
        self.assertEqual(direction_norms(TODAY)["rows"][0]["trips"], 1)

    def _one_day(self, department, day, expense):
        return make_trip(
            self.employee,
            day,
            day,
            destinations=[(department, day, day)],
            expenses=[("Такси", day, expense)],
        )

    def test_expensive_threshold_uses_unrounded_ratio(self):
        for day in (1, 5, 9):
            self._one_day(self.chelny, date(2026, 2, day), 1000)
        # 1,45 при округлении до десятых дало бы 1,5 и попало бы в список
        self._one_day(self.chelny, date(2026, 6, 1), 1450)
        self.assertEqual(expensive_trips(YEAR_2026, TODAY), [])

    def test_expensive_trips_without_city_use_overall_median(self):
        no_city = make_department("Без города", city=None)
        for day in (1, 5, 9):
            self._one_day(no_city, date(2025, 2, day), 3000)
        for day in (1, 5, 9, 13):
            self._one_day(self.chelny, date(2025, 3, day), 1000)
        candidate = self._one_day(no_city, date(2026, 6, 1), 3000)

        rows = expensive_trips(YEAR_2026, TODAY)

        self.assertEqual([row["id"] for row in rows], [candidate.pk])
        self.assertEqual(rows[0]["baseline_kind"], "all")
        self.assertEqual(rows[0]["baseline"], D("2000.00"))
        self.assertEqual(rows[0]["region"], "Город не указан")

    def test_merge_candidates_limit(self):
        for day in (1, 10, 19):
            self._one_day(self.chelny, date(2026, 3, day), 100)
        self.assertEqual(len(merge_candidates(YEAR_2026)), 2)
        rows = merge_candidates(YEAR_2026, limit=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["first"]["beg"], date(2026, 3, 1))


class TripSetTests(TestCase):
    """Набор командировок, загруженный один раз, отбирает то же, что запросы в БД."""

    @classmethod
    def setUpTestData(cls):
        cls.employee = make_employee()
        cls.other = make_employee("petrov", "Петров", "Пётр", "Петрович")
        for employee, beg, end in [
            (cls.employee, date(2025, 12, 30), date(2026, 1, 2)),  # на стыке
            (cls.employee, date(2026, 1, 1), date(2026, 1, 1)),  # граница
            (cls.other, date(2026, 12, 31), date(2027, 1, 3)),  # граница, будущая
            (cls.other, date(2026, 10, 16), date(2026, 10, 17)),  # «сегодня»
            (cls.employee, date(2026, 10, 17), date(2026, 10, 18)),  # завтра
            (cls.other, date(2025, 6, 1), date(2025, 6, 2)),
        ]:
            make_trip(employee, beg, end)

    @staticmethod
    def _ids(trips):
        return sorted(str(trip.pk) for trip in trips)

    def test_filters_match_database_queries(self):
        source = TripSet.load()
        for employee in (None, self.employee, self.other):
            with self.subTest(employee=employee):
                self.assertEqual(
                    self._ids(source.in_period(YEAR_2026, employee)),
                    self._ids(trips_in_period(YEAR_2026, employee)),
                )
                self.assertEqual(
                    self._ids(source.until(TODAY, employee)),
                    self._ids(trips_until(TODAY, employee)),
                )
                overlapping = BusinessTrip.objects.filter(
                    beg_dt__lte=YEAR_2026.date_to, end_dt__gte=YEAR_2026.date_from
                )
                if employee is not None:
                    overlapping = overlapping.filter(employee=employee)
                self.assertEqual(
                    self._ids(source.overlapping(YEAR_2026, employee)),
                    self._ids(overlapping),
                )

    def test_first_start_ignores_future_trips(self):
        source = TripSet.load()
        self.assertEqual(source.first_start(TODAY), date(2025, 6, 1))
        self.assertIsNone(TripSet([]).first_start(TODAY))

    def test_load_makes_no_queries_after_loading(self):
        source = TripSet.load()
        with self.assertNumQueries(0):
            for trip in source.in_period(YEAR_2026):
                trip_shares(trip)
                list(trip.service_type.all())
                list(trip.contract.all())
