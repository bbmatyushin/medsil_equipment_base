from django.contrib import admin

from business_trip.models import ExpenseType
from utils import MainModelAdmin


@admin.register(ExpenseType)
class ExpenseTypeAdmin(MainModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    search_help_text = "Поиск по наименованию вида затрат"

    fieldsets = (("Новый вид затрат", {"fields": ("name",)}),)
