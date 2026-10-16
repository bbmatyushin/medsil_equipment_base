from datetime import date
from decimal import Decimal
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from analytics.tests.factories import make_client, make_contract, make_payment
from analytics.views import TABS, Tab, _pareto_caption, visible_tabs
from clients.models import Client
from contracts.admin import format_money
from contracts.models import Contract, ContractExpense
from directory.models import City

User = get_user_model()

TODAY = date(2026, 10, 16)


def _fixed_today():
    """Подменяет «сегодня» страницы статистики."""
    return mock.patch("django.utils.timezone.localdate", return_value=TODAY)


class AnalyticsViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            "super", "super@example.com", "pass"
        )
        cls.staff = User.objects.create_user("staff", password="pass", is_staff=True)
        cls.finance_staff = User.objects.create_user(
            "finance_staff", password="pass", is_staff=True
        )
        cls.finance_staff.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="analytics", codename="view_finance"
            )
        )

    def test_superuser_sees_finance_tab(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("analytics:finance"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Деньги")

    def test_staff_without_permission_gets_403_on_tab(self):
        self.client.force_login(self.staff)
        with self.assertLogs("django.request", "WARNING"):
            response = self.client.get(reverse("analytics:finance"))
        self.assertEqual(response.status_code, 403)

    def test_staff_without_permission_gets_403_on_index(self):
        self.client.force_login(self.staff)
        with self.assertLogs("django.request", "WARNING"):
            response = self.client.get(reverse("analytics:index"))
        self.assertEqual(response.status_code, 403)

    def test_index_redirects_to_first_permitted_tab(self):
        self.client.force_login(self.finance_staff)
        response = self.client.get(reverse("analytics:index"))
        self.assertRedirects(
            response, reverse("analytics:finance"), fetch_redirect_response=False
        )

    def test_anonymous_redirected_to_admin_login(self):
        for name in ("analytics:index", "analytics:finance"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn("/admin/login/", response["Location"])

    def test_header_link_shown_with_permission(self):
        self.client.force_login(self.finance_staff)
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, reverse("analytics:index"))

    def test_header_link_hidden_without_permission(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("analytics:index"))

    def test_visible_tabs_follow_permissions(self):
        self.assertEqual(visible_tabs(self.superuser), TABS)
        self.assertEqual(
            [tab.key for tab in visible_tabs(self.finance_staff)], ["finance"]
        )
        self.assertEqual(visible_tabs(self.staff), [])

    def test_tab_is_frozen_dataclass(self):
        tab = Tab("finance", "Деньги", "analytics.view_finance", "analytics:finance")
        with self.assertRaises(Exception):
            tab.key = "other"

    def test_page_renders_breadcrumbs_and_tab_link(self):
        self.client.force_login(self.finance_staff)
        response = self.client.get(reverse("analytics:finance"))
        self.assertContains(response, "<title>Статистика — Деньги")
        self.assertContains(response, '<a href="%s"' % reverse("analytics:finance"))
        self.assertEqual(response.context["active_tab"].key, "finance")
        self.assertEqual(response.context["title"], "Статистика — Деньги")

    def test_page_shows_resolved_period_and_comparison(self):
        self.client.force_login(self.finance_staff)
        with _fixed_today():
            response = self.client.get(reverse("analytics:finance"))
        self.assertContains(
            response,
            "Период: 01.01.2026 — 31.12.2026 · сравнение с 01.01.2025 — 31.12.2025",
        )

    def test_garbage_params_fall_back_to_current_year(self):
        self.client.force_login(self.finance_staff)
        with _fixed_today():
            response = self.client.get(
                reverse("analytics:finance"),
                {"preset": "bogus", "client": "not-a-uuid"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Период: 01.01.2026 — 31.12.2026")

    def test_custom_period_is_prefilled_in_iso_format(self):
        self.client.force_login(self.finance_staff)
        with _fixed_today():
            response = self.client.get(
                reverse("analytics:finance"),
                {
                    "preset": "custom",
                    "date_from": "2026-03-05",
                    "date_to": "2026-04-10",
                },
            )
        self.assertContains(response, 'value="2026-03-05"')
        self.assertContains(response, 'value="2026-04-10"')
        self.assertContains(response, "Период: 05.03.2026 — 10.04.2026")
        self.assertContains(response, "сравнение с 05.03.2025 — 10.04.2025")

    def _make_client_with_contract(self):
        city, _ = City.objects.get_or_create(name="Москва", region=None)
        client = Client.objects.create(
            name="Клиника Тест", city=city, inn="123456789001"
        )
        Contract.objects.create(
            client=client,
            contract_number="CNT-001",
            conclusion_date="2026-01-15",
            contract_amount=100000,
        )
        return client

    def test_finance_form_renders_client_filter(self):
        self._make_client_with_contract()
        self.client.force_login(self.finance_staff)
        response = self.client.get(reverse("analytics:finance"))
        self.assertContains(response, "Все клиенты")
        self.assertContains(response, "Клиника Тест")
        self.assertIsNone(response.context["form"].get_client())

    def test_finance_form_client_filter_is_applied(self):
        client = self._make_client_with_contract()
        self.client.force_login(self.finance_staff)
        response = self.client.get(reverse("analytics:finance"), {"client": client.pk})
        self.assertEqual(response.context["form"].get_client(), client)


CHART_KEYS = {
    "money_flow",
    "concluded",
    "cost_structure",
    "debt_aging",
    "top_clients",
    "profitability",
    "scatter",
}


def _paid_contract(client, number, conclusion, amount, **fields):
    """Контракт, оплаченный полностью в день заключения."""
    contract = make_contract(client, number, conclusion, amount, **fields)
    make_payment(contract, conclusion, amount)
    return contract


class FinancePageTests(TestCase):
    """Вкладка «Деньги»: виджеты, подписи и ссылки в списки админки."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            "super", "super@example.com", "pass"
        )

    def setUp(self):
        self.client.force_login(self.superuser)

    def _get(self, params=None):
        with _fixed_today():
            response = self.client.get(reverse("analytics:finance"), params or {})
        self.assertEqual(response.status_code, 200)
        return response

    @staticmethod
    def _cell(matrix, services_provided, payment_status):
        row = next(row for row in matrix["rows"] if row["key"] == services_provided)
        return next(
            cell for cell in row["cells"] if cell["payment_status"] == payment_status
        )

    def test_finance_page_empty_db(self):
        response = self._get()

        self.assertContains(response, "Нет данных")
        # маржа без оплат и дельты без прошлого периода — «—», без деления на ноль
        self.assertContains(response, '<p class="an-tile-value">—</p>', count=1)
        self.assertContains(response, 'an-delta--flat">—</p>', count=6)
        self.assertContains(response, '<p class="an-tile-value">0,00 ₽</p>', count=5)
        self.assertEqual(set(response.context["charts"]), CHART_KEYS)
        for key, spec in response.context["charts"].items():
            self.assertTrue(spec["empty"], key)
        self.assertEqual(response.context["discipline"], [])
        self.assertIsNone(response.context["client"])
        # без платящих клиентов нет подписи «0 из 0»
        self.assertNotContains(response, "из 0")
        self.assertNotContains(response, '<span class="an-note">предоплата</span>')

    def test_finance_page_with_data(self):
        alpha = make_client("Альфа")
        contract = make_contract(alpha, "FIN-1", date(2026, 2, 1), 100000)
        make_payment(contract, date(2026, 2, 10), 40000)

        response = self._get()

        self.assertContains(response, format_money(Decimal("100000")))
        self.assertContains(response, "40 000,00 ₽")
        charts = response.context["charts"]
        self.assertEqual(set(charts), CHART_KEYS)
        self.assertIs(charts["money_flow"]["empty"], False)
        self.assertEqual(len(charts["money_flow"]["labels"]), 12)
        self.assertEqual(charts["money_flow"]["labels"][1], "фев 2026")
        self.assertEqual(charts["money_flow"]["datasets"][0]["data"][1], 40000.0)
        # «Накопительно» — линия на правой денежной шкале
        cumulative = charts["concluded"]["datasets"][1]
        self.assertEqual(
            (cumulative["kind"], cumulative["axis"], cumulative["fmt"]),
            ("line", "y2", "money"),
        )
        self.assertEqual(response.context["kpis"]["current"]["count"], 1)
        point = charts["scatter"]["datasets"][0]["data"][0]
        self.assertEqual(
            point["url"], reverse("admin:contracts_contract_change", args=[contract.pk])
        )
        self.assertEqual(charts["scatter"]["format"], "percent")
        self.assertEqual(charts["scatter"]["x_format"], "money")

    def test_finance_page_bad_params(self):
        response = self._get(
            {"preset": "zzz", "date_from": "abc", "client": "not-a-uuid"}
        )

        self.assertEqual(response.context["period"].date_from, date(2026, 1, 1))
        self.assertIsNone(response.context["client"])

    def test_finance_tiles_inverse_for_expenses_and_debt(self):
        response = self._get()

        self.assertContains(response, "an-tile--inverse", count=2)
        self.assertEqual(
            [tile["label"] for tile in response.context["tiles"] if tile["inverse"]],
            ["Затраты", "Долг"],
        )
        self.assertContains(response, "к 01.01.2025 — 31.12.2025", count=6)

    def test_finance_margin_delta_in_percentage_points(self):
        alpha = make_client("Альфа")
        _paid_contract(alpha, "PP-1", date(2025, 3, 1), 1000)
        _paid_contract(alpha, "PP-2", date(2026, 3, 1), 1000)

        response = self._get()

        # маржа 100 % в обоих годах: дельта 0 п.п.
        self.assertContains(response, "0,0 п.п.")

    def test_finance_matrix_links_filter_contract_changelist(self):
        alpha = make_client("Альфа")
        _paid_contract(
            alpha, "M-PAID", date(2026, 3, 1), 1000, services_provided="fully"
        )
        make_contract(alpha, "M-OPEN", date(2026, 4, 1), 500)
        _paid_contract(alpha, "M-OLD", date(2025, 3, 1), 700, services_provided="fully")

        response = self._get()

        cell = self._cell(response.context["matrix"], "fully", "paid")
        self.assertEqual(cell["count"], 1)
        self.assertEqual(
            parse_qs(urlsplit(cell["url"]).query),
            {
                "services_provided": ["fully"],
                "payment_status": ["paid"],
                "conclusion_date__gte": ["2026-01-01"],
                "conclusion_date__lte": ["2026-12-31"],
            },
        )
        self.assertTrue(
            cell["url"].startswith(reverse("admin:contracts_contract_changelist"))
        )
        # у каждой ячейки есть ссылка, даже у пустой
        empty = self._cell(response.context["matrix"], "partially", "partial")
        self.assertEqual(empty["count"], 0)
        self.assertIn("services_provided=partially", empty["url"])

        changelist = self.client.get(cell["url"])
        self.assertEqual(changelist.status_code, 200)
        self.assertContains(changelist, "M-PAID")
        self.assertNotContains(changelist, "M-OPEN")
        self.assertNotContains(changelist, "M-OLD")

    def test_finance_matrix_links_keep_selected_client(self):
        alpha = make_client("Альфа")
        beta = make_client("Бета")
        make_contract(alpha, "A-1", date(2026, 3, 1), 100)
        make_contract(beta, "B-1", date(2026, 3, 1), 200)

        response = self._get({"client": alpha.pk})

        self.assertEqual(response.context["client"], alpha)
        cell = self._cell(response.context["matrix"], "not_yet", "no_receipts")
        self.assertEqual(cell["count"], 1)
        self.assertEqual(
            parse_qs(urlsplit(cell["url"]).query)["client"], [str(alpha.pk)]
        )

        changelist = self.client.get(cell["url"])
        self.assertEqual(changelist.status_code, 200)
        self.assertContains(changelist, "A-1")
        self.assertNotContains(changelist, "B-1")

    def test_finance_aging_link_opens_changelist(self):
        alpha = make_client("Альфа")
        # без оплат: долг = сумма; возраст от даты заключения (на 16.10.2026)
        make_contract(alpha, "D-OLD", date(2026, 1, 10), 1000)  # 279 дн.
        make_contract(alpha, "D-FRESH", date(2026, 10, 1), 500)  # 15 дн.

        response = self._get()

        aging = {bucket["key"]: bucket for bucket in response.context["aging"]}
        old = aging["180_plus"]
        self.assertEqual(old["count"], 1)
        self.assertIn("id__in=", old["url"])
        self.assertIsNone(aging["31_90"]["url"])
        spec = response.context["charts"]["debt_aging"]
        self.assertIs(spec["horizontal"], True)
        self.assertEqual(
            spec["links"], [bucket["url"] for bucket in response.context["aging"]]
        )
        self.assertContains(response, "на сегодня, период не учитывается")

        changelist = self.client.get(old["url"])
        self.assertEqual(changelist.status_code, 200)
        self.assertContains(changelist, "D-OLD")
        self.assertNotContains(changelist, "D-FRESH")

    def test_finance_top_clients_ignore_client_filter(self):
        alpha = make_client("Альфа")
        beta = make_client("Бета")
        gamma = make_client("Гамма")
        _paid_contract(alpha, "T-1", date(2026, 3, 1), 6000)
        _paid_contract(beta, "T-2", date(2026, 3, 1), 3000)
        _paid_contract(gamma, "T-3", date(2026, 3, 1), 1000)

        response = self._get({"client": alpha.pk})

        spec = response.context["charts"]["top_clients"]
        self.assertEqual(spec["labels"], ["Альфа", "Бета", "Гамма"])
        share = spec["datasets"][1]
        self.assertEqual(
            (share["kind"], share["axis"], share["fmt"]), ("line", "y2", "percent")
        )
        self.assertIs(spec["horizontal"], False)
        self.assertContains(response, "2 из 3 клиентов дают 80 % оплат")
        self.assertContains(
            response, "все клиенты, фильтр клиента не применяется", count=2
        )
        self.assertEqual(
            response.context["charts"]["profitability"]["labels"],
            ["Альфа", "Бета", "Гамма"],
        )

    def test_finance_profitability_losers_at_bottom(self):
        names = ["Альфа", "Бета", "Гамма", "Дельта"]
        alpha, beta, gamma, delta = (make_client(name) for name in names)
        _paid_contract(alpha, "P-1", date(2026, 3, 1), 100)
        _paid_contract(beta, "P-2", date(2026, 3, 1), 50)
        for client, number, cost in ((gamma, "P-3", 10), (delta, "P-4", 30)):
            contract = make_contract(client, number, date(2026, 3, 1), 1000)
            ContractExpense.objects.create(
                contract=contract, expense_type="other", quantity=1, cost=cost
            )

        response = self._get()

        spec = response.context["charts"]["profitability"]
        self.assertIs(spec["horizontal"], True)
        # сверху вниз по убыванию прибыли: худший убыточный — последним
        self.assertEqual(spec["labels"], names)
        self.assertEqual(spec["datasets"][0]["data"], [100.0, 50.0, -10.0, -30.0])
        self.assertIs(spec["datasets"][0]["sign_colors"], True)

    def test_finance_discipline_marks_prepayment(self):
        alpha = make_client("Альфа")
        contract = make_contract(
            alpha,
            "PRE-1",
            date(2026, 3, 1),
            1000,
            service_end_date=date(2026, 3, 31),
        )
        make_payment(contract, date(2026, 3, 10), 1000)

        response = self._get()

        self.assertEqual(response.context["discipline"][0]["avg_days"], Decimal("-21"))
        self.assertContains(
            response, '-21,0 <span class="an-note">предоплата</span>', count=1
        )


class ParetoCaptionTests(SimpleTestCase):
    def _caption(self, clients_for_80, clients_total):
        return _pareto_caption(
            {"clients_for_80": clients_for_80, "clients_total": clients_total}
        )

    def test_no_paying_clients_gives_no_caption(self):
        self.assertIsNone(self._caption(0, 0))

    def test_caption_agrees_with_numbers(self):
        cases = [
            (2, 3, "2 из 3 клиентов дают 80 % оплат"),
            (1, 1, "1 из 1 клиента даёт 80 % оплат"),
            (3, 21, "3 из 21 клиента дают 80 % оплат"),
            (11, 111, "11 из 111 клиентов дают 80 % оплат"),
            (21, 40, "21 из 40 клиентов даёт 80 % оплат"),
        ]
        for clients_for_80, clients_total, expected in cases:
            with self.subTest(clients_total=clients_total):
                self.assertEqual(self._caption(clients_for_80, clients_total), expected)
