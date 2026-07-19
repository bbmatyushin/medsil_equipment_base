from django.test import TestCase

from business_trip.models import ExpenseType


class ExpenseTypeTests(TestCase):
    def test_create_expense_type(self):
        expense_type = ExpenseType.objects.create(name="Такси")
        self.assertEqual(expense_type.name, "Такси")
        self.assertEqual(str(expense_type), "Такси")

    def test_name_unique(self):
        ExpenseType.objects.create(name="Гостиница")
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ExpenseType.objects.create(name="Гостиница")


from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model

from business_trip.models import BusinessTrip

User = get_user_model()


class BusinessTripAllowanceTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")

    def _make(self, beg, end, **kwargs):
        return BusinessTrip.objects.create(employee=self.employee, beg_dt=beg, end_dt=end, **kwargs)

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
