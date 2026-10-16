from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from analytics.filters import Period
from analytics.services.finance import (
    TOTAL_KEYS,
    _bucket_by_month,
    concluded_by_month,
    contracts_in_period,
    finance_kpis,
    money_flow,
)
from analytics.tests.factories import (
    make_client,
    make_contract,
    make_payment,
    make_shipment,
)
from business_trip.models import BusinessTrip, BusinessTripContractExpense
from contracts.models import ContractExpense
from users.models import CompanyUser

P = Period(date(2026, 1, 1), date(2026, 12, 31))
EXPECTED_DELTA_KEYS = {*TOTAL_KEYS, "count", "margin_pct"}


class BucketByMonthTests(SimpleTestCase):
    MONTHS = [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]

    def test_sums_values_of_one_month(self):
        pairs = [
            (date(2026, 2, 1), Decimal("10")),
            (date(2026, 2, 28), Decimal("5.5")),
            (date(2026, 3, 31), Decimal("1")),
        ]
        self.assertEqual(
            _bucket_by_month(pairs, self.MONTHS),
            [Decimal("0"), Decimal("15.5"), Decimal("1")],
        )

    def test_ignores_dates_outside_months(self):
        pairs = [
            (date(2025, 12, 31), Decimal("10")),
            (date(2026, 4, 1), Decimal("20")),
            (date(2026, 1, 15), Decimal("3")),
        ]
        self.assertEqual(
            _bucket_by_month(pairs, self.MONTHS),
            [Decimal("3"), Decimal("0"), Decimal("0")],
        )

    def test_empty_input_gives_zeros(self):
        self.assertEqual(_bucket_by_month([], self.MONTHS), [Decimal("0")] * 3)


