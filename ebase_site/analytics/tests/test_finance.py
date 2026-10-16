from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from analytics.filters import Period
from analytics.services.finance import (
    AGING_BUCKETS,
    TOTAL_KEYS,
    _bucket_by_month,
    client_profitability,
    concluded_by_month,
    contracts_in_period,
    contracts_scatter,
    debt_aging,
    finance_kpis,
    money_flow,
    payment_discipline,
    status_matrix,
    top_clients,
)
from analytics.tests.factories import (
    make_client,
    make_contract,
    make_payment,
    make_shipment,
)
from business_trip.models import BusinessTrip, BusinessTripContractExpense
from contracts.models import Contract, ContractExpense
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


TODAY = date(2026, 10, 16)


class DebtAgingTests(TestCase):
    def _aging(self, today=TODAY, client=None):
        return {b["key"]: b for b in debt_aging(today, client)}

    def test_debt_aging_buckets(self):
        client = make_client()
        recent = make_contract(
            client, "A-1", date(2026, 1, 1), 1000, service_end_date=date(2026, 10, 1)
        )  # 15 дн.
        old = make_contract(
            client, "A-2", date(2026, 1, 1), 2500, service_end_date=date(2026, 6, 1)
        )  # 137 дн.

        a = self._aging()

        self.assertEqual(a["0_30"]["count"], 1)
        self.assertEqual(a["0_30"]["amount"], Decimal("1000"))
        self.assertEqual(a["0_30"]["ids"], [str(recent.pk)])
        self.assertEqual(a["91_180"]["count"], 1)
        self.assertEqual(a["91_180"]["amount"], Decimal("2500"))
        self.assertEqual(a["91_180"]["ids"], [str(old.pk)])
        for key in ("not_due", "31_90", "180_plus"):
            self.assertEqual(a[key]["count"], 0, key)
            self.assertEqual(a[key]["amount"], Decimal("0"), key)
            self.assertEqual(a[key]["ids"], [], key)

    def test_debt_aging_all_buckets_always_present_in_order(self):
        result = debt_aging(TODAY)

        self.assertEqual([(b["key"], b["label"]) for b in result], list(AGING_BUCKETS))
        for bucket in result:
            self.assertEqual(bucket["count"], 0)
            self.assertEqual(bucket["amount"], Decimal("0"))
            self.assertEqual(bucket["ids"], [])

    def test_debt_aging_bucket_boundaries(self):
        client = make_client()
        # возраст в днях -> ожидаемая корзина
        cases = [
            (-1, "not_due"),
            (0, "0_30"),
            (30, "0_30"),
            (31, "31_90"),
            (90, "31_90"),
            (91, "91_180"),
            (180, "91_180"),
            (181, "180_plus"),
        ]
        by_age = {}
        for age, _ in cases:
            by_age[age] = make_contract(
                client,
                f"B-{age}",
                date(2020, 1, 1),
                100,
                service_end_date=TODAY - timedelta(days=age),
            )

        a = self._aging()

        for age, key in cases:
            self.assertIn(str(by_age[age].pk), a[key]["ids"], f"{age} дн. -> {key}")
        for bucket in a.values():
            self.assertEqual(bucket["count"], len(bucket["ids"]))
        self.assertEqual(sum(b["count"] for b in a.values()), len(cases))

    def test_debt_aging_future_end_date(self):
        client = make_client()
        contract = make_contract(
            client, "F-1", date(2026, 1, 1), 700, service_end_date=date(2026, 12, 31)
        )

        a = self._aging()

        self.assertEqual(a["not_due"]["count"], 1)
        self.assertEqual(a["not_due"]["amount"], Decimal("700"))
        self.assertEqual(a["not_due"]["ids"], [str(contract.pk)])
        self.assertEqual(sum(b["count"] for b in a.values()), 1)

    def test_debt_aging_falls_back_to_conclusion_date(self):
        client = make_client()
        contract = make_contract(
            client, "C-1", date(2026, 3, 1), 900, service_end_date=None
        )

        a = self._aging()

        # 2026-03-01 -> 2026-10-16 = 229 дн.
        self.assertEqual(a["180_plus"]["count"], 1)
        self.assertEqual(a["180_plus"]["ids"], [str(contract.pk)])

    def test_debt_aging_skips_paid(self):
        client = make_client()
        paid = make_contract(
            client, "P-1", date(2026, 1, 1), 1000, service_end_date=date(2026, 10, 1)
        )
        make_payment(paid, date(2026, 10, 5), 1000)
        debtor = make_contract(
            client, "P-2", date(2026, 1, 1), 400, service_end_date=date(2026, 10, 1)
        )
        make_payment(debtor, date(2026, 10, 5), 100)

        a = self._aging()

        paid.refresh_from_db()
        self.assertEqual(paid.debt, Decimal("0"))
        self.assertEqual(a["0_30"]["count"], 1)
        self.assertEqual(a["0_30"]["ids"], [str(debtor.pk)])
        # в корзине остаток долга, а не сумма контракта
        self.assertEqual(a["0_30"]["amount"], Decimal("300"))
        self.assertEqual(sum(b["count"] for b in a.values()), 1)

    def test_debt_aging_ignores_period_and_sums_amount(self):
        client = make_client()
        # контракты заключены в разные годы: период на возраст долга не влияет
        make_contract(
            client, "S-1", date(2020, 1, 1), 100, service_end_date=date(2026, 10, 1)
        )
        make_contract(
            client, "S-2", date(2026, 5, 1), 250, service_end_date=date(2026, 9, 20)
        )

        a = self._aging()

        self.assertEqual(a["0_30"]["count"], 2)
        self.assertEqual(a["0_30"]["amount"], Decimal("350"))
        self.assertIsInstance(a["0_30"]["amount"], Decimal)

    def test_debt_aging_client_filter(self):
        alpha = make_client("Альфа")
        beta = make_client("Бета")
        mine = make_contract(
            alpha, "CF-1", date(2026, 1, 1), 100, service_end_date=date(2026, 10, 1)
        )
        make_contract(
            beta, "CF-2", date(2026, 1, 1), 900, service_end_date=date(2026, 10, 1)
        )

        only_alpha = self._aging(client=alpha)
        everyone = self._aging()

        self.assertEqual(only_alpha["0_30"]["ids"], [str(mine.pk)])
        self.assertEqual(only_alpha["0_30"]["amount"], Decimal("100"))
        self.assertEqual(sum(b["count"] for b in only_alpha.values()), 1)
        self.assertEqual(everyone["0_30"]["count"], 2)
        self.assertEqual(everyone["0_30"]["amount"], Decimal("1000"))


