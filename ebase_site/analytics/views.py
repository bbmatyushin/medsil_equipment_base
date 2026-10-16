"""Страницы раздела «Статистика» внутри админки."""

from dataclasses import dataclass

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView

from .filters import FinanceFilterForm, PeriodForm


@dataclass(frozen=True)
class Tab:
    """Вкладка раздела: ключ, заголовок, право доступа и имя URL."""

    key: str
    title: str
    perm: str
    url_name: str


# Следующие этапы дописывают сюда свои вкладки
TABS = [
    Tab("finance", "Деньги", "analytics.view_finance", "analytics:finance"),
]


def visible_tabs(user) -> list[Tab]:
    """Вкладки, на которые у пользователя есть право."""
    return [tab for tab in TABS if user.has_perm(tab.perm)]


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
            title=f"Статистика — {self.tab.title}",
        )
        return context


class FinanceView(AnalyticsTabView):
    """Вкладка «Деньги»."""

    tab_key = "finance"
    form_class = FinanceFilterForm
    template_name = "analytics/finance.html"
