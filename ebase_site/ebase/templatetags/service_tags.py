from django import template
from ebase.models import Equipment


register = template.Library()


@register.simple_tag()
def get_equipment_list():
    """Получаем список всех оборудований"""
    return Equipment.objects.values('id', 'short_name',)
