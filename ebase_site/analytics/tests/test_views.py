from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from analytics.views import TABS, Tab, visible_tabs
from clients.models import Client
from contracts.models import Contract
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