class StatusMatrixTests(TestCase):
    @staticmethod
    def _cells(matrix):
        """{(строка, столбец): (count, amount)} для удобных проверок."""
        return {
            (row["key"], cell["payment_status"]): (cell["count"], cell["amount"])
            for row in matrix["rows"]
            for cell in row["cells"]
        }

    def test_status_matrix_counts(self):
        client = make_client()
        make_contract(
            client, "M-1", date(2026, 2, 1), 100000, services_provided="fully"
        )  # fully + no_receipts
        done = make_contract(client, "M-2", date(2026, 3, 1), 40000)  # not_yet
        make_payment(done, date(2026, 3, 10), 40000)  # paid

        m = status_matrix(P)

        self.assertEqual(len(m["rows"]), 3)
        self.assertEqual(len(m["columns"]), 3)
        for row in m["rows"]:
            self.assertEqual(len(row["cells"]), 3)
        cells = self._cells(m)
        filled = {("fully", "no_receipts"), ("not_yet", "paid")}
        self.assertEqual(cells[("fully", "no_receipts")], (1, Decimal("100000")))
        self.assertEqual(cells[("not_yet", "paid")], (1, Decimal("40000")))
        empty = {key: value for key, value in cells.items() if key not in filled}
        self.assertEqual(len(empty), 7)
        for key, value in empty.items():
            self.assertEqual(value, (0, Decimal("0")), key)

    def test_status_matrix_structure_follows_choices_order(self):
        m = status_matrix(P)

        self.assertEqual(
            [(c["key"], c["label"]) for c in m["columns"]],
            Contract.PAYMENT_STATUS_CHOICES,
        )
        self.assertEqual(
            [(r["key"], r["label"]) for r in m["rows"]],
            Contract.SERVICES_PROVIDED_CHOICES,
        )
        column_keys = [key for key, _ in Contract.PAYMENT_STATUS_CHOICES]
        for row in m["rows"]:
            self.assertEqual(
                [cell["payment_status"] for cell in row["cells"]], column_keys
            )
            for cell in row["cells"]:
                self.assertEqual(cell["count"], 0)
                self.assertEqual(cell["amount"], Decimal("0"))

    def test_status_matrix_sums_amount_and_counts_in_one_cell(self):
        client = make_client()
        make_contract(
            client, "MS-1", date(2026, 2, 1), 100, services_provided="partially"
        )
        make_contract(
            client, "MS-2", date(2026, 7, 1), 250, services_provided="partially"
        )
        part = make_contract(
            client, "MS-3", date(2026, 8, 1), 1000, services_provided="partially"
        )
        make_payment(part, date(2026, 8, 5), 300)  # partial

        cells = self._cells(status_matrix(P))

        self.assertEqual(cells[("partially", "no_receipts")], (2, Decimal("350")))
        self.assertEqual(cells[("partially", "partial")], (1, Decimal("1000")))

    def test_status_matrix_period_and_client_filter(self):
        alpha = make_client("Альфа")
        beta = make_client("Бета")
        make_contract(alpha, "MF-1", date(2026, 2, 1), 100)
        make_contract(alpha, "MF-2", date(2025, 12, 31), 7000)  # вне периода
        make_contract(beta, "MF-3", date(2026, 2, 1), 900)

        everyone = self._cells(status_matrix(P))
        only_alpha = self._cells(status_matrix(P, client=alpha))

        self.assertEqual(everyone[("not_yet", "no_receipts")], (2, Decimal("1000")))
        self.assertEqual(only_alpha[("not_yet", "no_receipts")], (1, Decimal("100")))


