from datetime import date

from django.test import SimpleTestCase, TestCase
from django.utils import translation

from clients.models import Client
from contracts.models import Contract
from directory.models import City, Manufacturer, MedDirection
from ebase.models import Equipment
from business_trip.models import BusinessTrip
from users.models import CompanyUser
from analytics.filters import (
    EquipmentFilterForm,
    EquipmentFilters,
    FinanceFilterForm,
    TripsFilterForm,
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

    def test_invalid_extreme_dates_fall_back_to_year(self):
        cases = [
            ("0001-01-01", "9999-12-31"),
            ("1899-12-31", "2026-03-15"),
            ("2026-03-15", "2101-01-01"),
            ("9999-12-31", "0001-01-01"),  # после обмена местами тоже вне границ
        ]
        for date_from, date_to in cases:
            with self.subTest(date_from=date_from, date_to=date_to):
                period = PeriodForm(
                    data={
                        "preset": "custom",
                        "date_from": date_from,
                        "date_to": date_to,
                    }
                ).get_period(TODAY)
                self.assertEqual(period, YEAR_2026)
                # потребители периода не падают
                period.previous_year()
                period.months()

    def test_boundary_years_are_allowed(self):
        form = PeriodForm(
            data={
                "preset": "custom",
                "date_from": "1900-01-01",
                "date_to": "2100-12-31",
            }
        )
        self.assertEqual(
            form.get_period(TODAY), Period(date(1900, 1, 1), date(2100, 12, 31))
        )

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

    def test_client_empty_label(self):
        self.assertEqual(
            FinanceFilterForm().fields["client"].empty_label, "Все клиенты"
        )

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


class DateWidgetFormatTests(SimpleTestCase):
    def test_initial_dates_render_as_iso_for_date_input(self):
        """В ru-локали DateInput без format выводит 05.03.2026, а type=date ждёт ISO."""
        form = PeriodForm(
            initial={"date_from": date(2026, 3, 5), "date_to": date(2026, 4, 10)}
        )
        with translation.override("ru"):
            self.assertIn('value="2026-03-05"', str(form["date_from"]))
            self.assertIn('value="2026-04-10"', str(form["date_to"]))


class TripsFilterFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.traveller = CompanyUser.objects.create_user(
            "ivanov", last_name="Иванов", first_name="Иван", patron="Иванович"
        )
        cls.no_fio = CompanyUser.objects.create_user("petrov")
        cls.homebody = CompanyUser.objects.create_user("sidorov", last_name="Сидоров")
        for employee in (cls.traveller, cls.no_fio):
            BusinessTrip.objects.create(
                employee=employee, beg_dt=date(2026, 3, 1), end_dt=date(2026, 3, 2)
            )

    def test_trips_form_defaults(self):
        form = TripsFilterForm(data={})
        self.assertIsNone(form.get_employee())
        self.assertEqual(form.get_group(), "city")
        self.assertEqual(form.get_period(TODAY), YEAR_2026)

    def test_trips_form_employee_and_group(self):
        form = TripsFilterForm(
            data={"employee": str(self.traveller.pk), "group": "region"}
        )
        self.assertEqual(form.get_employee(), self.traveller)
        self.assertEqual(form.get_group(), "region")

    def test_trips_form_garbage_falls_back(self):
        form = TripsFilterForm(data={"employee": "not-a-uuid", "group": "foo"})
        self.assertIsNone(form.get_employee())
        self.assertEqual(form.get_group(), "city")

    def test_trips_form_lists_only_employees_with_trips(self):
        queryset = TripsFilterForm(data={}).fields["employee"].queryset
        self.assertEqual(set(queryset), {self.traveller, self.no_fio})
        self.assertEqual(queryset.count(), 2)

    def test_trips_form_employee_label_is_fio(self):
        field = TripsFilterForm(data={}).fields["employee"]
        self.assertEqual(
            field.label_from_instance(self.traveller), "Иванов Иван Иванович"
        )
        self.assertEqual(field.label_from_instance(self.no_fio), "petrov")


class EquipmentFilterFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hematology = MedDirection.objects.create(name="Гематология")
        cls.unused_direction = MedDirection.objects.create(name="ИФА")
        # город и страна явно пустые: иначе модель берёт по умолчанию «Не указан»/«Россия»
        cls.mindray = Manufacturer.objects.create(
            name="Mindray", city=None, country=None
        )
        cls.unused_manufacturer = Manufacturer.objects.create(
            name="Sysmex", city=None, country=None
        )
        Equipment.objects.create(
            full_name="BC-5000",
            med_direction=cls.hematology,
            manufacturer=cls.mindray,
        )

    def test_equipment_form_defaults(self):
        form = EquipmentFilterForm(data={})
        self.assertEqual(form.get_filters(), EquipmentFilters())
        self.assertTrue(form.get_filters().is_empty)
        self.assertEqual(form.get_period(TODAY), YEAR_2026)

    def test_equipment_form_values(self):
        form = EquipmentFilterForm(
            data={
                "direction": str(self.hematology.pk),
                "manufacturer": str(self.mindray.pk),
                "supply": "ours",
            }
        )
        filters = form.get_filters()
        self.assertEqual(filters.direction, self.hematology)
        self.assertEqual(filters.manufacturer, self.mindray)
        self.assertEqual(filters.supply, "ours")
        self.assertFalse(filters.is_empty)

    def test_equipment_form_garbage_falls_back(self):
        form = EquipmentFilterForm(
            data={"direction": "abc", "manufacturer": "not-a-uuid", "supply": "foo"}
        )
        self.assertEqual(form.get_filters(), EquipmentFilters())

    def test_equipment_form_lists_only_used_directories(self):
        form = EquipmentFilterForm(data={})
        self.assertEqual(list(form.fields["direction"].queryset), [self.hematology])
        self.assertEqual(list(form.fields["manufacturer"].queryset), [self.mindray])

    def test_equipment_form_manufacturer_label_is_name(self):
        # str(Manufacturer) падает без города: в списке — только название
        form = EquipmentFilterForm(data={})
        self.assertEqual(
            [label for _, label in form.fields["manufacturer"].choices],
            ["Все производители", "Mindray"],
        )
