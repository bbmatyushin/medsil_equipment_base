from decimal import Decimal

from django.contrib import admin
from django.test import RequestFactory, TestCase
from django.contrib.auth import get_user_model
from django.urls import resolve, reverse

from clients.models import Client, Department
from directory.models import City, ServiceType
from contracts.models import Contract
from ebase.forms import ServiceForm
from ebase.models import (
    Equipment,
    EquipmentAccDepartment,
    EquipmentAccounting,
    ReplacementEquipment,
    Service,
)


User = get_user_model()


class ServiceContractTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass")
        self.city, _ = City.objects.get_or_create(
            name="Москва", region=None, defaults={"region": None}
        )
        self.service_type = ServiceType.objects.create(name="Ремонт")
        self.client_obj = Client.objects.create(
            name="Тестовый клиент", city=self.city, inn="123456789001"
        )
        self.department = Department.objects.create(
            name="Главный офис", client=self.client_obj, city=self.city
        )
        self.equipment = Equipment.objects.create(
            full_name="Анализатор", short_name="Анализатор"
        )
        self.eq_acc = EquipmentAccounting.objects.create(
            equipment=self.equipment, serial_number="SN001", user=self.user
        )
        self.contract = Contract.objects.create(
            client=self.department,
            contract_number="CNT-SRV-001",
            conclusion_date="2026-01-15",
            contract_amount=50000,
        )

    def test_service_links_to_contract(self):
        """Проверяет что ремонт связывается с контрактом."""
        service = Service.objects.create(
            service_type=self.service_type,
            equipment_accounting=self.eq_acc,
            user=self.user,
            beg_dt="2026-02-01",
            contract=self.contract,
        )
        self.assertEqual(service.contract.contract_number, "CNT-SRV-001")

    def test_service_without_contract(self):
        """Проверяет что ремонт может существовать без контракта."""
        service = Service.objects.create(
            service_type=self.service_type,
            equipment_accounting=self.eq_acc,
            user=self.user,
            beg_dt="2026-02-01",
        )
        self.assertIsNone(service.contract)

    def test_service_contract_copies_to_shipment(self):
        """Связь отгрузки с контрактом корректно учитывается в расходах."""
        from directory.models import Unit
        from spare_part.models import (
            SparePart,
            SparePartShipmentV2,
            SparePartShipmentM2M,
        )

        self.service = Service.objects.create(
            service_type=self.service_type,
            equipment_accounting=self.eq_acc,
            user=self.user,
            beg_dt="2026-02-01",
            contract=self.contract,
        )
        self.unit = Unit.objects.create(short_name="шт.", full_name="штука")
        self.spare_part = SparePart.objects.create(
            name="Запчасть для отгрузки", unit=self.unit
        )
        shipment = SparePartShipmentV2.objects.create(
            doc_num="АВ-001",
            shipment_dt=self.service.beg_dt,
            user=self.service.user,
            service=self.service,
            contract=self.contract,
        )
        SparePartShipmentM2M.objects.create(
            shipment=shipment,
            spare_part=self.spare_part,
            quantity=1,
            price=Decimal("50.00"),
        )

        self.contract.refresh_from_db()
        self.assertEqual(self.contract.expenses_amount, Decimal("50.00"))


class ReplacementEquipmentReuseTests(TestCase):
    """Один подменный прибор можно выдавать в несколько ремонтов по очереди."""

    def setUp(self):
        self.user = User.objects.create_superuser(username="admin", password="pass")
        self.city, _ = City.objects.get_or_create(name="Москва", region=None)
        self.service_type = ServiceType.objects.create(name="Ремонт")
        self.client_obj = Client.objects.create(
            name="Тестовый клиент", city=self.city, inn="123456789002"
        )
        self.equipment = Equipment.objects.create(
            full_name="Анализатор", short_name="Анализатор"
        )
        self.old_dept = Department.objects.create(
            name="Старая больница", client=self.client_obj, city=self.city
        )
        self.new_dept = Department.objects.create(
            name="Новая больница", client=self.client_obj, city=self.city
        )
        self.old_eq_acc = EquipmentAccounting.objects.create(
            equipment=self.equipment, serial_number="SN-OLD", user=self.user
        )
        self.new_eq_acc = EquipmentAccounting.objects.create(
            equipment=self.equipment, serial_number="SN-NEW", user=self.user
        )
        EquipmentAccDepartment.objects.create(
            equipment_accounting=self.old_eq_acc, department=self.old_dept
        )
        EquipmentAccDepartment.objects.create(
            equipment_accounting=self.new_eq_acc, department=self.new_dept
        )
        self.replacement = ReplacementEquipment.objects.create(
            equipment=self.equipment, serial_number="REPL-1", user=self.user
        )
        self.old_service = Service.objects.create(
            service_type=self.service_type,
            equipment_accounting=self.old_eq_acc,
            user=self.user,
            beg_dt="2026-01-10",
            end_dt="2026-01-20",
            returned_to_office=True,
            replacement_equipment=self.replacement,
        )

    def _new_service(self, **kwargs):
        return Service.objects.create(
            service_type=self.service_type,
            equipment_accounting=self.new_eq_acc,
            user=self.user,
            beg_dt="2026-03-01",
            replacement_equipment=self.replacement,
            **kwargs,
        )

    def _replacement_choices(self, url):
        request = RequestFactory().get(url)
        request.user = self.user
        request.resolver_match = resolve(url)
        model_admin = admin.site._registry[Service]
        formfield = model_admin.formfield_for_foreignkey(
            Service._meta.get_field("replacement_equipment"), request
        )
        return list(formfield.queryset)

    def test_same_replacement_in_second_service(self):
        """Второй ремонт с тем же подменным прибором сохраняется."""
        new_service = self._new_service()
        self.assertEqual(
            set(self.replacement.service_replacement_equipment.all()),
            {self.old_service, new_service},
        )

    def test_service_form_accepts_already_used_replacement(self):
        """Форма ремонта не ругается, что прибор уже был в другом ремонте."""
        form = ServiceForm(
            data={
                "service_type": self.service_type.pk,
                "equipment_accounting": self.new_eq_acc.pk,
                "user": self.user.pk,
                "beg_dt": "2026-03-01",
                "replacement_equipment": self.replacement.pk,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_replacement_choices_on_add(self):
        """Прибор из незавершённого ремонта недоступен, из завершённого — доступен."""
        url = reverse("admin:ebase_service_add")
        self.assertIn(self.replacement, self._replacement_choices(url))

        self._new_service()
        self.assertNotIn(self.replacement, self._replacement_choices(url))

    def test_replacement_choices_on_old_service_change(self):
        """В старом ремонте его прибор остаётся в списке, даже если выдан снова."""
        self._new_service()
        url = reverse("admin:ebase_service_change", args=[self.old_service.pk])
        self.assertIn(self.replacement, self._replacement_choices(url))

    def test_replacement_changelist_shows_last_service(self):
        """В списке подменного оборудования — последний ремонт и его подразделение."""
        new_service = self._new_service()
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("admin:ebase_replacementequipment_changelist")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, reverse("admin:ebase_service_change", args=[new_service.pk])
        )
        self.assertContains(response, "Новая больница")
