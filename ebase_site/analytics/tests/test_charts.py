import json
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from analytics.charts import chart_spec, to_float
from analytics.links import change_url, changelist_url
from analytics.templatetags.analytics_tags import delta, delta_class, money, pct


class ToFloatTests(SimpleTestCase):
    def test_none_is_zero(self):
        self.assertEqual(to_float(None), 0.0)

    def test_decimal_and_int_are_rounded_to_kopecks(self):
        self.assertEqual(to_float(Decimal("10.505")), 10.51)
        self.assertEqual(to_float(7), 7.0)
        self.assertIsInstance(to_float(7), float)


class ChartSpecTests(SimpleTestCase):
    def test_chart_spec_converts_decimals(self):
        spec = chart_spec(
            "bar", ["янв 2026"], [{"label": "Пришло", "data": [Decimal("10.505")]}]
        )
        self.assertEqual(spec["datasets"][0]["data"], [10.51])
        self.assertFalse(spec["empty"])

    def test_chart_spec_keys_and_defaults(self):
        spec = chart_spec("bar", ["янв 2026"], [{"label": "Пришло", "data": [1]}])
        self.assertEqual(
            set(spec),
            {
                "kind",
                "labels",
                "datasets",
                "format",
                "x_format",
                "horizontal",
                "stacked",
                "links",
                "empty",
            },
        )
        self.assertEqual(spec["format"], "money")
        self.assertEqual(spec["links"], [])
        self.assertEqual(
            spec["datasets"][0],
            {
                "label": "Пришло",
                "data": [1.0],
                "kind": "bar",
                "axis": "y",
                "sign_colors": False,
                "fmt": None,
            },
        )

    def test_chart_spec_keeps_series_options(self):
        spec = chart_spec(
            "bar",
            ["А", "Б"],
            [
                {"label": "Оплачено", "data": [100, 50]},
                {
                    "label": "Накопленная доля",
                    "data": [Decimal("66.67"), Decimal("100")],
                    "kind": "line",
                    "axis": "y2",
                },
                {"label": "Прибыль", "data": [5, -3], "sign_colors": True},
            ],
            stacked=True,
        )
        line = spec["datasets"][1]
        self.assertEqual((line["kind"], line["axis"]), ("line", "y2"))
        self.assertEqual(line["data"], [66.67, 100.0])
        self.assertTrue(spec["datasets"][2]["sign_colors"])
        self.assertFalse(spec["horizontal"])
        self.assertTrue(spec["stacked"])

    def test_horizontal_chart(self):
        spec = chart_spec(
            "bar",
            ["Клиент А", "Клиент Б"],
            [{"label": "Прибыль", "data": [5, -3], "sign_colors": True}],
            horizontal=True,
        )
        self.assertTrue(spec["horizontal"])
        self.assertEqual(spec["datasets"][0]["axis"], "y")

    def test_dataset_fmt(self):
        spec = chart_spec(
            "bar",
            ["янв 2026", "фев 2026"],
            [
                {"label": "Сумма", "data": [100, 50]},
                {
                    "label": "Накопительно",
                    "data": [100, 150],
                    "kind": "line",
                    "axis": "y2",
                    "fmt": "money",
                },
            ],
        )
        self.assertIsNone(spec["datasets"][0]["fmt"])
        self.assertEqual(spec["datasets"][1]["fmt"], "money")
        self.assertEqual(spec["datasets"][1]["axis"], "y2")
        with self.assertRaises(ValueError):
            chart_spec(
                "bar",
                ["янв 2026"],
                [{"label": "Сумма", "data": [1], "fmt": "rubles"}],
            )

    def test_chart_spec_empty_when_all_zero(self):
        spec = chart_spec(
            "bar",
            ["янв 2026", "фев 2026"],
            [{"label": "Пришло", "data": [0, Decimal("0")]}],
        )
        self.assertTrue(spec["empty"])

    def test_chart_spec_empty_without_labels(self):
        spec = chart_spec("bar", [], [{"label": "Пришло", "data": []}])
        self.assertTrue(spec["empty"])

    def test_chart_spec_none_values_count_as_zero(self):
        spec = chart_spec("line", ["янв 2026"], [{"label": "Сальдо", "data": [None]}])
        self.assertEqual(spec["datasets"][0]["data"], [0.0])
        self.assertTrue(spec["empty"])

    def test_chart_spec_negative_values_are_not_empty(self):
        spec = chart_spec("bar", ["янв 2026"], [{"label": "Сальдо", "data": [-1]}])
        self.assertFalse(spec["empty"])

    def test_scatter_points(self):
        contract_id = uuid.uuid4()
        spec = chart_spec(
            "scatter",
            [],
            [
                {
                    "label": "Контракты",
                    "data": [
                        {
                            "x": Decimal("1000.50"),
                            "y": Decimal("12.5"),
                            "label": "№ 1 · Клиент",
                            "url": change_url("contracts_contract", contract_id),
                        }
                    ],
                }
            ],
            fmt="percent",
        )
        self.assertFalse(spec["empty"])
        self.assertEqual(spec["x_format"], "money")
        self.assertEqual(
            spec["datasets"][0]["data"],
            [
                {
                    "x": 1000.5,
                    "y": 12.5,
                    "label": "№ 1 · Клиент",
                    "url": f"/admin/contracts/contract/{contract_id}/change/",
                }
            ],
        )

    def test_scatter_without_points_is_empty(self):
        spec = chart_spec("scatter", [], [{"label": "Контракты", "data": []}])
        self.assertTrue(spec["empty"])

    def test_chart_spec_is_json_serializable(self):
        spec = chart_spec(
            "bar",
            ["янв 2026"],
            [
                {"label": "Пришло", "data": [Decimal("1.5")]},
                {"label": "Сальдо", "data": [None], "kind": "line"},
            ],
            links=[changelist_url("contracts_contract", id__in=[uuid.uuid4()])],
        )
        json.dumps(spec)

    def test_chart_spec_rejects_unknown_options(self):
        cases = [
            {"kind": "pie"},
            {"fmt": "rubles"},
            {"datasets": [{"label": "А", "data": [1], "axis": "y3"}]},
            {"datasets": [{"label": "А", "data": [1], "kind": "pie"}]},
            {"links": ["/a/", "/b/"]},
            # правая ось y2 есть только у вертикальных графиков
            {
                "horizontal": True,
                "datasets": [
                    {"label": "А", "data": [1]},
                    {"label": "Доля", "data": [100], "kind": "line", "axis": "y2"},
                ],
            },
        ]
        base = {
            "kind": "bar",
            "labels": ["янв 2026"],
            "datasets": [{"label": "А", "data": [1]}],
        }
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                chart_spec(**{**base, **case})


