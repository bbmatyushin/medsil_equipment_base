from django.urls import path
from . import views

urlpatterns = [
    path("", views.IndexRedirectView.as_view(), name="home"),
]