def make_expense(contract, cost):
    """Ручной расход на контракт (сигнал пересчитывает прибыль)."""
    return ContractExpense.objects.create(
        contract=contract, expense_type="other", quantity=1, cost=cost
    )


class TopClientsTests(TestCase):
    def _paid(self, client, number, amount, conclusion=date(2026, 3, 1)):
        contract = make_contract(client, number, conclusion, amount)
        make_payment(contract, conclusion, amount)
        return contract

    def test_top_clients_pareto(self):
        alpha = make_client("Альфа")
        beta = make_client("Бета")
        gamma = make_client("Гамма")
        # у «Альфы» два контракта: 4000 + 2000 = 6000
        self._paid(alpha, "T-1", 4000)
        self._paid(alpha, "T-2", 2000)
        self._paid(beta, "T-3", 3000)
        self._paid(gamma, "T-4", 1000)
        # вне периода не учитывается
        self._paid(gamma, "T-5", 50000, conclusion=date(2025, 12, 31))

        result = top_clients(P)

        self.assertEqual(
            [c["name"] for c in result["clients"]], ["Альфа", "Бета", "Гамма"]
        )
        self.assertEqual(
            [c["id"] for c in result["clients"]],
            [str(alpha.pk), str(beta.pk), str(gamma.pk)],
        )
        self.assertEqual(
            [c["amount"] for c in result["clients"]],
            [Decimal("6000"), Decimal("3000"), Decimal("1000")],
        )
        self.assertEqual(
            [c["cumulative_pct"] for c in result["clients"]],
            [Decimal("60.0"), Decimal("90.0"), Decimal("100.0")],
        )
        self.assertEqual(result["total"], Decimal("10000"))
        self.assertEqual(result["clients_total"], 3)
        self.assertEqual(result["clients_for_80"], 2)

    def test_top_clients_excludes_zero(self):
        paid = make_client("Оплативший")
        unpaid = make_client("Без оплат")
        self._paid(paid, "Z-1", 500)
        make_contract(unpaid, "Z-2", date(2026, 3, 1), 9000)

        result = top_clients(P)

        self.assertEqual([c["name"] for c in result["clients"]], ["Оплативший"])
        self.assertEqual(result["clients_total"], 1)
        self.assertEqual(result["total"], Decimal("500"))
        self.assertEqual(result["clients_for_80"], 1)

    def test_top_clients_excludes_negative_sums(self):
        paid = make_client("Оплативший")
        refunded = make_client("Возврат")
        self._paid(paid, "NEG-1", 800)
        refund = make_contract(refunded, "NEG-2", date(2026, 3, 1), 9000)
        make_payment(refund, date(2026, 3, 2), -500)  # возврат: сумма клиента < 0

        result = top_clients(P)

        self.assertEqual([c["name"] for c in result["clients"]], ["Оплативший"])
        self.assertEqual(
            [c["cumulative_pct"] for c in result["clients"]], [Decimal("100.0")]
        )
        self.assertEqual(result["total"], Decimal("800"))
        self.assertEqual(result["clients_total"], 1)
        self.assertEqual(result["clients_for_80"], 1)

    def test_top_clients_limit_keeps_totals_over_all_clients(self):
        for name, amount in [("К1", 4000), ("К2", 3000), ("К3", 2000), ("К4", 1000)]:
            self._paid(make_client(name), f"L-{name}", amount)

        result = top_clients(P, limit=2)

        self.assertEqual([c["name"] for c in result["clients"]], ["К1", "К2"])
        # доли считаются от суммы по всем клиентам (10000), а не по первым двум
        self.assertEqual(
            [c["cumulative_pct"] for c in result["clients"]],
            [Decimal("40.0"), Decimal("70.0")],
        )
        self.assertEqual(result["total"], Decimal("10000"))
        self.assertEqual(result["clients_total"], 4)
        # 40 + 30 + 20 = 90 >= 80: три клиента, хотя в списке только два
        self.assertEqual(result["clients_for_80"], 3)

    def test_top_clients_for_80_reached_exactly(self):
        for name, amount in [("К1", 5000), ("К2", 3000), ("К3", 2000)]:
            self._paid(make_client(name), f"E-{name}", amount)

        # 50 + 30 = ровно 80 %
        self.assertEqual(top_clients(P)["clients_for_80"], 2)

    def test_top_clients_for_80_uses_unrounded_share(self):
        self._paid(make_client("К1"), "U-1", 7996)
        self._paid(make_client("К2"), "U-2", 2004)

        result = top_clients(P)

        # 79,96 % округляется до 80,0, но порога ещё не достигает
        self.assertEqual(result["clients"][0]["cumulative_pct"], Decimal("80.0"))
        self.assertEqual(result["clients_for_80"], 2)

    def test_top_clients_cumulative_rounded_half_up(self):
        self._paid(make_client("К1"), "H-1", 125)
        self._paid(make_client("К2"), "H-2", 9875)

        result = top_clients(P)

        # 9875 / 10000 = 98,75 % -> 98,8 (не банковское округление)
        self.assertEqual(
            [c["cumulative_pct"] for c in result["clients"]],
            [Decimal("98.8"), Decimal("100.0")],
        )

    def test_top_clients_equal_amounts_sorted_by_name(self):
        self._paid(make_client("Яблоко"), "S-1", 1000)
        self._paid(make_client("Арбуз"), "S-2", 1000)

        names = [c["name"] for c in top_clients(P)["clients"]]

        self.assertEqual(names, ["Арбуз", "Яблоко"])

    def test_top_clients_empty_period(self):
        self.assertEqual(
            top_clients(P),
            {
                "clients": [],
                "total": Decimal("0"),
                "clients_total": 0,
                "clients_for_80": 0,
            },
        )


