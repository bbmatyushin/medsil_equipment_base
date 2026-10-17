from django.contrib.admin.apps import AdminConfig


class EbaseAdminConfig(AdminConfig):
    """Админка Django с сайтом проекта `EbaseAdminSite` вместо стандартного."""

    default_site = "ebase_site.admin.EbaseAdminSite"
