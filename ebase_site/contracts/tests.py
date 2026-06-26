from django.test import TestCase
from django.contrib.auth import get_user_model

from clients.models import Client, Department
from directory.models import City
from contracts.models import Contract, Payment, ContractExpense


User = get_user_model()


class ContractModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass")
        self.city, _ = City.objects.get_or_create(
            name="Москва", region=None, defaults={"region": None}
        )
        self.client_obj = Client.objects.create(
            name="Тестовый клиент", city=self.city, inn="123456789001"
        )
        self.department = Department.objects.create(
            name="Главный офис", client=self.client_obj, city=self.city
        )
        self.contract = Contract.objects.create(
            client=self.department,
            contract_number="CNT-001",
            conclusion_date="2026-01-15",
            contract_amount=100000,
        )

    def test_contract_creation(self):
        self.assertEqual(self.contract.contract_number, "CNT-001")
        self.assertEqual(str(self.contract), "CNT-001 — Главный офис")

    def test_payment_recalc(self):
        Payment.objects.create(contract=self.contract, date="2026-01-20", amount=30000)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.payment_amount, 30000)
        self.assertEqual(self.contract.debt, 70000)
        self.assertEqual(self.contract.profit, 30000)

    def test_contract_expense_recalc(self):
        expense = ContractExpense.objects.create(
            contract=self.contract, expense_type="business_trip", quantity=2, cost=5000
        )
        self.contract.refresh_from_db()
        self.assertEqual(expense.name, "Командировочные")
        self.assertEqual(expense.sum, 10000)
        self.assertEqual(self.contract.expenses_amount, 10000)
        self.assertEqual(self.contract.profit, -10000)

    def test_payment_and_expense_recalc(self):
        Payment.objects.create(contract=self.contract, date="2026-01-20", amount=50000)
        ContractExpense.objects.create(
            contract=self.contract, expense_type="other", quantity=1, cost=15000
        )
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.payment_amount, 50000)
        self.assertEqual(self.contract.expenses_amount, 15000)
        self.assertEqual(self.contract.debt, 50000)
        self.assertEqual(self.contract.profit, 35000)

    def test_payment_delete_recalc(self):
        payment = Payment.objects.create(
            contract=self.contract, date="2026-01-20", amount=30000
        )
        payment.delete()
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.payment_amount, 0)
        self.assertEqual(self.contract.debt, 100000)

    def test_contract_expense_delete_recalc(self):
        expense = ContractExpense.objects.create(
            contract=self.contract, expense_type="other", quantity=1, cost=15000
        )
        expense.delete()
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.expenses_amount, 0)
        self.assertEqual(self.contract.profit, 0)
