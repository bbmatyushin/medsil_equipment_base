from django import template
from ebase.models import Service, Equipment
from spare_part.models import SparePart


register = template.Library()

@register.simple_tag()
def get_equipment_list():
    """Получаем список всех оборудований"""
    return Equipment.objects.values('id', 'short_name',)
