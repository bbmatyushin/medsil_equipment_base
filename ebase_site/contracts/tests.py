from datetime import date
from decimal import Decimal

from django.test import RequestFactory, SimpleTestCase, TestCase
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse

from clients.models import Client
from directory.models import City
from contracts.admin import ClientNameOnlyAutocompleteSelect, ContractAdmin
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
        self.contract = Contract.objects.create(
            client=self.client_obj,
            contract_number="CNT-001",
            conclusion_date="2026-01-15",
            contract_amount=100000,
        )

    def test_contract_creation(self):
        self.assertEqual(self.contract.contract_number, "CNT-001")
        self.assertEqual(str(self.contract), "CNT-001 — Тестовый клиент")

    def test_payment_recalc(self):
        Payment.objects.create(contract=self.contract, date="2026-01-20", amount=30000)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.payment_amount, 30000)
        self.assertEqual(self.contract.debt, 70000)
        self.assertEqual(self.contract.profit, 30000)
        self.assertEqual(self.contract.payment_status, "partial")

    def test_payment_status_no_receipts_on_creation(self):
        self.assertEqual(self.contract.payment_status, "no_receipts")

    def test_payment_status_partial(self):
        Payment.objects.create(contract=self.contract, date="2026-01-20", amount=30000)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.payment_status, "partial")

    def test_payment_status_paid(self):
        Payment.objects.create(
            contract=self.contract, date="2026-01-20", amount=Decimal("100000.00")
        )
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.payment_status, "paid")

    def test_payment_status_paid_when_overpaid(self):
        Payment.objects.create(
            contract=self.contract, date="2026-01-20", amount=Decimal("150000.00")
        )
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.payment_status, "paid")

    def test_payment_status_resets_after_payment_delete(self):
        payment = Payment.objects.create(
            contract=self.contract, date="2026-01-20", amount=Decimal("100000.00")
        )
        payment.delete()
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.payment_status, "no_receipts")

    def test_payment_status_updates_when_contract_amount_changes(self):
        Payment.objects.create(
            contract=self.contract, date="2026-01-20", amount=Decimal("100000.00")
        )
        self.contract.contract_amount = Decimal("200000.00")
        self.contract.save()
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.payment_status, "partial")
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

    def test_contract_recalc_on_spare_part_shipment(self):
        """Создание отгрузки с запчастями увеличивает expenses_amount контракта."""
        from spare_part.models import (
            SparePart,
            SparePartShipmentV2,
            SparePartShipmentM2M,
        )
        from directory.models import Unit
        from users.models import CompanyUser

        unit = Unit.objects.create(short_name="шт.", full_name="штука")
        spare_part = SparePart.objects.create(name="Тестовая запчасть", unit=unit)
        user = CompanyUser.objects.create_user(username="testshipper", password="pass")

        shipment = SparePartShipmentV2.objects.create(
            doc_num="ТО-001",
            shipment_dt=date.today(),
            user=user,
            contract=self.contract,
        )
        SparePartShipmentM2M.objects.create(
            shipment=shipment,
            spare_part=spare_part,
            quantity=2,
            price=Decimal("100.00"),
        )

        self.contract.refresh_from_db()
        self.assertEqual(self.contract.expenses_amount, Decimal("200.00"))


class ContractAdminWidgetTests(SimpleTestCase):
    """Проверяет, что autocomplete-виджет клиента настроен на прямое поле ForeignKey.

    Передача обратной связи (ManyToOneRel) в AutocompleteSelect приводит к тому,
    что AJAX-запрос уходит с ``field_name=<related_name>`` и падает в
    ``AutocompleteJsonView`` с ``AttributeError: 'ManyToOneRel' object has no
    attribute 'get_limit_choices_to'``.
    """

    def test_client_autocomplete_widget_uses_forward_field(self):
        request = RequestFactory().get("/admin/contracts/contract/add/")
        user = AnonymousUser()
        user.is_staff = True
        user.is_superuser = True
        request.user = user

        model_admin = ContractAdmin(Contract, admin.site)
        form = model_admin.get_form(request)()
        widget = form.fields["client"].widget
        # Django оборачивает виджет в RelatedFieldWidgetWrapper
        inner = widget.widget if hasattr(widget, "widget") else widget

        self.assertIsInstance(inner, ClientNameOnlyAutocompleteSelect)
        self.assertEqual(inner.field, Contract._meta.get_field("client"))

        attrs = inner.build_attrs({"name": "client"}, {"id": "id_client"})
        self.assertEqual(attrs["data-app-label"], "contracts")
        self.assertEqual(attrs["data-model-name"], "contract")
        self.assertEqual(attrs["data-field-name"], "client")


