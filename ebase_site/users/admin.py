from django.contrib import admin
from .models import *


@admin.register(CompanyUser)
class CompanyUserAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'patron', 'username', 'birth', 'phone',
                    'email_new', 'is_staff_new', 'date_joined', 'last_login', 'is_active',)
    list_filter = ('is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('last_name',)

    @admin.display(description='Сотрудник', boolean=True)
    def is_staff_new(self, obj):
        return obj.is_staff

    @admin.display(description='Адрес эл.почты')
    def email_new(self, obj):
        return obj.email

    # для добавления блоков с полями при заполнени таблицы через админку
    fieldsets = (
        ('Логин и пароль нового пользователя', {'fields': ('username', 'password')}),
        ('Персональная информация', {'fields': ('first_name', 'last_name', 'patron', 'sex', 'birth', 'phone', 'email')}),
        ('Разрешения', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        # ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )