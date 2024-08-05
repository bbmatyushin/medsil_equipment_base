from django.contrib import admin

from directory.models import PositionType
from .models import *
from directory.models import Position


@admin.register(CompanyUser)
class CompanyUserAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'patron', 'username', 'birth', 'phone',
                    'user_position',
                    'email_new', 'is_staff_new', 'date_joined', 'last_login', 'is_active',)
    list_display_links = ('username', 'first_name')
    list_filter = ('is_staff', 'is_active')
    search_fields = ('username', 'email')
    search_help_text = 'Поиск по имени пользователи или эл.почте'
    ordering = ('last_name',)

    @admin.display(description='Сотрудник', boolean=True)
    def is_staff_new(self, obj):
        return obj.is_staff

    @admin.display(description='Адрес эл.почты')
    def email_new(self, obj):
        return obj.email

    @admin.display(description='Должность')
    def user_position(self, obj):
        return obj.position.name

    # Переопределяет метод для выбора должностей. Будут видны только должности типа "Сотрудник"
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        fields = super().formfield_for_manytomany(db_field, request, **kwargs)
        if db_field.name == "position":
            fields.queryset = fields.queryset.filter(type='employee').order_by('name')
        return fields

    # для добавления блоков с полями при заполнени таблицы через админку
    fieldsets = (
        ('Логин и пароль нового пользователя', {'fields': ('username', 'password'),}),
        ('Персональная информация', {'fields': (('first_name', 'patron'), 'last_name', 'sex',
                                                'birth', ('phone', 'email'), 'position', )}),
        ('Разрешения', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        # ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )