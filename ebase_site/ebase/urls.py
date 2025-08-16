from django.urls import path
from . import views

urlpatterns = [
    path("", views.IndexRedirectView.as_view(), name="home"),
    path('admin/get-spare-part-quantity/<uuid:spare_part_id>/',
         views.get_spare_part_quantity,
         name="get_spare_part_quantity")
]
