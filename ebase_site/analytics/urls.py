from django.contrib import admin
from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("", admin.site.admin_view(views.index), name="index"),
    path(
        "finance/", admin.site.admin_view(views.FinanceView.as_view()), name="finance"
    ),
]
