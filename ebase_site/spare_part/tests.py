from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model

from directory.models import Unit, City
from ebase.models import Equipment
from spare_part.models import SparePart, SparePartSupplyV2, SparePartSupplyItem, SparePartCount


User = get_user_model()


class SparePartSupplyV2Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')
        self.unit = Unit.objects.create(short_name='шт.', full_name='штука')
        self.city = City.objects.create(name='Тест город')
        self.equipment = Equipment.objects.create(
            full_name='Анализатор', short_name='Анализатор'
        )
        self.part = SparePart.objects.create(
            article='ART-001', name='Датчик', unit=self.unit
        )
        self.part.equipment.add(self.equipment)

    def test_supply_item_sum_auto(self):
        """Проверяет что сумма вычисляется автоматически."""
        supply = SparePartSupplyV2.objects.create(
            doc_num='SUP-001', supply_dt='2026-01-10', user=self.user
        )
        item = SparePartSupplyItem.objects.create(
            supply=supply, spare_part=self.part, quantity=10, price=1500
        )
        self.assertEqual(item.sum, Decimal('15000'))

    def test_supply_increases_stock(self):
        """Проверяет что поставка увеличивает остаток."""
        supply = SparePartSupplyV2.objects.create(
            doc_num='SUP-002', supply_dt='2026-01-10', user=self.user
        )
        SparePartSupplyItem.objects.create(
            supply=supply, spare_part=self.part, quantity=5, price=1000,
            expiration_dt='2027-01-01'
        )
        count = SparePartCount.objects.get(spare_part=self.part, expiration_dt='2027-01-01')
        self.assertEqual(count.amount, 5)

    def test_supply_delete_decreases_stock(self):
        """Проверяет что удаление строки поставки уменьшает остаток."""
        supply = SparePartSupplyV2.objects.create(
            doc_num='SUP-003', supply_dt='2026-01-10', user=self.user
        )
        item = SparePartSupplyItem.objects.create(
            supply=supply, spare_part=self.part, quantity=3, price=500,
            expiration_dt='2027-06-01'
        )
        count = SparePartCount.objects.get(spare_part=self.part, expiration_dt='2027-06-01')
        self.assertEqual(count.amount, 3)

        item.delete()
        count.refresh_from_db()
        self.assertEqual(count.amount, 0)

    def test_supply_update_changes_stock(self):
        """Проверяет что обновление количества пересчитывает остаток."""
        supply = SparePartSupplyV2.objects.create(
            doc_num='SUP-004', supply_dt='2026-01-10', user=self.user
        )
        item = SparePartSupplyItem.objects.create(
            supply=supply, spare_part=self.part, quantity=5, price=1000,
            expiration_dt='2027-03-01'
        )
        count = SparePartCount.objects.get(spare_part=self.part, expiration_dt='2027-03-01')
        self.assertEqual(count.amount, 5)

        item.quantity = 8
        item.save()
        count.refresh_from_db()
        self.assertEqual(count.amount, 8)