class FinanceKpisTests(TestCase):
    def test_kpis_match_contract_totals(self):
        client = make_client()
        paid = make_contract(client, "K-1", date(2026, 2, 1), 100000)
        make_payment(paid, date(2026, 2, 10), 30000)
        make_contract(client, "K-2", date(2026, 6, 1), 50000)
        make_contract(client, "K-3", date(2025, 5, 1), 80000)

        k = finance_kpis(P)

        self.assertEqual(k["current"]["count"], 2)
        self.assertEqual(k["current"]["contract_amount"], Decimal("150000"))
        self.assertEqual(k["current"]["payment_amount"], Decimal("30000"))
        self.assertEqual(k["current"]["expenses_amount"], Decimal("0"))
        self.assertEqual(k["current"]["debt"], Decimal("120000"))
        self.assertEqual(k["current"]["profit"], Decimal("30000"))
        # profit 30000 / payment 30000
        self.assertEqual(k["current"]["margin_pct"], Decimal("100.0"))
        self.assertEqual(k["previous"]["count"], 1)
        self.assertEqual(k["previous"]["contract_amount"], Decimal("80000"))
        self.assertIsNone(k["previous"]["margin_pct"])
        self.assertEqual(k["delta_pct"]["contract_amount"], Decimal("87.5"))
        self.assertEqual(k["delta_pct"]["count"], Decimal("100.0"))
        # у прошлого периода нет оплат: дельты по ним и по марже не определены
        self.assertIsNone(k["delta_pct"]["payment_amount"])
        self.assertIsNone(k["delta_pct"]["margin_pct"])
        self.assertEqual(set(k["delta_pct"]), EXPECTED_DELTA_KEYS)

    def test_kpis_client_filter(self):
        alpha = make_client("Альфа")
        beta = make_client("Бета")
        a_now = make_contract(alpha, "A-1", date(2026, 3, 1), 100000)
        make_payment(a_now, date(2026, 3, 5), 40000)
        make_contract(alpha, "A-0", date(2025, 3, 1), 40000)
        make_contract(beta, "B-1", date(2026, 3, 1), 50000)
        make_contract(beta, "B-0", date(2025, 3, 1), 80000)

        k = finance_kpis(P, client=alpha)

        self.assertEqual(k["current"]["count"], 1)
        self.assertEqual(k["current"]["contract_amount"], Decimal("100000"))
        self.assertEqual(k["current"]["payment_amount"], Decimal("40000"))
        self.assertEqual(k["current"]["debt"], Decimal("60000"))
        self.assertEqual(k["previous"]["count"], 1)
        self.assertEqual(k["previous"]["contract_amount"], Decimal("40000"))
        # (100000 - 40000) / 40000 * 100
        self.assertEqual(k["delta_pct"]["contract_amount"], Decimal("150.0"))

    def test_kpis_empty_period(self):
        k = finance_kpis(P)

        for totals in (k["current"], k["previous"]):
            self.assertEqual(totals["count"], 0)
            for key in TOTAL_KEYS:
                self.assertEqual(totals[key], Decimal("0"))
            self.assertIsNone(totals["margin_pct"])
        self.assertEqual(set(k["delta_pct"]), EXPECTED_DELTA_KEYS)
        self.assertTrue(all(v is None for v in k["delta_pct"].values()))

    def test_margin_and_its_delta_in_percentage_points(self):
        client = make_client()
        # прошлый год: оплачено 80000, затраты 40000 -> маржа 50.0 %
        old = make_contract(client, "M-0", date(2025, 4, 1), 80000)
        make_payment(old, date(2025, 4, 10), 80000)
        ContractExpense.objects.create(
            contract=old, expense_type="other", quantity=1, cost=40000
        )
        # этот год: оплачено 30000, затрат нет -> маржа 100.0 %
        new = make_contract(client, "M-1", date(2026, 4, 1), 100000)
        make_payment(new, date(2026, 4, 10), 30000)

        k = finance_kpis(P)

        self.assertEqual(k["previous"]["margin_pct"], Decimal("50.0"))
        self.assertEqual(k["current"]["margin_pct"], Decimal("100.0"))
        self.assertEqual(k["delta_pct"]["margin_pct"], Decimal("50.0"))

    def test_margin_rounded_to_tenth_half_up(self):
        client = make_client()
        contract = make_contract(client, "R-1", date(2026, 4, 1), 100000)
        make_payment(contract, date(2026, 4, 10), 2000)
        ContractExpense.objects.create(
            contract=contract, expense_type="other", quantity=1, cost=1999
        )

        k = finance_kpis(P)

        # profit 1 / payment 2000 * 100 = 0.05 -> 0.1 (не банковское округление)
        self.assertEqual(k["current"]["margin_pct"], Decimal("0.1"))

    def test_margin_of_mixed_contracts(self):
        client = make_client()
        profitable = make_contract(client, "R-2", date(2026, 4, 1), 100000)
        make_payment(profitable, date(2026, 4, 10), 8000)
        ContractExpense.objects.create(
            contract=profitable, expense_type="other", quantity=1, cost=2000
        )
        loss = make_contract(client, "R-3", date(2026, 5, 1), 100000)
        make_payment(loss, date(2026, 5, 10), 4000)
        ContractExpense.objects.create(
            contract=loss, expense_type="other", quantity=1, cost=8000
        )

        k = finance_kpis(P)

        # оплачено 12000, прибыль 6000 + (-4000) = 2000 -> 16.666... -> 16.7
        self.assertEqual(k["current"]["margin_pct"], Decimal("16.7"))

    def test_delta_rounded_half_up_and_uses_abs_of_previous(self):
        client = make_client()
        make_contract(client, "D-0", date(2025, 4, 1), 400)
        make_contract(client, "D-1", date(2026, 4, 1), 449)

        k = finance_kpis(P)

        # (449 - 400) / 400 * 100 = 12.25 -> 12.3 (не банковское округление)
        self.assertEqual(k["delta_pct"]["contract_amount"], Decimal("12.3"))

    def test_delta_with_negative_previous_uses_abs(self):
        client = make_client()
        # прошлый год: прибыль -1000 (затраты без оплат)
        old = make_contract(client, "N-0", date(2025, 4, 1), 5000)
        ContractExpense.objects.create(
            contract=old, expense_type="other", quantity=1, cost=1000
        )
        # этот год: прибыль 500
        new = make_contract(client, "N-1", date(2026, 4, 1), 5000)
        make_payment(new, date(2026, 4, 10), 500)

        k = finance_kpis(P)

        self.assertEqual(k["previous"]["profit"], Decimal("-1000"))
        # (500 - (-1000)) / |-1000| * 100 = 150
        self.assertEqual(k["delta_pct"]["profit"], Decimal("150.0"))

    def test_contracts_in_period_boundaries_and_client(self):
        alpha = make_client("Альфа")
        beta = make_client("Бета")
        first = make_contract(alpha, "C-1", date(2026, 1, 1), 1)
        last = make_contract(alpha, "C-2", date(2026, 12, 31), 1)
        make_contract(alpha, "C-3", date(2025, 12, 31), 1)
        make_contract(alpha, "C-4", date(2027, 1, 1), 1)
        other = make_contract(beta, "C-5", date(2026, 6, 1), 1)

        self.assertCountEqual(contracts_in_period(P), [first, last, other])
        self.assertCountEqual(contracts_in_period(P, alpha), [first, last])


