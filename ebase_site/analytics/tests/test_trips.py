from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from analytics.services.trips import (
    load_trips,
    client_of,
    direction_of,
    split_proportional,
    trip_shares,
    trip_total,
)
from analytics.tests.factories import (
    make_city,
    make_client,
    make_department,
    make_employee,
    make_trip,
)
from business_trip.models import BusinessTrip

D = Decimal


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
