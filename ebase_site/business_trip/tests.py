import tempfile
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase, override_settings

from business_trip.models import (
    BusinessTrip,
    BusinessTripDestination,
    BusinessTripExpense,
    BusinessTripPhoto,
    ExpenseType,
)
from clients.models import Client, Department
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
