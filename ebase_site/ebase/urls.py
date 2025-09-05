from django.urls import path, re_path
from . import views

urlpatterns = [
    path("", views.IndexRedirectView.as_view(), name="home"),
    # re_path(
    #     "^admin/get-spare-part-quantity/(?P<service_id>null|[0-9a-f-]+)/(?P<spare_part_id>[0-9a-f-]+)/$",
    #     views.get_spare_part_quantity,
    #     name="get_spare_part_quantity",
    # ),
    path(
        "get_equipment_id_by_name/<str:equipment_full_name>/",
        views.get_equipment_id_by_name,
        name="get_equipment_id_by_name"
    )
    # path('admin/get-spare-part-quantity/<uuid:service_id>/<uuid:spare_part_id>/',
    #      views.get_spare_part_quantity,
    #      name="get_spare_part_quantity"),
    # path('admin/get-spare-part-quantity/null/<uuid:spare_part_id>/',
    #      views.get_spare_part_quantity_null,
    #      name="get_spare_part_quantity_null")
]
