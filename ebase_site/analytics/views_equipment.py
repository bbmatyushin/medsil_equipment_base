"""Вкладка «Оборудование» раздела «Аналитика»."""

from .filters import EquipmentFilterForm
from .views import AnalyticsTabView


class EquipmentView(AnalyticsTabView):
    """Вкладка «Оборудование»: парк, ремонты, надёжность, подменный фонд."""

    tab_key = "equipment"
    form_class = EquipmentFilterForm
    template_name = "analytics/equipment.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(filters=self.form.get_filters(), charts={})
        return context
