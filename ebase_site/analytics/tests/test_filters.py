from datetime import date

from django.test import SimpleTestCase, TestCase

from clients.models import Client
from contracts.models import Contract
from directory.models import City
from analytics.filters import (
    FinanceFilterForm,
    Period,
    PeriodForm,
    month_label,
    shift_year,
)

TODAY = date(2026, 10, 16)
YEAR_2026 = Period(date(2026, 1, 1), date(2026, 12, 31))


class PeriodFormTests(SimpleTestCase):
    def test_default_is_current_year(self):
        self.assertEqual(PeriodForm(data={}).get_period(TODAY), YEAR_2026)

    def test_year_preset(self):
        self.assertEqual(
            PeriodForm(data={"preset": "year"}).get_period(TODAY), YEAR_2026
        )

    def test_presets(self):
        cases = {
            "prev_year": Period(date(2025, 1, 1), date(2025, 12, 31)),
            "quarter": Period(date(2026, 10, 1), date(2026, 12, 31)),
            "month": Period(date(2026, 10, 1), date(2026, 10, 31)),
        }
        for preset, expected in cases.items():
            with self.subTest(preset=preset):
                self.assertEqual(
                    PeriodForm(data={"preset": preset}).get_period(TODAY), expected
                )

    def test_quarter_and_month_edges(self):
        cases = [
            (date(2026, 1, 1), "quarter", Period(date(2026, 1, 1), date(2026, 3, 31))),
            (date(2026, 6, 30), "quarter", Period(date(2026, 4, 1), date(2026, 6, 30))),
            (
                date(2026, 12, 31),
                "month",
                Period(date(2026, 12, 1), date(2026, 12, 31)),
            ),
            (date(2024, 2, 10), "month", Period(date(2024, 2, 1), date(2024, 2, 29))),
        ]
        for today, preset, expected in cases:
            with self.subTest(today=today, preset=preset):
                self.assertEqual(
                    PeriodForm(data={"preset": preset}).get_period(today), expected
                )

    def test_custom_range(self):
        form = PeriodForm(
            data={
                "preset": "custom",
                "date_from": "2026-02-01",
                "date_to": "2026-03-15",
            }
        )
        self.assertEqual(
            form.get_period(TODAY), Period(date(2026, 2, 1), date(2026, 3, 15))
        )

    def test_custom_without_dates_falls_back_to_year(self):
        cases = [
            {"preset": "custom"},
            {"preset": "custom", "date_from": "2026-02-01"},
            {"preset": "custom", "date_to": "2026-03-15"},
        ]
        for data in cases:
            with self.subTest(data=data):
                self.assertEqual(PeriodForm(data=data).get_period(TODAY), YEAR_2026)

    def test_dates_ignored_for_non_custom_preset(self):
        form = PeriodForm(
            data={
                "preset": "month",
                "date_from": "2026-02-01",
                "date_to": "2026-03-15",
            }
        )
        self.assertEqual(
            form.get_period(TODAY), Period(date(2026, 10, 1), date(2026, 10, 31))
        )

    def test_invalid_preset_falls_back_to_year(self):
        self.assertEqual(
            PeriodForm(data={"preset": "zzz"}).get_period(TODAY), YEAR_2026
        )

    def test_invalid_dates_fall_back_to_year(self):
        form = PeriodForm(
            data={"preset": "custom", "date_from": "abc", "date_to": "2026-03-15"}
        )
        self.assertEqual(form.get_period(TODAY), YEAR_2026)

    def test_invalid_reversed_range_is_swapped(self):
        form = PeriodForm(
            data={
                "preset": "custom",
                "date_from": "2026-05-01",
                "date_to": "2026-03-01",
            }
        )
        self.assertEqual(
            form.get_period(TODAY), Period(date(2026, 3, 1), date(2026, 5, 1))
        )

    def test_get_period_is_repeatable(self):
        # get_period не требует предварительного is_valid() и безопасен при повторе
        form = PeriodForm(data={"preset": "prev_year"})
        self.assertEqual(
            form.get_period(TODAY), Period(date(2025, 1, 1), date(2025, 12, 31))
        )
        self.assertEqual(
            form.get_period(TODAY), Period(date(2025, 1, 1), date(2025, 12, 31))
        )


