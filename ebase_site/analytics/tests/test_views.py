import re
from datetime import date
from decimal import Decimal
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils.html import escape

from analytics.services.finance import TOTAL_KEYS
from analytics.tests.factories import (
    make_client,
    make_contract,
    make_payment,
    make_shipment,
)
from analytics.navigation import TABS, Tab, visible_tabs
from analytics.views import MAX_LINK_IDS, _pareto_caption
from clients.models import Client
from contracts.admin import format_money
from contracts.models import Contract, ContractExpense
from directory.models import City

User = get_user_model()

TODAY = date(2026, 10, 16)


def _fixed_today():
    """Подменяет «сегодня» страницы аналитики."""
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
        self.assertContains(response, "Финансы")

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

    def test_sidebar_lists_analytics_tabs_with_permission(self):
        self.client.force_login(self.finance_staff)
        response = self.client.get(reverse("admin:index"))
        apps = [
            app
            for app in response.context["available_apps"]
            if app["app_label"] == "analytics"
        ]
        self.assertEqual(len(apps), 1)
        app = apps[0]
        self.assertEqual(app["name"], "Аналитика")
        self.assertEqual(app["app_url"], reverse("analytics:index"))
        self.assertEqual(
            [(model["name"], model["admin_url"]) for model in app["models"]],
            [("Финансы", reverse("analytics:finance"))],
        )
        # тот же раздел — в списке на главной странице: на телефоне боковая панель скрыта
        self.assertIn(app, response.context["app_list"])
        self.assertContains(response, '<a href="%s"' % reverse("analytics:finance"))

    def test_sidebar_hides_analytics_without_permission(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            "analytics",
            [app["app_label"] for app in response.context["available_apps"]],
        )
        self.assertNotContains(response, reverse("analytics:finance"))

    def test_header_has_no_analytics_link(self):
        self.client.force_login(self.finance_staff)
        response = self.client.get(reverse("admin:index"))
        user_tools = re.search(
            r'<div id="user-tools">(.*?)</div>', response.content.decode(), re.S
        ).group(1)
        self.assertNotIn(reverse("analytics:index"), user_tools)
        self.assertNotIn("Аналитика", user_tools)

    def test_tab_page_highlights_tab_in_sidebar(self):
        self.client.force_login(self.finance_staff)
        response = self.client.get(reverse("analytics:finance"))
        self.assertContains(response, '<tr class="model-finance current-model">')

    def test_visible_tabs_follow_permissions(self):
        self.assertEqual(visible_tabs(self.superuser), TABS)
        self.assertEqual(
            [tab.key for tab in visible_tabs(self.finance_staff)], ["finance"]
        )
        self.assertEqual(visible_tabs(self.staff), [])

    def _trips_staff(self):
        user = User.objects.create_user("trips_staff", password="pass", is_staff=True)
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="analytics", codename="view_trips"
            )
        )
        return user

    def test_superuser_sees_trips_tab(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("analytics:trips"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Командировки")

    def test_staff_without_trips_permission_gets_403(self):
        self.client.force_login(self.finance_staff)
        response = self.client.get(reverse("analytics:trips"))
        self.assertEqual(response.status_code, 403)

    def test_index_redirects_to_trips_when_only_trips_permitted(self):
        self.client.force_login(self._trips_staff())
        response = self.client.get(reverse("analytics:index"))
        self.assertRedirects(response, reverse("analytics:trips"))
        self.assertEqual(reverse("analytics:trips"), "/admin/analytics/trips/")

    def test_sidebar_lists_trips_tab_with_permission(self):
        self.client.force_login(self._trips_staff())
        response = self.client.get(reverse("admin:index"))
        app = next(
            app
            for app in response.context["available_apps"]
            if app["app_label"] == "analytics"
        )
        self.assertEqual(
            [(model["name"], model["admin_url"]) for model in app["models"]],
            [("Командировки", reverse("analytics:trips"))],
        )

    def test_trips_tab_follows_finance_in_tabs(self):
        self.assertEqual([tab.key for tab in TABS][:2], ["finance", "trips"])

    def test_tab_is_frozen_dataclass(self):
        tab = Tab("finance", "Финансы", "analytics.view_finance", "analytics:finance")
        with self.assertRaises(Exception):
            tab.key = "other"

    def test_page_renders_breadcrumbs_and_tab_link(self):
        self.client.force_login(self.finance_staff)
        response = self.client.get(reverse("analytics:finance"))
        self.assertContains(response, "<title>Аналитика — Финансы")
        self.assertContains(response, '<a href="%s"' % reverse("analytics:finance"))
        self.assertEqual(response.context["active_tab"].key, "finance")
        self.assertEqual(response.context["title"], "Аналитика — Финансы")

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
    "stage_money",
}


def _paid_contract(client, number, conclusion, amount, **fields):
    """Контракт, оплаченный полностью в день заключения."""
    contract = make_contract(client, number, conclusion, amount, **fields)
    make_payment(contract, conclusion, amount)
    return contract


class FinancePageTests(TestCase):
    """Вкладка «Финансы»: виджеты, подписи и ссылки в списки админки."""

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
                # параметр бокового фильтра «Оплата?» (list_filter): `__exact`
                "payment_status__exact": ["paid"],
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

        # боковой фильтр «Оплата?» отмечает выбранный статус, а не «Все»:
        # иначе «Итого» можно принять за итог по всем контрактам
        cl = changelist.context["cl"]
        status_spec = next(
            spec
            for spec in cl.filter_specs
            if spec.lookup_kwarg == "payment_status__exact"
        )
        choices = list(status_spec.choices(cl))
        selected = [choice["display"] for choice in choices if choice["selected"]]
        self.assertEqual(
            selected, [Contract(payment_status="paid").get_payment_status_display()]
        )
        # клик по другому статусу в панели заменяет выбранный, а не складывается с ним
        other = next(
            choice
            for choice in choices
            if choice["display"]
            == Contract(payment_status="no_receipts").get_payment_status_display()
        )
        self.assertEqual(
            parse_qs(other["query_string"].lstrip("?"))["payment_status__exact"],
            ["no_receipts"],
        )

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

    def test_finance_tiles_match_contract_changelist_totals(self):
        alpha = make_client("Альфа")
        beta = make_client("Бета")
        # контракты внутри периода 01.02–30.06.2026
        first = make_contract(alpha, "R-1", date(2026, 3, 1), 1000)
        make_payment(first, date(2026, 3, 5), 250)
        second = make_contract(alpha, "R-2", date(2026, 5, 10), 2000)
        make_payment(second, date(2026, 5, 20), 800)
        ContractExpense.objects.create(
            contract=second, expense_type="other", quantity=1, cost=150
        )
        make_shipment(second, date(2026, 5, 12), 300)
        make_contract(beta, "R-3", date(2026, 4, 1), 700)
        # граничные дни периода входят в него
        make_contract(alpha, "R-FIRST-DAY", date(2026, 2, 1), 400)
        make_contract(beta, "R-LAST-DAY", date(2026, 6, 30), 600)
        # вне периода: до начала и после конца
        _paid_contract(alpha, "R-OLD", date(2026, 1, 31), 5000)
        make_contract(alpha, "R-LATE", date(2026, 7, 1), 9000)

        params = {
            "preset": "custom",
            "date_from": "2026-02-01",
            "date_to": "2026-06-30",
        }
        for client in (alpha, None):
            with self.subTest(client=client):
                tiles_params = dict(params)
                register_params = {
                    "conclusion_date__gte": params["date_from"],
                    "conclusion_date__lte": params["date_to"],
                }
                if client is not None:
                    tiles_params["client"] = client.pk
                    register_params["client"] = client.pk

                current = self._get(tiles_params).context["kpis"]["current"]
                changelist = self.client.get(
                    reverse("admin:contracts_contract_changelist"), register_params
                )
                self.assertEqual(changelist.status_code, 200)
                totals = changelist.context["totals"]

                self.assertEqual(set(totals), set(TOTAL_KEYS))
                for key in TOTAL_KEYS:
                    self.assertEqual(totals[key], format_money(current[key]), key)

        # фильтры действительно применены: клиент и период сужают итог
        alpha_only = self._get({**params, "client": alpha.pk}).context["kpis"]
        everyone = self._get(params).context["kpis"]
        self.assertEqual(alpha_only["current"]["count"], 3)
        self.assertEqual(everyone["current"]["count"], 5)

    def test_finance_registry_link_opens_same_contracts_as_tiles(self):
        alpha = make_client("Альфа")
        beta = make_client("Бета")
        make_contract(alpha, "L-IN", date(2026, 3, 1), 100)
        make_contract(alpha, "L-OLD", date(2025, 3, 1), 200)
        make_contract(beta, "L-BETA", date(2026, 3, 1), 400)

        response = self._get({"client": alpha.pk})

        registry_url = response.context["registry_url"]
        self.assertEqual(
            parse_qs(urlsplit(registry_url).query),
            {
                "conclusion_date__gte": ["2026-01-01"],
                "conclusion_date__lte": ["2026-12-31"],
                "client": [str(alpha.pk)],
            },
        )
        self.assertContains(response, f'href="{escape(registry_url)}"')
        self.assertContains(response, "Открыть в реестре")

        changelist = self.client.get(registry_url)
        self.assertEqual(changelist.status_code, 200)
        self.assertContains(changelist, "L-IN")
        self.assertNotContains(changelist, "L-OLD")
        self.assertNotContains(changelist, "L-BETA")

    def test_finance_registry_link_without_client_has_no_client_param(self):
        response = self._get()

        self.assertEqual(
            parse_qs(urlsplit(response.context["registry_url"]).query),
            {
                "conclusion_date__gte": ["2026-01-01"],
                "conclusion_date__lte": ["2026-12-31"],
            },
        )
        changelist = self.client.get(response.context["registry_url"])
        self.assertEqual(changelist.status_code, 200)

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

    def test_finance_aging_large_bucket_links_to_all_debtors(self):
        alpha = make_client("Альфа")
        # корзина «Более 180 дн.» длиннее предела ссылки, «0–30 дн.» — короткая
        for number in range(MAX_LINK_IDS + 1):
            make_contract(alpha, f"BIG-{number:03d}", date(2026, 1, 10), 100)
        make_contract(alpha, "D-FRESH", date(2026, 10, 1), 500)

        response = self._get()

        aging = {bucket["key"]: bucket for bucket in response.context["aging"]}
        large, small = aging["180_plus"], aging["0_30"]
        self.assertEqual(large["count"], MAX_LINK_IDS + 1)
        all_debtors = reverse("admin:contracts_contract_changelist") + "?debt__gt=0"
        self.assertEqual(large["url"], all_debtors)
        self.assertIs(large["all_debtors"], True)
        self.assertIn("id__in=", small["url"])
        self.assertIs(small["all_debtors"], False)
        self.assertEqual(
            response.context["charts"]["debt_aging"]["links"][4], all_debtors
        )
        self.assertContains(
            response, f"все должники: в корзине больше {MAX_LINK_IDS} контрактов"
        )

        changelist = self.client.get(large["url"])
        self.assertEqual(changelist.status_code, 200)
        self.assertContains(changelist, "D-FRESH")

    def test_finance_aging_large_bucket_keeps_selected_client(self):
        alpha = make_client("Альфа")
        beta = make_client("Бета")
        for number in range(MAX_LINK_IDS + 1):
            make_contract(alpha, f"BIG-{number:03d}", date(2026, 1, 10), 100)
        make_contract(beta, "B-DEBT", date(2026, 1, 10), 700)

        response = self._get({"client": alpha.pk})

        large = next(
            bucket
            for bucket in response.context["aging"]
            if bucket["key"] == "180_plus"
        )
        self.assertEqual(large["count"], MAX_LINK_IDS + 1)
        self.assertIs(large["all_debtors"], True)
        self.assertEqual(
            parse_qs(urlsplit(large["url"]).query),
            {"debt__gt": ["0"], "client": [str(alpha.pk)]},
        )
        self.assertContains(
            response,
            f"все должники клиента: в корзине больше {MAX_LINK_IDS} контрактов",
        )
        self.assertNotContains(response, "все должники: в корзине")

        changelist = self.client.get(large["url"])
        self.assertEqual(changelist.status_code, 200)
        # список постраничный: считаем все найденные, а не видимые на странице
        self.assertEqual(changelist.context["cl"].result_count, MAX_LINK_IDS + 1)
        self.assertNotContains(changelist, "B-DEBT")

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

    def test_finance_scatter_bubbles_sized_by_margin_and_colored_by_sign(self):
        client = make_client("Пузырьки")
        # маржа 100 %: оплата без затрат
        _paid_contract(client, "B-1", date(2026, 3, 1), 1000)
        # маржа 10 % и −50 %: затраты 900 и 1500 при оплате 1000
        for number, cost in (("B-2", 900), ("B-3", 1500)):
            contract = _paid_contract(client, number, date(2026, 3, 1), 1000)
            ContractExpense.objects.create(
                contract=contract, expense_type="other", quantity=1, cost=cost
            )

        response = self._get()

        dataset = response.context["charts"]["scatter"]["datasets"][0]
        self.assertIs(dataset["sign_colors"], True)
        # крупные пузырьки идут первыми, чтобы мелкие рисовались поверх них
        self.assertEqual(
            [(point["y"], point["r"]) for point in dataset["data"]],
            [(100.0, 20.0), (-50.0, 15.3), (10.0, 9.1)],
        )
        self.assertContains(response, "убыточные — красные")

    def test_finance_stage_money_chart(self):
        client = make_client("Стадии")
        done = make_contract(
            client, "S-1", date(2026, 3, 1), 1000, services_provided="fully"
        )
        make_payment(done, date(2026, 3, 5), 300)
        paid = _paid_contract(
            client, "S-2", date(2026, 4, 1), 500, services_provided="fully"
        )

        response = self._get()

        spec = response.context["charts"]["stage_money"]
        self.assertEqual(spec["labels"], ["Ещё нет", "Частично", "Полностью"])
        self.assertEqual(
            [(d["label"], d["color"], d["data"]) for d in spec["datasets"]],
            [
                ("Получено", "positive", [0.0, 0.0, 800.0]),
                ("Долг", "negative", [0.0, 0.0, 700.0]),
            ],
        )
        self.assertIs(spec["horizontal"], True)
        self.assertIs(spec["stacked"], True)
        self.assertIs(spec["value_labels"], True)
        self.assertEqual(spec["format"], "money_short")
        # клик по полосе — должники этой стадии за тот же период
        query = parse_qs(urlsplit(spec["links"][2]).query)
        self.assertEqual(query["services_provided"], ["fully"])
        self.assertEqual(query["debt__gt"], ["0"])
        self.assertEqual(query["conclusion_date__gte"], ["2026-01-01"])
        self.assertEqual(query["conclusion_date__lte"], ["2026-12-31"])
        changelist = self.client.get(spec["links"][2])
        self.assertEqual(changelist.status_code, 200)
        self.assertNotIn("e=1", changelist.request["QUERY_STRING"])
        self.assertContains(changelist, done.contract_number)
        self.assertNotContains(changelist, paid.contract_number)

    def test_finance_matrix_cells_are_shaded_by_meaning_and_amount(self):
        client = make_client("Тона")
        make_contract(client, "T-1", date(2026, 3, 1), 900, services_provided="fully")
        partly_paid = make_contract(
            client, "T-2", date(2026, 3, 1), 400, services_provided="fully"
        )
        make_payment(partly_paid, date(2026, 3, 2), 100)
        _paid_contract(client, "T-3", date(2026, 3, 1), 100, services_provided="fully")
        make_contract(
            client, "T-4", date(2026, 3, 1), 5000, services_provided="partially"
        )

        response = self._get()

        matrix = response.context["matrix"]
        shades = {
            (row, column): (cell["tone"], cell["shade"])
            for row, column in (
                ("fully", "no_receipts"),
                ("fully", "partial"),
                ("fully", "paid"),
                ("partially", "no_receipts"),
                ("not_yet", "partial"),
            )
            for cell in [self._cell(matrix, row, column)]
        }
        # насыщенность — внутри своего цвета: крупная «в процессе» не глушит красные
        self.assertEqual(
            shades,
            {
                ("fully", "no_receipts"): ("risk", 1.0),
                # √(400/900) ≈ 0,67
                ("fully", "partial"): ("risk", 0.67),
                ("fully", "paid"): ("ok", 1.0),
                ("partially", "no_receipts"): ("progress", 1.0),
                ("not_yet", "partial"): ("progress", 0.0),
            },
        )
        self.assertContains(
            response, '<td class="num an-tone-risk" style="--an-shade: 0.67">'
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
        contract = make_contract(alpha, "PRE-1", date(2026, 3, 22), 1000)
        # оплата за 21 день до подписания
        make_payment(contract, date(2026, 3, 1), 1000)

        response = self._get()

        self.assertEqual(response.context["discipline"][0]["avg_days"], Decimal("-21"))
        self.assertContains(
            response, '-21,0 <span class="an-note">предоплата</span>', count=1
        )

    def test_finance_discipline_counts_partially_paid_contracts(self):
        alpha = make_client("Альфа")
        contract = make_contract(alpha, "PART-1", date(2026, 3, 1), 1000)
        make_payment(contract, date(2026, 3, 15), 400)

        response = self._get()

        (row,) = response.context["discipline"]
        self.assertEqual((row["name"], row["avg_days"]), ("Альфа", Decimal("14")))
        self.assertContains(response, "с весом по сумме оплаты")


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
