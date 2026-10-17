"""Фабрики тестовых данных раздела «Аналитика».

Создают реальные записи через ORM, поэтому сигналы пересчёта контрактов
срабатывают как в проде. Экземпляр `Contract`, переданный в фабрику, после
создания оплат/отгрузок устаревает: вызывайте `refresh_from_db()`.
"""

from itertools import count

from clients.models import Client
from contracts.models import Contract, Payment
from directory.models import City, Unit
from spare_part.models import SparePart, SparePartShipmentM2M, SparePartShipmentV2
from users.models import CompanyUser

_inn_counter = count(1)
_shipment_counter = count(1)


def make_client(name="Клиент", inn=None) -> Client:
    """Клиент с уникальным ИНН (по счётчику). Город общий («Москва»).

    Пара (название, город) уникальна, поэтому нескольким клиентам в одном тесте
    нужны разные названия.
    """
    city, _ = City.objects.get_or_create(name="Москва", region=None)
    if inn is None:
        inn = f"77{next(_inn_counter):010d}"
    return Client.objects.create(name=name, city=city, inn=inn)


def make_contract(client, number, conclusion_date, amount, **fields) -> Contract:
    """Контракт; `fields` — любые дополнительные поля модели."""
    return Contract.objects.create(
        client=client,
        contract_number=number,
        conclusion_date=conclusion_date,
        contract_amount=amount,
        **fields,
    )


def make_payment(contract, date, amount) -> Payment:
    """Оплата по контракту (сигнал пересчитывает контракт)."""
    return Payment.objects.create(contract=contract, date=date, amount=amount)


def make_shipment(contract, shipment_dt, total) -> SparePartShipmentM2M:
    """Отгрузка запчастей на сумму `total`: одна строка, количество 1, цена `total`.

    `contract` может быть None: отгрузка без контракта. Единица «шт.»,
    запчасть и пользователь-отгрузчик создаются по необходимости.
    """
    unit, _ = Unit.objects.get_or_create(
        short_name="шт.", defaults={"full_name": "штука"}
    )
    spare_part, _ = SparePart.objects.get_or_create(
        name="Тестовая запчасть", defaults={"unit": unit}
    )
    user, _ = CompanyUser.objects.get_or_create(username="test_shipper")
    shipment = SparePartShipmentV2.objects.create(
        doc_num=f"ОТ-{next(_shipment_counter)}",
        shipment_dt=shipment_dt,
        user=user,
        contract=contract,
    )
    return SparePartShipmentM2M.objects.create(
        shipment=shipment, spare_part=spare_part, quantity=1, price=total
    )