class PeriodTests(SimpleTestCase):
    def test_previous_year_leap_day(self):
        self.assertEqual(
            Period(date(2024, 2, 1), date(2024, 2, 29)).previous_year(),
            Period(date(2023, 2, 1), date(2023, 2, 28)),
        )

    def test_previous_year_regular(self):
        self.assertEqual(
            YEAR_2026.previous_year(), Period(date(2025, 1, 1), date(2025, 12, 31))
        )

    def test_shift_year(self):
        self.assertEqual(shift_year(date(2024, 2, 29), -1), date(2023, 2, 28))
        self.assertEqual(shift_year(date(2024, 2, 29), 4), date(2028, 2, 29))
        self.assertEqual(shift_year(date(2026, 10, 16), -1), date(2025, 10, 16))

    def test_months(self):
        self.assertEqual(
            Period(date(2026, 1, 15), date(2026, 3, 2)).months(),
            [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)],
        )

    def test_months_across_years(self):
        self.assertEqual(
            Period(date(2025, 11, 30), date(2026, 2, 1)).months(),
            [date(2025, 11, 1), date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)],
        )

    def test_months_single_day(self):
        self.assertEqual(
            Period(date(2026, 5, 20), date(2026, 5, 20)).months(), [date(2026, 5, 1)]
        )

    def test_month_label(self):
        self.assertEqual(month_label(date(2026, 1, 1)), "янв 2026")
        self.assertEqual(month_label(date(2025, 12, 15)), "дек 2025")


class FinanceFilterFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        city, _ = City.objects.get_or_create(name="Москва", region=None)
        cls.with_contract = Client.objects.create(
            name="Клиент с контрактом", city=city, inn="123456789001"
        )
        cls.without_contract = Client.objects.create(
            name="Клиент без контракта", city=city, inn="123456789002"
        )
        Contract.objects.create(
            client=cls.with_contract,
            contract_number="CNT-001",
            conclusion_date="2026-01-15",
            contract_amount=100000,
        )

    def test_invalid_client_is_ignored(self):
        form = FinanceFilterForm(data={"client": "not-a-uuid"})
        self.assertIsNone(form.get_client())
        self.assertEqual(form.get_period(TODAY), YEAR_2026)

    def test_client_with_contract_is_returned(self):
        form = FinanceFilterForm(data={"client": str(self.with_contract.pk)})
        self.assertEqual(form.get_client(), self.with_contract)

    def test_client_without_contract_is_ignored(self):
        form = FinanceFilterForm(data={"client": str(self.without_contract.pk)})
        self.assertIsNone(form.get_client())

    def test_no_client_param(self):
        self.assertIsNone(FinanceFilterForm(data={}).get_client())

    def test_bad_client_does_not_break_period(self):
        form = FinanceFilterForm(
            data={
                "client": "not-a-uuid",
                "preset": "custom",
                "date_from": "2026-02-01",
                "date_to": "2026-03-15",
            }
        )
        self.assertIsNone(form.get_client())
        self.assertEqual(
            form.get_period(TODAY), Period(date(2026, 2, 1), date(2026, 3, 15))
        )

    def test_client_choices_are_sorted_distinct_with_contracts(self):
        city = self.with_contract.city
        second = Client.objects.create(name="Альфа", city=city, inn="123456789003")
        for number in ("CNT-002", "CNT-003"):
            Contract.objects.create(
                client=second,
                contract_number=number,
                conclusion_date="2026-02-01",
                contract_amount=1000,
            )
        queryset = FinanceFilterForm().fields["client"].queryset
        self.assertEqual(list(queryset), [second, self.with_contract])