class MoneyFlowTests(TestCase):
    def _trip(self, employee, beg, end):
        """Командировка без контрактов: сигналы не создают долей."""
        return BusinessTrip.objects.create(employee=employee, beg_dt=beg, end_dt=end)

    def test_money_flow_by_actual_dates(self):
        client = make_client()
        contract = make_contract(client, "F-1", date(2025, 12, 20), 100000)
        make_payment(contract, date(2026, 2, 10), 40000)
        make_shipment(contract, date(2026, 3, 5), 1000)
        make_shipment(None, date(2026, 3, 6), 999)  # без контракта: не учитывается
        expense = ContractExpense.objects.create(
            contract=contract, expense_type="other", quantity=1, cost=500
        )
        # дата расхода пуста, дата создания в марте 2026 (середина месяца, без сдвигов зон)
        ContractExpense.objects.filter(pk=expense.pk).update(
            create_dt=datetime(2026, 3, 15, 12, 0, tzinfo=dt_timezone.utc)
        )
        employee = CompanyUser.objects.create_user(username="traveller")
        trip = self._trip(employee, date(2026, 4, 1), date(2026, 4, 2))
        BusinessTripContractExpense.objects.create(
            business_trip=trip, contract=contract, amount=300
        )

        f = money_flow(P)

        self.assertEqual(len(f["months"]), 12)
        for key in ("inflow", "spare_parts", "trips", "other", "outflow", "balance"):
            self.assertEqual(len(f[key]), 12, key)
        self.assertEqual(f["inflow"][1], Decimal("40000"))
        self.assertEqual(f["spare_parts"][2], Decimal("1000"))
        self.assertEqual(f["other"][2], Decimal("500"))
        self.assertEqual(f["trips"][3], Decimal("300"))
        self.assertEqual(f["outflow"][2], Decimal("1500"))
        self.assertEqual(f["balance"][2], Decimal("-1500"))
        self.assertEqual(f["balance"][1], Decimal("40000"))
        self.assertEqual(f["balance"][3], Decimal("-300"))
        self.assertEqual(sum(f["inflow"]), Decimal("40000"))
        self.assertEqual(sum(f["outflow"]), Decimal("1800"))

    def test_expense_with_date_ignores_create_dt(self):
        client = make_client()
        contract = make_contract(client, "F-2", date(2026, 1, 1), 1000)
        expense = ContractExpense.objects.create(
            contract=contract,
            expense_type="other",
            quantity=2,
            cost=100,
            date=date(2026, 5, 20),
        )
        ContractExpense.objects.filter(pk=expense.pk).update(
            create_dt=datetime(2026, 3, 15, 12, 0, tzinfo=dt_timezone.utc)
        )

        f = money_flow(P)

        self.assertEqual(f["other"][4], Decimal("200"))
        self.assertEqual(f["other"][2], Decimal("0"))

    def test_expense_create_dt_uses_local_date(self):
        # 31 марта 22:30 UTC = 1 апреля 01:30 по Москве
        client = make_client()
        contract = make_contract(client, "F-3", date(2026, 1, 1), 1000)
        expense = ContractExpense.objects.create(
            contract=contract, expense_type="other", quantity=1, cost=70
        )
        ContractExpense.objects.filter(pk=expense.pk).update(
            create_dt=datetime(2026, 3, 31, 22, 30, tzinfo=dt_timezone.utc)
        )

        f = money_flow(P)

        self.assertEqual(f["other"][2], Decimal("0"))
        self.assertEqual(f["other"][3], Decimal("70"))

    def test_values_outside_period_are_ignored(self):
        client = make_client()
        contract = make_contract(client, "F-4", date(2025, 1, 1), 100000)
        make_payment(contract, date(2025, 12, 31), 1000)
        make_payment(contract, date(2027, 1, 1), 2000)
        make_shipment(contract, date(2025, 12, 31), 300)
        expense = ContractExpense.objects.create(
            contract=contract, expense_type="other", quantity=1, cost=50
        )
        ContractExpense.objects.filter(pk=expense.pk).update(
            create_dt=datetime(2025, 12, 31, 12, 0, tzinfo=dt_timezone.utc)
        )
        employee = CompanyUser.objects.create_user(username="traveller")
        trip = self._trip(employee, date(2027, 1, 1), date(2027, 1, 2))
        BusinessTripContractExpense.objects.create(
            business_trip=trip, contract=contract, amount=900
        )

        f = money_flow(P)

        for key in ("inflow", "spare_parts", "trips", "other", "outflow", "balance"):
            self.assertEqual(f[key], [Decimal("0")] * 12, key)

    def test_money_flow_client_filter(self):
        alpha = make_client("Альфа")
        beta = make_client("Бета")
        a = make_contract(alpha, "FA-1", date(2026, 1, 10), 100000)
        b = make_contract(beta, "FB-1", date(2026, 1, 10), 100000)
        employee = CompanyUser.objects.create_user(username="traveller")
        for contract, payment, shipment, expense, trip_share in (
            (a, 1000, 100, 10, 1),
            (b, 2000, 200, 20, 2),
        ):
            make_payment(contract, date(2026, 2, 10), payment)
            make_shipment(contract, date(2026, 2, 11), shipment)
            ContractExpense.objects.create(
                contract=contract,
                expense_type="other",
                quantity=1,
                cost=expense,
                date=date(2026, 2, 12),
            )
            trip = self._trip(employee, date(2026, 2, 13), date(2026, 2, 14))
            BusinessTripContractExpense.objects.create(
                business_trip=trip, contract=contract, amount=trip_share
            )

        only_a = money_flow(P, client=alpha)
        total = money_flow(P)

        self.assertEqual(only_a["inflow"][1], Decimal("1000"))
        self.assertEqual(only_a["spare_parts"][1], Decimal("100"))
        self.assertEqual(only_a["other"][1], Decimal("10"))
        self.assertEqual(only_a["trips"][1], Decimal("1"))
        self.assertEqual(only_a["balance"][1], Decimal("889"))
        self.assertEqual(total["inflow"][1], Decimal("3000"))
        self.assertEqual(total["outflow"][1], Decimal("333"))

    def test_money_flow_empty_db(self):
        f = money_flow(P)

        self.assertEqual(len(f["months"]), 12)
        self.assertEqual(f["balance"], [Decimal("0")] * 12)


