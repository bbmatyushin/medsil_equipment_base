"""Вкладка «Запчасти» раздела «Аналитика»."""

from .filters import SparePartFilterForm
from .views import AnalyticsTabView


class SparePartsView(AnalyticsTabView):
    tab_key = "spare_parts"
    form_class = SparePartFilterForm
    template_name = "analytics/spare_parts.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(filters=self.form.get_filters(), charts={})
        return context
