import tempfile
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.db.models import Sum
from django.test import TestCase, override_settings
from django.urls import reverse

from business_trip.models import (
    BusinessTrip,
    BusinessTripDestination,
    BusinessTripExpense,
    BusinessTripPhoto,
    ExpenseType,
)
from clients.models import Client, Department
from contracts.models import Contract
from directory.models import City

User = get_user_model()


class ExpenseTypeTests(TestCase):
    def test_create_expense_type(self):
        expense_type = ExpenseType.objects.create(name="Такси")
        self.assertEqual(expense_type.name, "Такси")
        self.assertEqual(str(expense_type), "Такси")

    def test_name_unique(self):
        ExpenseType.objects.create(name="Гостиница")
        with self.assertRaises(IntegrityError):
            ExpenseType.objects.create(name="Гостиница")


class BusinessTripAllowanceTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")

    def _make(self, beg, end, **kwargs):
        return BusinessTrip.objects.create(
            employee=self.employee, beg_dt=beg, end_dt=end, **kwargs
        )

    def test_allowance_four_days(self):
        # 16.03–19.03 — 4 дня включительно
        trip = self._make(date(2026, 3, 16), date(2026, 3, 19))
        self.assertEqual(trip.days_count, 4)
        self.assertEqual(trip.allowance_amount, Decimal("2800.00"))

    def test_allowance_one_day(self):
        # 26.03–26.03 — 1 день
        trip = self._make(date(2026, 3, 26), date(2026, 3, 26))
        self.assertEqual(trip.days_count, 1)
        self.assertEqual(trip.allowance_amount, Decimal("700.00"))

    def test_allowance_recalc_on_date_change(self):
        trip = self._make(date(2026, 3, 16), date(2026, 3, 19))
        self.assertEqual(trip.allowance_amount, Decimal("2800.00"))
        trip.end_dt = date(2026, 3, 20)
        trip.save(update_fields=["end_dt"])
        trip.refresh_from_db()
        self.assertEqual(trip.allowance_amount, Decimal("3500.00"))

    def test_allowance_zero_for_inverted_dates(self):
        # save() обходит clean() — проверяем защитную ветку _calc_allowance
        trip = self._make(date(2026, 3, 19), date(2026, 3, 16))
        self.assertEqual(trip.allowance_amount, Decimal("0"))


class BusinessTripDocNumberTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")

    def test_doc_number_auto_first(self):
        trip = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 3, 16), end_dt=date(2026, 3, 19)
        )
        self.assertEqual(trip.doc_number, 1)

    def test_doc_number_auto_increment(self):
        first = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 3, 16), end_dt=date(2026, 3, 19)
        )
        second = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 4, 1), end_dt=date(2026, 4, 3)
        )
        self.assertEqual(first.doc_number, 1)
        self.assertEqual(second.doc_number, 2)

    def test_doc_number_manual_not_overwritten(self):
        trip = BusinessTrip.objects.create(
            employee=self.employee,
            beg_dt=date(2026, 3, 16),
            end_dt=date(2026, 3, 19),
            doc_number=100,
        )
        self.assertEqual(trip.doc_number, 100)


class BusinessTripValidationTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")

    def test_end_before_beg_raises(self):
        trip = BusinessTrip(
            employee=self.employee, beg_dt=date(2026, 3, 19), end_dt=date(2026, 3, 16)
        )
        with self.assertRaises(ValidationError):
            trip.clean()


class BusinessTripDestinationTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")
        self.city, _ = City.objects.get_or_create(
            name="Смоленск", region=None, defaults={"region": None}
        )
        self.client_obj = Client.objects.create(
            name="СОДКБ", city=self.city, inn="111111111111"
        )
        self.department = Department.objects.create(
            name="СОДКБ",
            client=self.client_obj,
            city=self.city,
            address="ул. Ленина, 1",
        )
        self.trip = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 4, 1), end_dt=date(2026, 4, 3)
        )

    def test_city_pulled_from_department(self):
        dest = BusinessTripDestination.objects.create(
            business_trip=self.trip,
            department=self.department,
            beg_dt=date(2026, 4, 1),
            end_dt=date(2026, 4, 2),
        )
        self.assertEqual(dest.city, self.city)
        self.assertEqual(dest.client, self.client_obj)

    def test_dest_dates_outside_trip_raises(self):
        dest = BusinessTripDestination(
            business_trip=self.trip,
            department=self.department,
            beg_dt=date(2026, 3, 30),  # до выезда
            end_dt=date(2026, 4, 2),
        )
        with self.assertRaises(ValidationError):
            dest.clean()

    def test_dest_end_before_beg_raises(self):
        dest = BusinessTripDestination(
            business_trip=self.trip,
            department=self.department,
            beg_dt=date(2026, 4, 2),
            end_dt=date(2026, 4, 1),
        )
        with self.assertRaises(ValidationError):
            dest.clean()


class BusinessTripExpenseTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")
        self.trip = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 3, 16), end_dt=date(2026, 3, 19)
        )
        self.expense_type = ExpenseType.objects.create(name="Такси")

    def test_create_expense(self):
        expense = BusinessTripExpense.objects.create(
            business_trip=self.trip,
            expense_type=self.expense_type,
            date=date(2026, 3, 16),
            amount=Decimal("500.00"),
            comment="Такси до гостиницы",
        )
        self.assertEqual(expense.amount, Decimal("500.00"))
        self.assertEqual(str(self.trip.expenses.first()), str(expense))

    def test_negative_amount_raises(self):
        expense = BusinessTripExpense(
            business_trip=self.trip,
            expense_type=self.expense_type,
            date=date(2026, 3, 16),
            amount=Decimal("-100.00"),
        )
        with self.assertRaises(ValidationError):
            expense.full_clean()


class BusinessTripContractTests(TestCase):
    """Тесты M2M-связи командировки с контрактами."""

    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")
        self.city, _ = City.objects.get_or_create(
            name="Москва", defaults={"region": None}
        )
        self.client_obj = Client.objects.create(
            name="Клиент 1", city=self.city, inn="111111111111"
        )
        self.contract1 = Contract.objects.create(
            client=self.client_obj,
            contract_number="CNT-001",
            conclusion_date=date(2026, 1, 10),
            contract_amount=Decimal("100000"),
        )
        self.contract2 = Contract.objects.create(
            client=self.client_obj,
            contract_number="CNT-002",
            conclusion_date=date(2026, 1, 15),
            contract_amount=Decimal("200000"),
        )
        self.trip = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 3, 16), end_dt=date(2026, 3, 19)
        )

    def test_multiple_contracts_linked(self):
        """К одной командировке можно привязать несколько контрактов."""
        self.trip.contract.add(self.contract1, self.contract2)
        self.assertEqual(self.trip.contract.count(), 2)
        self.assertIn(self.contract1, self.trip.contract.all())
        self.assertIn(self.contract2, self.trip.contract.all())

    def test_reverse_relation(self):
        """Из контракта видны связанные командировки."""
        self.trip.contract.add(self.contract1)
        self.assertIn(self.trip, self.contract1.business_trip.all())

    def test_no_contracts_by_default(self):
        """Новая командировка не имеет контрактов."""
        self.assertEqual(self.trip.contract.count(), 0)