class ConcludedByMonthTests(TestCase):
    def test_concluded_by_month_cumulative(self):
        client = make_client()
        make_contract(client, "Z-1", date(2026, 1, 15), 100000)
        make_contract(client, "Z-2", date(2026, 3, 1), 50000)
        make_contract(client, "Z-3", date(2025, 12, 31), 7000)  # вне периода

        r = concluded_by_month(P)

        self.assertEqual(len(r["months"]), 12)
        self.assertEqual(r["amount"][0], Decimal("100000"))
        self.assertEqual(r["amount"][1], Decimal("0"))
        self.assertEqual(r["amount"][2], Decimal("50000"))
        self.assertEqual(r["cumulative"][0], Decimal("100000"))
        self.assertEqual(r["cumulative"][1], Decimal("100000"))
        self.assertEqual(r["cumulative"][2], Decimal("150000"))
        self.assertEqual(r["cumulative"][11], Decimal("150000"))

    def test_concluded_by_month_client_filter(self):
        alpha = make_client("Альфа")
        beta = make_client("Бета")
        make_contract(alpha, "ZA-1", date(2026, 2, 1), 100)
        make_contract(beta, "ZB-1", date(2026, 2, 1), 900)

        r = concluded_by_month(P, client=alpha)

        self.assertEqual(r["amount"][1], Decimal("100"))
        self.assertEqual(r["cumulative"][11], Decimal("100"))

    def test_concluded_by_month_empty(self):
        r = concluded_by_month(P)

        self.assertEqual(r["amount"], [Decimal("0")] * 12)
        self.assertEqual(r["cumulative"], [Decimal("0")] * 12)
