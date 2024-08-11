from django import template
from directory.models import MedDirection, City


register = template.Library()


@register.simple_tag()
def get_med_direction():
    return MedDirection.objects.values('name', 'slug_name').distinct()\
            .order_by('name')


@register.simple_tag()
def get_cities():
    return City.objects.values_list('name', flat=True).distinct().order_by('name')
