from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model

from clients.models import Client, Department
from directory.models import City, ServiceType
from contracts.models import Contract
from ebase.models import Equipment, EquipmentAccounting, Service, ServiceExpense


User = get_user_model()


class ServiceContractTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')
        self.city, _ = City.objects.get_or_create(name='Москва', region=None, defaults={'region': None})
        self.service_type = ServiceType.objects.create(name='Ремонт')
        self.client_obj = Client.objects.create(
            name='Тестовый клиент', city=self.city, inn='123456789001'
        )
        self.department = Department.objects.create(
            name='Главный офис', client=self.client_obj, city=self.city
        )
        self.equipment = Equipment.objects.create(
            full_name='Анализатор', short_name='Анализатор'
        )
        self.eq_acc = EquipmentAccounting.objects.create(
            equipment=self.equipment, serial_number='SN001', user=self.user
        )
        self.contract = Contract.objects.create(
            client=self.department,
            contract_number='CNT-SRV-001',
            conclusion_date='2026-01-15',
            contract_amount=50000,
        )

    def test_service_links_to_contract(self):
        """Проверяет что ремонт связывается с контрактом."""
        service = Service.objects.create(
            service_type=self.service_type,
            equipment_accounting=self.eq_acc,
            user=self.user,
            beg_dt='2026-02-01',
            contract=self.contract,
        )
        self.assertEqual(service.contract.contract_number, 'CNT-SRV-001')

    def test_service_without_contract(self):
        """Проверяет что ремонт может существовать без контракта."""
        service = Service.objects.create(
            service_type=self.service_type,
            equipment_accounting=self.eq_acc,
            user=self.user,
            beg_dt='2026-02-01',
        )
        self.assertIsNone(service.contract)

    def test_contract_recalc_on_service_save(self):
        """Проверяет что сохранение сервиса с контрактом пересчитывает контракт."""
        Service.objects.create(
            service_type=self.service_type,
            equipment_accounting=self.eq_acc,
            user=self.user,
            beg_dt='2026-02-01',
            contract=self.contract,
            spare_part_count={},
        )
        # No spare parts: ServiceExpense empty, profit should be 0
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.profit, 0)
        self.assertEqual(self.contract.expenses_amount, 0)

    def test_unique_contract_service_link(self):
        """Проверяет что один контракт нельзя связать с двумя ремонтами."""
        service1 = Service.objects.create(
            service_type=self.service_type,
            equipment_accounting=self.eq_acc,
            user=self.user,
            beg_dt='2026-02-01',
            contract=self.contract,
        )
        # Creating a second service with the same contract should fail
        with self.assertRaises(Exception):
            Service.objects.create(
                service_type=self.service_type,
                equipment_accounting=self.eq_acc,
                user=self.user,
                beg_dt='2026-02-02',
                contract=self.contract,
            )
