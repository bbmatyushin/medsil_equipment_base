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