class LinksTests(SimpleTestCase):
    def test_changelist_url_joins_lists(self):
        self.assertEqual(
            changelist_url("contracts_contract", id__in=["a", "b"], client=None),
            "/admin/contracts/contract/?id__in=a%2Cb",
        )

    def test_changelist_url_without_params(self):
        self.assertEqual(
            changelist_url("contracts_contract"), "/admin/contracts/contract/"
        )

    def test_changelist_url_stringifies_values(self):
        client_id = uuid.uuid4()
        self.assertEqual(
            changelist_url(
                "contracts_contract",
                payment_status="paid",
                client=client_id,
                conclusion_date__gte="2026-01-01",
            ),
            "/admin/contracts/contract/?payment_status=paid"
            f"&client={client_id}&conclusion_date__gte=2026-01-01",
        )

    def test_change_url(self):
        contract_id = uuid.uuid4()
        self.assertEqual(
            change_url("contracts_contract", contract_id),
            f"/admin/contracts/contract/{contract_id}/change/",
        )


class FilterTests(SimpleTestCase):
    def test_money_filter(self):
        self.assertEqual(money(Decimal("20000")), "20 000,00 ₽")
        self.assertEqual(money(None), "—")

    def test_pct_filter(self):
        self.assertEqual(pct(Decimal("12.5")), "12,5 %")
        self.assertEqual(pct(Decimal("100")), "100,0 %")
        self.assertEqual(pct(None), "—")

    def test_delta_filter(self):
        self.assertEqual(delta(Decimal("12.5")), "+12,5 %")
        self.assertEqual(delta(Decimal("-3")), "−3,0 %")
        self.assertEqual(delta(Decimal("0")), "0,0 %")
        self.assertEqual(delta(None), "—")

    def test_delta_filter_percentage_points(self):
        self.assertEqual(delta(Decimal("1.5"), "pp"), "+1,5 п.п.")
        self.assertEqual(delta(Decimal("-0.4"), "pp"), "−0,4 п.п.")
        self.assertEqual(delta(None, "pp"), "—")

    def test_delta_class(self):
        self.assertEqual(delta_class(Decimal("12.5")), "an-delta--up")
        self.assertEqual(delta_class(Decimal("-3")), "an-delta--down")
        self.assertEqual(delta_class(Decimal("0")), "an-delta--flat")
        self.assertEqual(delta_class(None), "an-delta--flat")


class ChartIncludeTests(SimpleTestCase):
    def test_renders_canvas_and_json(self):
        spec = chart_spec("bar", ["янв 2026"], [{"label": "Пришло", "data": [5]}])
        html = render_to_string(
            "analytics/includes/chart.html",
            {"spec": spec, "chart_id": "chart-money-flow"},
        )
        self.assertIn('<canvas data-chart="chart-money-flow"', html)
        self.assertIn('<script id="chart-money-flow" type="application/json">', html)
        self.assertNotIn("Нет данных за выбранный период", html)

    def test_empty_spec_shows_message_instead_of_canvas(self):
        spec = chart_spec("bar", ["янв 2026"], [{"label": "Пришло", "data": [0]}])
        html = render_to_string(
            "analytics/includes/chart.html",
            {"spec": spec, "chart_id": "chart-money-flow"},
        )
        self.assertIn("Нет данных за выбранный период", html)
        self.assertNotIn("<canvas", html)


class ChartAssetsTests(TestCase):
    def test_chart_js_is_vendored_without_source_map(self):
        path = finders.find("analytics/vendor/chart.umd.min.js")
        self.assertIsNotNone(path)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn("Chart.js v4.5.1", content[:200])
        # ManifestStaticFilesStorage падает на sourceMappingURL без .map
        self.assertNotIn("sourceMappingURL", content)

    def test_base_template_includes_assets(self):
        user = get_user_model().objects.create_superuser(
            "super", "super@example.com", "pass"
        )
        self.client.force_login(user)
        response = self.client.get(reverse("analytics:finance"))
        self.assertContains(response, "analytics/vendor/chart.umd.min.js")
        self.assertContains(response, "analytics/js/charts.js")
        self.assertContains(response, "analytics/css/analytics.css")
