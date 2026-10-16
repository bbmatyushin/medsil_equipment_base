from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from analytics.filters import Period
from analytics.services.finance import (
    AGING_BUCKETS,
    TOTAL_KEYS,
    _bucket_by_month,
    concluded_by_month,
    contracts_in_period,
    debt_aging,
    finance_kpis,
    money_flow,
    status_matrix,
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
