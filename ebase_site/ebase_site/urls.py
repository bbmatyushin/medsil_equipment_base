from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from debug_toolbar.toolbar import debug_toolbar_urls

urlpatterns = [
    path("", include("ebase.urls")),
    path("", include("directory.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += debug_toolbar_urls()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = 'ООО "Фирма МЕДСИЛ" - Сервис'
admin.site.index_title = 'Администрирование учета сервисного оборудования'
