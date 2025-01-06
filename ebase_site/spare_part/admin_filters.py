from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Value
from django.db.models.functions import Concat, Trim

CompanyUser = get_user_model()


class WhoShipment(admin.SimpleListFilter):
    title = 'Кто отгрузил'
    parameter_name = 'user'

    users = CompanyUser.objects \
        .annotate(fio=Trim(Concat('last_name', Value(' '), 'first_name'))) \
        .filter(position__name__in=['инженер']) \
        .values_list('username', 'fio')

    def lookups(self, request, model_admin):
        return list(self.users)

    def queryset(self, request, queryset):
        if self.value():  # здесь будет username выбранного фильтра
            return queryset.filter(user__username=self.value())
        return queryset