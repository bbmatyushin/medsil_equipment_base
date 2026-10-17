"""Страницы раздела «Аналитика» внутри админки."""

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView

from clients.models import Client

from .charts import bubble_radius, chart_spec
from .filters import FinanceFilterForm, Period, PeriodForm, month_label
from .links import change_url, changelist_url
from .navigation import TABS, visible_tabs
from .services import finance


def index(request):
    """Корень раздела: ведёт на первую доступную вкладку, иначе 403."""
    tabs = visible_tabs(request.user)
    if not tabs:
        raise PermissionDenied
    return redirect(tabs[0].url_name)


class AnalyticsTabView(TemplateView):
    """Общая часть вкладок: проверка права, разбор фильтров, контекст вкладок."""

    tab_key: str
    form_class = PeriodForm

    def dispatch(self, request, *args, **kwargs):
        self.tab = next(tab for tab in TABS if tab.key == self.tab_key)
        if not request.user.has_perm(self.tab.perm):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        today = timezone.localdate()
        # форма доступна наследникам как self.form (например, для get_client())
        self.form = self.form_class(data=self.request.GET)
        period = self.form.get_period(today)
        context = super().get_context_data(**kwargs)
        context.update(
            **admin.site.each_context(self.request),
            tabs=visible_tabs(self.request.user),
            active_tab=self.tab,
            form=self.form,
            period=period,
            previous_period=period.previous_year(),
            today=today,
            title=f"Аналитика — {self.tab.title}",
        )
        return context


# --- Вкладка «Финансы» --------------------------------------------------------

# Список контрактов в админке: сюда ведут клики по виджетам
CONTRACTS = "contracts_contract"

# Не больше стольких id в ссылке `?id__in=`: UUID с разделителем «%2C» — 39 символов,
# 90 штук ≈ 3,5 КБ, меньше предела строки запроса gunicorn по умолчанию (4094 байта)
MAX_LINK_IDS = 90

# Маржа, при которой пузырёк «Контракты: сумма и маржа» максимальный. Маржа
# в плюс не бывает больше 100 %, убыток — бывает (−900 %), такие тоже максимальные
MARGIN_FOR_MAX_BUBBLE = 100

# Плитки: ключ показателя finance_kpis, подпись, «рост — плохо» (затраты, долг)
FINANCE_TILES = [
    ("contract_amount", "Сумма контрактов", False),
    ("payment_amount", "Оплачено", False),
    ("expenses_amount", "Затраты", True),
    ("debt", "Долг", True),
    ("profit", "Прибыль", False),
    ("margin_pct", "Маржа", False),
]

# Высота горизонтального графика на одну строку: иначе Chart.js при многих
# клиентах пропускает часть подписей оси
ROW_HEIGHT_PX = 24
MIN_CHART_HEIGHT_PX = 300


def _finance_tiles(kpis: dict) -> list[dict]:
    """Плитки: значение, дельта к прошлому году, признаки показа."""
    return [
        {
            "label": label,
            "value": kpis["current"][key],
            "delta": kpis["delta_pct"][key],
            "inverse": inverse,
            # маржа в %, её дельта — в процентных пунктах
            "percent": key == "margin_pct",
        }
        for key, label, inverse in FINANCE_TILES
    ]


def _client_param(client: Client | None) -> str | None:
    """Значение GET-параметра `client` для ссылок в реестр; None — без клиента."""
    return str(client.pk) if client is not None else None


def _aging_link(
    ids: list[str], client_pk: str | None = None
) -> tuple[str | None, bool]:
    """Ссылка корзины долга и признак «ведёт на всех должников».

    Пустая корзина — без ссылки. Корзина больше `MAX_LINK_IDS` ведёт на всех
    должников (выбранного клиента, если он задан): длинный `?id__in=` gunicorn
    отклонил бы с ответом 400.
    """
    if not ids:
        return None, False
    if len(ids) > MAX_LINK_IDS:
        return changelist_url(CONTRACTS, debt__gt=0, client=client_pk), True
    return changelist_url(CONTRACTS, id__in=ids), False


def _with_aging_links(aging: list[dict], client: Client | None) -> list[dict]:
    """Корзины долга со ссылкой (`url`) и признаком `all_debtors`."""
    client_pk = _client_param(client)
    result = []
    for bucket in aging:
        url, all_debtors = _aging_link(bucket["ids"], client_pk)
        result.append({**bucket, "url": url, "all_debtors": all_debtors})
    return result


def _with_matrix_links(matrix: dict, period: Period, client: Client | None) -> dict:
    """Матрица «оказано × оплачено» со ссылкой у каждой ячейки на её контракты."""
    for row in matrix["rows"]:
        for cell in row["cells"]:
            cell["url"] = changelist_url(
                CONTRACTS,
                services_provided=row["key"],
                # параметр бокового фильтра «Оплата?»: без `__exact` он его не отметит
                payment_status__exact=cell["payment_status"],
                conclusion_date__gte=period.date_from.isoformat(),
                conclusion_date__lte=period.date_to.isoformat(),
                client=_client_param(client),
            )
    return matrix


def _registry_url(period: Period, client: Client | None) -> str:
    """Реестр контрактов с теми же фильтрами, что у плиток: сверка с «Итого» списка."""
    return changelist_url(
        CONTRACTS,
        conclusion_date__gte=period.date_from.isoformat(),
        conclusion_date__lte=period.date_to.isoformat(),
        client=_client_param(client),
    )


