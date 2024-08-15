from django.contrib import admin
from django.urls import path, include
from debug_toolbar.toolbar import debug_toolbar_urls

urlpatterns = [
    path("", include("ebase.urls")),
    path("", include("directory.urls")),
    path("admin/", admin.site.urls),
] + debug_toolbar_urls()

admin.site.site_header = 'ООО "Фирма МЕДСИЛ":  Сервис'
admin.site.index_title = 'Администрирование учета сервисного оборудования'
