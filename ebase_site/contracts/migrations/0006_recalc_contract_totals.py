from decimal import Decimal

from django.db import migrations
from django.db.models import Sum


def recalc_contract_totals(apps, schema_editor):
    """Пересчитывает суммы, долг, прибыль и статус оплаты у всех контрактов.

    Формулы повторяют contracts/signals.py: recalc_contract. Раньше долг не
    пересчитывался при сохранении самого контракта, поэтому в БД остались
    устаревшие значения. У исторических моделей нет методов, поэтому правило
    статуса оплаты (Contract.update_payment_status) продублировано здесь.
    """
    Contract = apps.get_model("contracts", "Contract")
    Payment = apps.get_model("contracts", "Payment")
    ContractExpense = apps.get_model("contracts", "ContractExpense")
    SparePartShipmentM2M = apps.get_model("spare_part", "SparePartShipmentM2M")
    BusinessTripContractExpense = apps.get_model(
        "business_trip", "BusinessTripContractExpense"
    )

    zero = Decimal("0")

    for contract in Contract.objects.all().iterator():
        payment_amount = (
            Payment.objects.filter(contract_id=contract.pk).aggregate(s=Sum("amount"))[
                "s"
            ]
            or zero
        )
        shipment_expenses = (
            SparePartShipmentM2M.objects.filter(
                shipment__contract_id=contract.pk
            ).aggregate(s=Sum("sum"))["s"]
            or zero
        )
        manual_expenses = (
            ContractExpense.objects.filter(contract_id=contract.pk).aggregate(
                s=Sum("sum")
            )["s"]
            or zero
        )
        trip_expenses = (
            BusinessTripContractExpense.objects.filter(
                contract_id=contract.pk
            ).aggregate(s=Sum("amount"))["s"]
            or zero
        )
        expenses_amount = shipment_expenses + manual_expenses + trip_expenses
        contract_amount = contract.contract_amount or zero

        if payment_amount == 0:
            payment_status = "no_receipts"
        elif payment_amount < contract_amount:
            payment_status = "partial"
        else:
            payment_status = "paid"

        Contract.objects.filter(pk=contract.pk).update(
            payment_amount=payment_amount,
            expenses_amount=expenses_amount,
            debt=contract_amount - payment_amount,
            profit=payment_amount - expenses_amount,
            payment_status=payment_status,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0005_alter_contract_payment_status"),
        (
            "spare_part",
            "0008_sparepartshipmentm2m_price_sparepartshipmentm2m_sum_and_more",
        ),
        ("business_trip", "0008_money_receipt"),
    ]

    operations = [
        migrations.RunPython(recalc_contract_totals, migrations.RunPython.noop),
    ]