def _is_singular(number: int) -> bool:
    """1, 21, 31… (но не 11): «1 клиент даёт», «из 21 клиента»."""
    return number % 10 == 1 and number % 100 != 11


def _pareto_caption(top: dict) -> str | None:
    """«N из M клиентов дают 80 % оплат»; без платящих клиентов — None."""
    total = top["clients_total"]
    if not total:
        return None
    count = top["clients_for_80"]
    clients = "клиента" if _is_singular(total) else "клиентов"
    verb = "даёт" if _is_singular(count) else "дают"
    return f"{count} из {total} {clients} {verb} 80 % оплат"


def _horizontal_chart_height(rows: int) -> int:
    """Высота горизонтального графика в px по числу строк."""
    return max(MIN_CHART_HEIGHT_PX, rows * ROW_HEIGHT_PX + 60)


def _scatter_bubbles(points: list[dict]) -> list[dict]:
    """Точки «Контракты: сумма и маржа»: ссылка на контракт и радиус по марже.

    Чем больше модуль маржи, тем крупнее пузырёк (убыточные красит `charts.js`).
    Крупные идут первыми, чтобы мелкие рисовались поверх них.
    """
    bubbles = [
        {
            **point,
            "url": change_url(CONTRACTS, point["id"]),
            "r": bubble_radius(point["y"], MARGIN_FOR_MAX_BUBBLE),
        }
        for point in points
    ]
    return sorted(bubbles, key=lambda bubble: -bubble["r"])


def _finance_charts(
    flow: dict,
    concluded: dict,
    aging: list[dict],
    top: dict,
    profit_rows: list[dict],
    points: list[dict],
) -> dict:
    """Спецификации графиков вкладки «Финансы»."""
    months = [month_label(month) for month in flow["months"]]
    concluded_months = [month_label(month) for month in concluded["months"]]
    clients = top["clients"]
    return {
        "money_flow": chart_spec(
            "bar",
            months,
            [
                {"label": "Пришло", "data": flow["inflow"]},
                {"label": "Ушло", "data": flow["outflow"]},
                {"label": "Сальдо", "data": flow["balance"], "kind": "line"},
            ],
        ),
        "concluded": chart_spec(
            "bar",
            concluded_months,
            [
                {"label": "Сумма", "data": concluded["amount"]},
                {
                    "label": "Накопительно",
                    "data": concluded["cumulative"],
                    "kind": "line",
                    "axis": "y2",
                    "fmt": "money",
                },
            ],
        ),
        "cost_structure": chart_spec(
            "bar",
            months,
            [
                {"label": "Запчасти", "data": flow["spare_parts"]},
                {"label": "Командировки", "data": flow["trips"]},
                {"label": "Прочие", "data": flow["other"]},
            ],
            stacked=True,
        ),
        "debt_aging": chart_spec(
            "bar",
            [bucket["label"] for bucket in aging],
            [{"label": "Долг", "data": [bucket["amount"] for bucket in aging]}],
            horizontal=True,
            links=[bucket["url"] for bucket in aging],
        ),
        "top_clients": chart_spec(
            "bar",
            [row["name"] for row in clients],
            [
                {"label": "Оплачено", "data": [row["amount"] for row in clients]},
                {
                    "label": "Накопленная доля",
                    "data": [row["cumulative_pct"] for row in clients],
                    "kind": "line",
                    "axis": "y2",
                    "fmt": "percent",
                },
            ],
        ),
        "profitability": chart_spec(
            "bar",
            [row["name"] for row in profit_rows],
            [
                {
                    "label": "Прибыль",
                    "data": [row["profit"] for row in profit_rows],
                    "sign_colors": True,
                }
            ],
            horizontal=True,
        ),
        "scatter": chart_spec(
            "scatter",
            [],
            [
                {
                    "label": "Контракты",
                    "data": _scatter_bubbles(points),
                    "sign_colors": True,
                }
            ],
            fmt="percent",
            x_fmt="money",
        ),
    }


class FinanceView(AnalyticsTabView):
    """Вкладка «Финансы»."""

    tab_key = "finance"
    form_class = FinanceFilterForm
    template_name = "analytics/finance.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period = context["period"]
        client = self.form.get_client()

        kpis = finance.finance_kpis(period, client)
        aging = _with_aging_links(finance.debt_aging(context["today"], client), client)
        # «Топ» и «Рентабельность» сравнивают клиентов: фильтр клиента не применяется
        top = finance.top_clients(period)
        profitability = finance.client_profitability(period)
        # сверху вниз по убыванию прибыли: лучшие, затем убыточные, худший — последним
        profit_rows = profitability["best"] + profitability["losers"][::-1]

        context.update(
            client=client,
            kpis=kpis,
            tiles=_finance_tiles(kpis),
            registry_url=_registry_url(period, client),
            charts=_finance_charts(
                flow=finance.money_flow(period, client),
                concluded=finance.concluded_by_month(period, client),
                aging=aging,
                top=top,
                profit_rows=profit_rows,
                points=finance.contracts_scatter(period, client),
            ),
            matrix=_with_matrix_links(
                finance.status_matrix(period, client), period, client
            ),
            aging=aging,
            max_link_ids=MAX_LINK_IDS,
            pareto_caption=_pareto_caption(top),
            profitability_height=_horizontal_chart_height(len(profit_rows)),
            discipline=finance.payment_discipline(period, client),
        )
        return context