class ClientProfitabilityTests(TestCase):
    def _profit(self, client, number, payment, expense=0, conclusion=date(2026, 3, 1)):
        contract = make_contract(client, number, conclusion, 100000)
        make_payment(contract, conclusion, payment)
        if expense:
            make_expense(contract, expense)
        return contract

    def test_client_profitability_split(self):
        top = make_client("Лидер")
        mid = make_client("Середняк")
        bad = make_client("Убыточный")
        self._profit(top, "P-1", 800, expense=300)  # +500
        self._profit(mid, "P-2", 100)  # +100
        self._profit(bad, "P-3", 100, expense=300)  # -200

        result = client_profitability(P)

        self.assertEqual(
            result["best"],
            [
                {"id": str(top.pk), "name": "Лидер", "profit": Decimal("500")},
                {"id": str(mid.pk), "name": "Середняк", "profit": Decimal("100")},
            ],
        )
        self.assertEqual(
            result["losers"],
            [{"id": str(bad.pk), "name": "Убыточный", "profit": Decimal("-200")}],
        )

    def test_client_profitability_sums_contracts_per_client_in_period(self):
        mixed = make_client("Смешанный")
        self._profit(mixed, "Q-1", 1000)  # +1000
        self._profit(mixed, "Q-2", 100, expense=400)  # -300
        # вне периода не учитывается
        self._profit(mixed, "Q-3", 9000, conclusion=date(2025, 12, 31))

        result = client_profitability(P)

        self.assertEqual([c["profit"] for c in result["best"]], [Decimal("700")])
        self.assertEqual(result["losers"], [])

    def test_client_profitability_zero_profit_in_neither_list(self):
        client = make_client("Нулевой")
        self._profit(client, "ZP-1", 500, expense=500)  # 0
        make_contract(make_client("Без оплат"), "ZP-2", date(2026, 3, 1), 777)  # 0

        result = client_profitability(P)

        self.assertEqual(result, {"best": [], "losers": []})

    def test_client_profitability_limit_applies_to_best_only(self):
        for index, profit in enumerate([100, 400, 300, 200], start=1):
            self._profit(make_client(f"Плюс {index}"), f"B-{index}", profit)
        for index, loss in enumerate([50, 150, 100], start=1):
            self._profit(
                make_client(f"Минус {index}"), f"W-{index}", 10, expense=10 + loss
            )

        result = client_profitability(P, limit=2)

        self.assertEqual(
            [c["profit"] for c in result["best"]], [Decimal("400"), Decimal("300")]
        )
        # убыточные показываются все, от худшего к лучшему
        self.assertEqual(
            [c["profit"] for c in result["losers"]],
            [Decimal("-150"), Decimal("-100"), Decimal("-50")],
        )

    def test_client_profitability_equal_profit_sorted_by_name(self):
        self._profit(make_client("Яблоко"), "N-1", 100)
        self._profit(make_client("Арбуз"), "N-2", 100)

        self._profit(make_client("Волк"), "N-3", 10, expense=110)
        self._profit(make_client("Бобр"), "N-4", 10, expense=110)

        result = client_profitability(P)

        self.assertEqual([c["name"] for c in result["best"]], ["Арбуз", "Яблоко"])
        self.assertEqual([c["name"] for c in result["losers"]], ["Бобр", "Волк"])

    def test_client_profitability_empty_period(self):
        self.assertEqual(client_profitability(P), {"best": [], "losers": []})


