from django.contrib import admin
from .models import *


@admin.register(SparePart)
class SparePartAdmin(admin.ModelAdmin):
    list_display = ('article', 'name', 'unit', 'is_expiration', 'equipment_name')
    search_fields = ('name', 'article')
    ordering = ('name', 'article')
    list_select_related = ('unit',)

    fieldsets = (
        ('Новая запчасть', {'fields': ('article', ('name', 'unit'), 'is_expiration', 'equipment')}),

    )

    @admin.display(description='Оборудование')
    def equipment_name(self, obj):
        equipment_list = obj.equipment.values_list('full_name', flat=True)
        return ", ".join(equipment_list)