class BusinessTripContractExpenseTests(TestCase):
    """Тесты автоматического разнесения расходов командировки по контрактам."""

    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")
        self.city, _ = City.objects.get_or_create(
            name="Москва", defaults={"region": None}
        )
        self.client_obj = Client.objects.create(
            name="Клиент 1", city=self.city, inn="111111111111"
        )
        self.department = Department.objects.create(
            name="Отделение 1",
            client=self.client_obj,
            city=self.city,
            address="ул. Ленина, 1",
        )
        self.contract1 = Contract.objects.create(
            client=self.client_obj,
            contract_number="CNT-001",
            conclusion_date=date(2026, 1, 10),
            contract_amount=Decimal("100000"),
        )
        self.contract2 = Contract.objects.create(
            client=self.client_obj,
            contract_number="CNT-002",
            conclusion_date=date(2026, 1, 15),
            contract_amount=Decimal("200000"),
        )
        self.expense_type = ExpenseType.objects.create(name="Такси")
        # Однодневная командировка: суточные = 700
        self.trip = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 3, 26), end_dt=date(2026, 3, 26)
        )
        BusinessTripDestination.objects.create(
            business_trip=self.trip,
            department=self.department,
            beg_dt=date(2026, 3, 26),
            end_dt=date(2026, 3, 26),
        )

    def _shares(self):
        return {
            entry.contract_id: entry.amount
            for entry in self.trip.contract_expenses.all()
        }

    def test_split_with_remainder_between_two_contracts(self):
        """4000,33 на 2 контракта: 2000,17 первому по дате, 2000,16 второму.

        4000,33 / 2 = 2000,165 — база округляется вниз до копеек (2000,16),
        остаток 0,01 уходит на первый по дате заключения контракт.
        """
        BusinessTripExpense.objects.create(
            business_trip=self.trip,
            expense_type=self.expense_type,
            date=date(2026, 3, 26),
            amount=Decimal("3300.33"),
        )
        self.trip.contract.add(self.contract1, self.contract2)

        shares = self._shares()
        # 3300,33 (затраты) + 700 (суточные) = 4000,33
        self.assertEqual(shares[self.contract1.pk], Decimal("2000.17"))
        self.assertEqual(shares[self.contract2.pk], Decimal("2000.16"))

        self.contract1.refresh_from_db()
        self.contract2.refresh_from_db()
        self.assertEqual(self.contract1.expenses_amount, Decimal("2000.17"))
        self.assertEqual(self.contract2.expenses_amount, Decimal("2000.16"))

    def test_contract_of_other_client_not_attributed(self):
        """Контракт клиента, которого нет в пунктах командировки, доли не получает."""
        other_client = Client.objects.create(
            name="Клиент 2", city=self.city, inn="222222222222"
        )
        contract3 = Contract.objects.create(
            client=other_client,
            contract_number="CNT-003",
            conclusion_date=date(2026, 1, 20),
            contract_amount=Decimal("50000"),
        )
        self.trip.contract.add(self.contract1, contract3)

        shares = self._shares()
        self.assertNotIn(contract3.pk, shares)
        # Вся сумма (700 суточных) ушла на единственный подходящий контракт
        self.assertEqual(shares[self.contract1.pk], Decimal("700.00"))

    def test_split_between_contracts_of_different_clients(self):
        """Контракты разных клиентов делят сумму, если оба клиента в пунктах."""
        other_client = Client.objects.create(
            name="Клиент 2", city=self.city, inn="222222222222"
        )
        other_department = Department.objects.create(
            name="Отделение 2",
            client=other_client,
            city=self.city,
            address="ул. Мира, 2",
        )
        contract3 = Contract.objects.create(
            client=other_client,
            contract_number="CNT-003",
            conclusion_date=date(2026, 1, 20),
            contract_amount=Decimal("50000"),
        )
        BusinessTripDestination.objects.create(
            business_trip=self.trip,
            department=other_department,
            beg_dt=date(2026, 3, 26),
            end_dt=date(2026, 3, 26),
        )
        self.trip.contract.add(self.contract1, contract3)

        shares = self._shares()
        self.assertEqual(shares[self.contract1.pk], Decimal("350.00"))
        self.assertEqual(shares[contract3.pk], Decimal("350.00"))

    def test_recalc_on_expense_change_and_delete(self):
        """Изменение и удаление затрат пересчитывает доли и затраты контракта."""
        self.trip.contract.add(self.contract1)
        expense = BusinessTripExpense.objects.create(
            business_trip=self.trip,
            expense_type=self.expense_type,
            date=date(2026, 3, 26),
            amount=Decimal("300.00"),
        )
        self.assertEqual(self._shares()[self.contract1.pk], Decimal("1000.00"))

        expense.amount = Decimal("800.00")
        expense.save()
        self.assertEqual(self._shares()[self.contract1.pk], Decimal("1500.00"))

        expense.delete()
        self.assertEqual(self._shares()[self.contract1.pk], Decimal("700.00"))
        self.contract1.refresh_from_db()
        self.assertEqual(self.contract1.expenses_amount, Decimal("700.00"))

    def test_share_removed_with_contract_unlink(self):
        """Удаление контракта из командировки удаляет его долю, остаток пересчитывается."""
        self.trip.contract.add(self.contract1, self.contract2)
        self.trip.contract.remove(self.contract2)

        shares = self._shares()
        self.assertNotIn(self.contract2.pk, shares)
        self.assertEqual(shares[self.contract1.pk], Decimal("700.00"))

        self.contract2.refresh_from_db()
        self.assertEqual(self.contract2.expenses_amount, Decimal("0"))

    def test_trip_deletion_recalc_contract(self):
        """Удаление командировки убирает её долю из затрат контракта."""
        self.trip.contract.add(self.contract1)
        self.contract1.refresh_from_db()
        self.assertEqual(self.contract1.expenses_amount, Decimal("700.00"))

        self.trip.delete()
        self.contract1.refresh_from_db()
        self.assertEqual(self.contract1.expenses_amount, Decimal("0"))


