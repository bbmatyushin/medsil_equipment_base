from django.contrib import admin
from django.urls import path

from . import views
from .views_equipment import EquipmentView
from .views_trips import TripsView

app_name = "analytics"

urlpatterns = [
    path("", admin.site.admin_view(views.index), name="index"),
    path(
        "finance/", admin.site.admin_view(views.FinanceView.as_view()), name="finance"
    ),
    path("trips/", admin.site.admin_view(TripsView.as_view()), name="trips"),
    path(
        "equipment/",
        admin.site.admin_view(EquipmentView.as_view()),
        name="equipment",
    ),
]