class ContractAdminFormTests(TestCase):
    """Проверки отображения и фильтрации поля payment_status в админке."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin_form_tester", password="pass"
        )

    def test_payment_status_excluded_on_add_form(self):
        request = RequestFactory().get("/admin/contracts/contract/add/")
        request.user = self.user
        model_admin = ContractAdmin(Contract, admin.site)
        form = model_admin.get_form(request)()
        self.assertNotIn("payment_status", form.fields)

    def test_payment_status_included_on_change_form(self):
        city, _ = City.objects.get_or_create(
            name="Москва", region=None, defaults={"region": None}
        )
        client_obj = Client.objects.create(
            name="Тестовый клиент", city=city, inn="123456789001"
        )
        contract = Contract.objects.create(
            client=client_obj,
            contract_number="CNT-FORM-001",
            conclusion_date="2026-01-15",
            contract_amount=Decimal("100000.00"),
        )

        request = RequestFactory().get(
            f"/admin/contracts/contract/{contract.pk}/change/"
        )
        request.user = self.user
        model_admin = ContractAdmin(Contract, admin.site)
        form = model_admin.get_form(request, obj=contract)()
        self.assertIn("payment_status", form.fields)

    def test_payment_status_list_filter_enabled(self):
        self.assertIn("payment_status", ContractAdmin.list_filter)


class ContractAdminChangelistTotalsTests(TestCase):
    """Проверяет блок общих итогов в changelist админки контрактов."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="totals_tester", password="pass"
        )
        self.city, _ = City.objects.get_or_create(
            name="Москва", region=None, defaults={"region": None}
        )
        self.client_obj = Client.objects.create(
            name="Тестовый клиент", city=self.city, inn="123456789001"
        )
        self.contract_first = Contract.objects.create(
            client=self.client_obj,
            contract_number="CNT-001",
            conclusion_date="2026-01-15",
            contract_amount=Decimal("100000.00"),
        )
        self.contract_second = Contract.objects.create(
            client=self.client_obj,
            contract_number="CNT-002",
            conclusion_date="2026-02-15",
            contract_amount=Decimal("200000.00"),
        )
        Payment.objects.create(
            contract=self.contract_first, date="2026-01-20", amount=Decimal("30000.00")
        )
        Payment.objects.create(
            contract=self.contract_second, date="2026-02-20", amount=Decimal("50000.00")
        )
        ContractExpense.objects.create(
            contract=self.contract_first,
            expense_type="business_trip",
            quantity=2,
            cost=Decimal("5000.00"),
        )
        ContractExpense.objects.create(
            contract=self.contract_second,
            expense_type="other",
            quantity=1,
            cost=Decimal("10000.00"),
        )
        self.url = reverse("admin:contracts_contract_changelist")

    def _login(self):
        self.client.force_login(self.user)

    def test_changelist_includes_totals_for_all_contracts(self):
        self._login()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("totals", response.context)

        totals = response.context["totals"]
        self.assertEqual(totals["contract_amount"], "300 000,00")
        self.assertEqual(totals["payment_amount"], "80 000,00")
        self.assertEqual(totals["expenses_amount"], "20 000,00")
        self.assertEqual(totals["debt"], "220 000,00")
        self.assertEqual(totals["profit"], "60 000,00")

    def test_changelist_totals_are_filtered_by_search(self):
        self._login()
        response = self.client.get(self.url, {"q": "CNT-001"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("totals", response.context)

        totals = response.context["totals"]
        self.assertEqual(totals["contract_amount"], "100 000,00")
        self.assertEqual(totals["payment_amount"], "30 000,00")
        self.assertEqual(totals["expenses_amount"], "10 000,00")
        self.assertEqual(totals["debt"], "70 000,00")
        self.assertEqual(totals["profit"], "20 000,00")

    def test_changelist_totals_empty_result(self):
        self._login()
        response = self.client.get(self.url, {"q": "несуществующий-номер"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("totals", response.context)

        totals = response.context["totals"]
        self.assertEqual(totals["contract_amount"], "—")
        self.assertEqual(totals["payment_amount"], "—")
        self.assertEqual(totals["expenses_amount"], "—")
        self.assertEqual(totals["debt"], "—")
        self.assertEqual(totals["profit"], "—")


class ContractAdminAutocompleteTests(TestCase):
    """Интеграционная проверка endpoint ``/admin/autocomplete/`` для поля Клиент."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="autocomplete_tester", password="pass"
        )
        self.city, _ = City.objects.get_or_create(
            name="Москва", region=None, defaults={"region": None}
        )
        self.client_obj = Client.objects.create(
            name="Тестовый клиент", city=self.city, inn="123456789001"
        )

    def test_client_autocomplete_returns_results(self):
        self.client.force_login(self.user)
        url = reverse("admin:autocomplete")
        response = self.client.get(
            url,
            {
                "app_label": "contracts",
                "model_name": "contract",
                "field_name": "client",
                "term": "Тест",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(
            any(self.client_obj.name in result["text"] for result in data["results"]),
            f"Клиент не найден в результатах autocomplete: {data}",
        )


class ContractAdminBusinessTripSectionTests(TestCase):
    """Smoke-тест раздела «Командировки по контракту» на карточке контракта."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="trip_section_tester", password="pass"
        )
        self.employee = User.objects.create_user(username="ivanov", password="pass")
        self.city, _ = City.objects.get_or_create(
            name="Москва", region=None, defaults={"region": None}
        )
        self.client_obj = Client.objects.create(
            name="Тестовый клиент", city=self.city, inn="123456789001"
        )
        self.contract = Contract.objects.create(
            client=self.client_obj,
            contract_number="CNT-BT-001",
            conclusion_date=date(2026, 1, 10),
            contract_amount=Decimal("100000.00"),
        )

    def test_change_page_renders_trip_section(self):
        from business_trip.models import (
            BusinessTrip,
            BusinessTripDestination,
        )
        from clients.models import Department

        department = Department.objects.create(
            name="Отделение 1",
            client=self.client_obj,
            city=self.city,
            address="ул. Ленина, 1",
        )
        trip = BusinessTrip.objects.create(
            employee=self.employee,
            beg_dt=date(2026, 3, 26),
            end_dt=date(2026, 3, 26),
        )
        BusinessTripDestination.objects.create(
            business_trip=trip,
            department=department,
            beg_dt=date(2026, 3, 26),
            end_dt=date(2026, 3, 26),
        )
        trip.contract.add(self.contract)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("admin:contracts_contract_change", args=[self.contract.pk])
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Командировочные расходы", content)
        # Доля = 700 (суточные за 1 день), ссылка на командировку
        self.assertIn("700.00", content)
        self.assertIn(
            reverse("admin:business_trip_businesstrip_change", args=[trip.pk]),
            content,
        )
