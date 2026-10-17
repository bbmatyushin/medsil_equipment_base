"""Вкладка «Командировки» раздела «Аналитика»."""

from .filters import PeriodForm
from .views import AnalyticsTabView


class TripsView(AnalyticsTabView):
    """Вкладка «Командировки»."""

    tab_key = "trips"
    form_class = PeriodForm
    template_name = "analytics/trips.html"