class BusinessTripExpensesTotalTests(TestCase):
    """Тесты расчёта итоговых затрат (командировочные + затраты на поездку)."""

    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")
        self.trip = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 3, 16), end_dt=date(2026, 3, 19)
        )
        self.expense_type = ExpenseType.objects.create(name="Такси")

    def test_allowance_only_no_expenses(self):
        """Без затрат на поездку итог = командировочные (4 дня × 700 = 2800)."""
        total = self.trip.allowance_amount + Decimal(
            str(self.trip.expenses.aggregate(total=Sum("amount"))["total"] or 0)
        )
        self.assertEqual(total, Decimal("2800.00"))

    def test_allowance_plus_expenses(self):
        """Итог = командировочные + сумма всех затрат."""
        BusinessTripExpense.objects.create(
            business_trip=self.trip,
            expense_type=self.expense_type,
            date=date(2026, 3, 16),
            amount=Decimal("500.00"),
        )
        BusinessTripExpense.objects.create(
            business_trip=self.trip,
            expense_type=self.expense_type,
            date=date(2026, 3, 17),
            amount=Decimal("1200.00"),
        )
        expenses_sum = self.trip.expenses.aggregate(total=Sum("amount"))[
            "total"
        ] or Decimal("0")
        total = self.trip.allowance_amount + expenses_sum
        # 2800 (суточные) + 500 + 1200 = 4500
        self.assertEqual(total, Decimal("4500.00"))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class BusinessTripPhotoTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")
        self.trip = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 3, 16), end_dt=date(2026, 3, 19)
        )

    def test_photo_linked_and_deleted_with_record(self):
        photo_file = SimpleUploadedFile(
            "check.jpg", b"\x47\x49\x46\x38\x39\x61", content_type="image/jpeg"
        )
        photo = BusinessTripPhoto.objects.create(
            business_trip=self.trip, photo=photo_file
        )
        self.assertIn(photo, self.trip.photos.all())
        file_name = photo.photo.name
        self.assertTrue(photo.photo.storage.exists(file_name))
        photo.delete()
        self.assertFalse(photo.photo.storage.exists(file_name))


class BusinessTripAdminSmokeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="admin", password="pass")
        self.employee = User.objects.create_user(username="ivanov", password="pass")
        self.client.force_login(self.admin)

    def test_changelist_200(self):
        response = self.client.get(
            reverse("admin:business_trip_businesstrip_changelist")
        )
        self.assertEqual(response.status_code, 200)

    def test_add_page_200(self):
        response = self.client.get(reverse("admin:business_trip_businesstrip_add"))
        self.assertEqual(response.status_code, 200)

    def test_change_page_200(self):
        trip = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 3, 16), end_dt=date(2026, 3, 19)
        )
        response = self.client.get(
            reverse("admin:business_trip_businesstrip_change", args=[trip.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_expense_type_changelist_200(self):
        response = self.client.get(
            reverse("admin:business_trip_expensetype_changelist")
        )
        self.assertEqual(response.status_code, 200)