class ContractsScatterTests(TestCase):
    def test_contracts_scatter_skips_unpaid(self):
        client = make_client("Альфа")
        paid = make_contract(client, "SC-1", date(2026, 3, 1), 100000)
        make_payment(paid, date(2026, 3, 5), 3000)
        make_expense(paid, 1000)
        make_contract(client, "SC-2", date(2026, 4, 1), 50000)  # без оплат

        result = contracts_scatter(P)

        # прибыль 3000 - 1000 = 2000; 2000 / 3000 * 100 = 66.666... -> 66.7
        self.assertEqual(
            result,
            [
                {
                    "id": str(paid.pk),
                    "label": "SC-1 — Альфа",
                    "x": Decimal("100000"),
                    "y": Decimal("66.7"),
                }
            ],
        )

    def test_contracts_scatter_negative_margin(self):
        client = make_client("Альфа")
        loss = make_contract(client, "SN-1", date(2026, 3, 1), 10000)
        make_payment(loss, date(2026, 3, 5), 400)
        make_expense(loss, 500)

        (point,) = contracts_scatter(P)

        # прибыль -100; -100 / 400 * 100 = -25
        self.assertEqual(point["y"], Decimal("-25.0"))

    def test_contracts_scatter_y_matches_kpi_margin(self):
        client = make_client("Альфа")
        contract = make_contract(client, "SK-1", date(2026, 3, 1), 100000)
        make_payment(contract, date(2026, 3, 5), 2000)
        make_expense(contract, 1999)

        (point,) = contracts_scatter(P)

        # прибыль 1 / оплата 2000 * 100 = 0.05 -> 0.1 (как в плитке)
        self.assertEqual(point["y"], Decimal("0.1"))
        self.assertEqual(point["y"], finance_kpis(P)["current"]["margin_pct"])

    def test_contracts_scatter_period_and_client_filter(self):
        alpha = make_client("Альфа")
        beta = make_client("Бета")
        for client, number, conclusion in [
            (alpha, "SF-1", date(2026, 3, 1)),
            (beta, "SF-2", date(2026, 3, 2)),
            (alpha, "SF-3", date(2025, 12, 31)),  # вне периода
        ]:
            contract = make_contract(client, number, conclusion, 1000)
            make_payment(contract, conclusion, 100)

        def labels(points):
            return [point["label"] for point in points]

        self.assertEqual(labels(contracts_scatter(P)), ["SF-1 — Альфа", "SF-2 — Бета"])
        self.assertEqual(labels(contracts_scatter(P, client=beta)), ["SF-2 — Бета"])

    def test_contracts_scatter_reads_client_name_without_extra_queries(self):
        for index in range(3):
            client = make_client(f"Клиент {index}")
            contract = make_contract(client, f"SQ-{index}", date(2026, 3, 1), 1000)
            make_payment(contract, date(2026, 3, 2), 100)

        with self.assertNumQueries(1):
            points = contracts_scatter(P)

        self.assertEqual(len(points), 3)

    def test_contracts_scatter_empty_period(self):
        self.assertEqual(contracts_scatter(P), [])


