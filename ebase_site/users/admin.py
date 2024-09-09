from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin

from .models import *


@admin.register(CompanyUser)
class CompanyUserAdmin(UserAdmin):
    actions = ('set_admin', 'cancel_admin', 'set_active', 'cancel_active',)
    list_display = ('last_name', 'first_name', 'patron', 'username', 'birth', 'phone',
                    'user_position',
                    'email_new', 'is_staff_new', 'date_joined', 'last_login', 'is_active',)
    list_display_links = ('username', 'first_name')
    # autocomplete_fields = ('position',)
    # list_filter = ('is_staff', 'is_active')
    search_fields = ('username', 'email')
    search_help_text = 'Поиск по имени пользователи или эл.почте'
    ordering = ('last_name',)

    fieldsets = (
        ('Логин и пароль нового пользователя', {'fields': ('username', 'password'), }),
        ('Персональная информация', {'fields': (('first_name', 'patron'), 'last_name', 'sex',
                                                'birth', ('phone', 'email'), 'position',)}),
        ('Разрешения', {
            'classes': ('collapse',),
            'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        # ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    @admin.display(description='Сотрудник', boolean=True)
    def is_staff_new(self, obj):
        return obj.is_staff

    @admin.display(description='Адрес эл.почты')
    def email_new(self, obj):
        return obj.email

    @admin.display(description='Должность')
    def user_position(self, obj):
        return ", ".join(obj.position.values_list('name', flat=True))

    @admin.action(description='Назначить права администратора')
    def set_admin(self, request, queryset):
        """Действие для массового наделения прав администартора"""
        if (request.user.is_superuser or request.user.is_staff) and not request.user.is_anonymous:
            count = queryset.update(is_staff=True)
            self.message_user(request, message=f'Права администратора выдано {count} пользователям')
        else:
            self.message_user(request, message='Ошибка назначения прав! Вы должны обладать правами '
                                               'суперпользователя или администратора.',
                              level=messages.ERROR)

    @admin.action(description='Отозвать права администратора')
    def cancel_admin(self, request, queryset):
        """Действие для массовой отмены прав администартора"""
        if (request.user.is_superuser or request.user.is_staff) and not request.user.is_anonymous:
            count = queryset.update(is_staff=False)
            self.message_user(request, message=f'Права администратора были отозваны у {count} пользователей',
                              level=messages.WARNING)
        else:
            self.message_user(request, message='Ошибка назначения прав! Вы должны обладать правами '
                                               'суперпользователя или администратора.',
                              level=messages.ERROR)

    @admin.action(description='Сделать пользователей активными')
    def set_active(self, request, queryset):
        """Действие для массового включения пользователей"""
        if request.user.is_superuser and not request.user.is_anonymous:
            count = queryset.update(is_active=True)
            self.message_user(request, message=f'Активировано {count} пользователей')
        else:
            self.message_user(request, message='Ошибка активации пользователей! Вы должны обладать правами '
                                               'суперпользователя.',
                              level=messages.ERROR)

    @admin.action(description='Сделать пользователей НЕактивными')
    def cancel_active(self, request, queryset):
        """Действие для массового отключения пользователей"""
        if request.user.is_superuser and not request.user.is_anonymous:
            count = queryset.update(is_active=False)
            self.message_user(request, message=f'{count} пользователей стали неактивными',
                              level=messages.WARNING)
        else:
            self.message_user(request, message='Ошибка деактивации пользователей! Вы должны обладать правами '
                                               'суперпользователя.',
                              level=messages.ERROR)

    # Переопределяет метод для выбора должностей. Будут видны только должности типа "Сотрудник"
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        fields = super().formfield_for_manytomany(db_field, request, **kwargs)
        if db_field.name == "position":
            fields.queryset = fields.queryset.filter(type='employee').order_by('name')
        return fields

    # для добавления блоков с полями при заполнени таблицы через админку

