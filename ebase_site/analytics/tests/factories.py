"""Фабрики тестовых данных раздела «Аналитика».

Создают реальные записи через ORM, поэтому сигналы пересчёта контрактов
срабатывают как в проде. Экземпляр `Contract`, переданный в фабрику, после
создания оплат/отгрузок устаревает: вызывайте `refresh_from_db()`.
"""

from itertools import count

from business_trip.models import (
    BusinessTrip,
    BusinessTripDestination,
    BusinessTripExpense,
    ExpenseType,
    MoneyReceipt,
)
from clients.models import Client, Department
from contracts.models import Contract, Payment
from directory.models import City, ServiceType, Unit
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


_DEFAULT = object()


def make_employee(
    username="ivanov", last_name="Иванов", first_name="Иван", patron="Иванович"
) -> CompanyUser:
    """Сотрудник с ФИО."""
    return CompanyUser.objects.create_user(
        username, last_name=last_name, first_name=first_name, patron=patron
    )


def make_city(name="Казань", region="Татарстан") -> City:
    """Город (пара «город, регион» уникальна — берётся существующий)."""
    city, _ = City.objects.get_or_create(name=name, region=region)
    return city


def make_department(name, client=None, city=_DEFAULT, address=None) -> Department:
    """Подразделение. По умолчанию город — Казань; `city=None` — без города."""
    if city is _DEFAULT:
        city = make_city()
    return Department.objects.create(
        name=name,
        address=address or f"адрес {name}",
        client=client,
        city=city,
    )


def make_trip(
    employee,
    beg,
    end,
    *,
    destinations=(),
    expenses=(),
    service_types=(),
    contracts=(),
) -> BusinessTrip:
    """Командировка с пунктами, затратами, видами работ и контрактами.

    `destinations` — кортежи (подразделение, дата прибытия, дата выбытия);
    `expenses` — кортежи (вид затрат, дата, сумма); `service_types` — имена
    видов работ. Контракты добавляются последними: сигналы пересчитают доли.
    """
    trip = BusinessTrip.objects.create(employee=employee, beg_dt=beg, end_dt=end)
    for department, dest_beg, dest_end in destinations:
        BusinessTripDestination.objects.create(
            business_trip=trip, department=department, beg_dt=dest_beg, end_dt=dest_end
        )
    for type_name, day, amount in expenses:
        expense_type, _ = ExpenseType.objects.get_or_create(name=type_name)
        BusinessTripExpense.objects.create(
            business_trip=trip, expense_type=expense_type, date=day, amount=amount
        )
    for name in service_types:
        service_type, _ = ServiceType.objects.get_or_create(name=name)
        trip.service_type.add(service_type)
    if contracts:
        trip.contract.add(*contracts)
    return trip


def make_receipt(employee, receipt_date, amount) -> MoneyReceipt:
    """Поступление ДС сотруднику."""
    return MoneyReceipt.objects.create(
        employee=employee, receipt_date=receipt_date, amount=amount
    )