class PaymentDisciplineTests(TestCase):
    def _paid(
        self, client, number, end_date, payment_date, conclusion=None, amount=1000
    ):
        contract = make_contract(
            client,
            number,
            conclusion or date(2026, 1, 15),
            amount,
            service_end_date=end_date,
        )
        make_payment(contract, payment_date, amount)
        return contract

    def test_payment_discipline_days(self):
        client = make_client("Альфа")
        # конец услуг 1 марта, оплата 31 марта: 30 дней
        self._paid(client, "PD-1", date(2026, 3, 1), date(2026, 3, 31))
        # предоплата за 10 дней: -10
        self._paid(client, "PD-2", date(2026, 5, 11), date(2026, 5, 1))

        result = payment_discipline(P)

        self.assertEqual(
            result,
            [
                {
                    "client_id": str(client.pk),
                    "name": "Альфа",
                    "avg_days": Decimal("10.0"),
                    "contracts": 2,
                }
            ],
        )

    def test_payment_discipline_uses_last_payment(self):
        client = make_client("Альфа")
        contract = make_contract(
            client,
            "PL-1",
            date(2026, 1, 15),
            1000,
            service_end_date=date(2026, 2, 1),
        )
        make_payment(contract, date(2026, 2, 5), 400)
        make_payment(contract, date(2026, 2, 21), 600)

        (row,) = payment_discipline(P)

        # последняя оплата 21 февраля: 20 дней
        self.assertEqual(row["avg_days"], Decimal("20.0"))

    def test_payment_discipline_falls_back_to_conclusion_date(self):
        client = make_client("Альфа")
        self._paid(client, "PF-1", None, date(2026, 2, 14), conclusion=date(2026, 2, 4))

        (row,) = payment_discipline(P)

        self.assertEqual(row["avg_days"], Decimal("10.0"))

    def test_payment_discipline_only_paid_contracts(self):
        client = make_client("Альфа")
        self._paid(client, "PP-1", date(2026, 3, 1), date(2026, 3, 11))  # paid: 10
        partial = make_contract(
            client, "PP-2", date(2026, 1, 15), 5000, service_end_date=date(2026, 3, 1)
        )
        make_payment(partial, date(2026, 9, 1), 1000)  # частичная оплата
        make_contract(client, "PP-3", date(2026, 1, 15), 5000)  # без оплат

        (row,) = payment_discipline(P)

        self.assertEqual(row["contracts"], 1)
        self.assertEqual(row["avg_days"], Decimal("10.0"))

    def test_payment_discipline_sorted_by_avg_days_desc_then_name(self):
        slow = make_client("Медленный")
        fast = make_client("Быстрый")
        tie_b = make_client("Яблоко")
        tie_a = make_client("Арбуз")
        self._paid(slow, "PS-1", date(2026, 3, 1), date(2026, 4, 1))  # 31
        self._paid(fast, "PS-2", date(2026, 3, 11), date(2026, 3, 1))  # -10
        self._paid(tie_b, "PS-3", date(2026, 3, 1), date(2026, 3, 6))  # 5
        self._paid(tie_a, "PS-4", date(2026, 3, 1), date(2026, 3, 6))  # 5

        result = payment_discipline(P)

        self.assertEqual(
            [(r["name"], r["avg_days"]) for r in result],
            [
                ("Медленный", Decimal("31.0")),
                ("Арбуз", Decimal("5.0")),
                ("Яблоко", Decimal("5.0")),
                ("Быстрый", Decimal("-10.0")),
            ],
        )

    def test_payment_discipline_avg_rounded_half_up(self):
        client = make_client("Альфа")
        for index, days in enumerate([1, 0, 0, 0], start=1):
            self._paid(
                client,
                f"PR-{index}",
                date(2026, 3, 1),
                date(2026, 3, 1) + timedelta(days=days),
            )

        (row,) = payment_discipline(P)

        # 1 / 4 = 0,25 -> 0,3 (не банковское округление)
        self.assertEqual(row["avg_days"], Decimal("0.3"))
        self.assertEqual(row["contracts"], 4)

    def test_payment_discipline_period_and_client_filter(self):
        alpha = make_client("Альфа")
        beta = make_client("Бета")
        self._paid(alpha, "PC-1", date(2026, 3, 1), date(2026, 3, 11))  # 10
        self._paid(beta, "PC-2", date(2026, 3, 1), date(2026, 3, 21))  # 20
        # заключён вне периода
        self._paid(
            alpha,
            "PC-3",
            date(2025, 11, 1),
            date(2025, 12, 31),
            conclusion=date(2025, 10, 1),
        )

        everyone = {r["name"]: r["avg_days"] for r in payment_discipline(P)}
        only_alpha = payment_discipline(P, client=alpha)

        self.assertEqual(everyone, {"Альфа": Decimal("10.0"), "Бета": Decimal("20.0")})
        self.assertEqual([r["name"] for r in only_alpha], ["Альфа"])
        self.assertEqual(only_alpha[0]["contracts"], 1)

    def test_payment_discipline_one_query(self):
        for index in range(3):
            client = make_client(f"Клиент {index}")
            self._paid(client, f"PQ-{index}", date(2026, 3, 1), date(2026, 3, 11))

        with self.assertNumQueries(1):
            result = payment_discipline(P)

        self.assertEqual(len(result), 3)

    def test_payment_discipline_empty_period(self):
        self.assertEqual(payment_discipline(P), [])
