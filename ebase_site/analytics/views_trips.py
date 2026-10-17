"""Вкладка «Командировки» раздела «Аналитика»."""

from .filters import TripsFilterForm
from .views import AnalyticsTabView


class TripsView(AnalyticsTabView):
    """Вкладка «Командировки»."""

    tab_key = "trips"
    form_class = TripsFilterForm
    template_name = "analytics/trips.html"
