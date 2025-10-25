from django import forms
from django.forms.widgets import URLInput
from django.db.models import Value, CharField, Q
from django.db.models.functions import Concat
from django.utils.safestring import mark_safe
from .models import *
from spare_part.models import SparePart
from directory.models import MedDirection


class ButtonWidget(forms.Widget):
    def render(self, name, value, attrs=None, renderer=None):
        return mark_safe(f'''
        <button type="button" 
                id="{attrs.get('id')}" 
                class="search-equipment-button">
            {value or 'Поиск'}
        </button>
        ''')


def get_equipment_for_form() -> tuple:
    """Вернет картеж для поля формы ChoiceField"""
    qs = Equipment.objects.values_list("pk", "full_name",)
    return qs


class EquipmentAccountingForm(forms.ModelForm):
    class Meta:
        model = EquipmentAccounting
        fields = '__all__'
        widgets = {
            'comment': forms.Textarea(attrs={
                'rows': 4,  # уменьшаем высоту до 4 строк
                "cols": 60,
                'style': 'resize: both; max-width: 600px; max-height: 250px;',  # разрешаем изменять только по высоте
                'placeholder': "Введите комменарий для данного оборудования...",
            }),
        }


class ServiceForm(forms.ModelForm):
    search_equipment = forms.CharField(
        required=False,
        label="Поиск оборудования",
        help_text="Поиск по названию или серийному номеру",
        empty_value=""
    )
    search_button = forms.CharField(
        required=False,
        widget=ButtonWidget,
        label='',  # ширину поля для label задаем в custom_form.css стр.126
    )
    contact_person = forms.ModelChoiceField(
        queryset=DeptContactPers.objects.all(),
        required=False,
        label="Контактное лицо",
        help_text="Выберите контактное лицо для актов"
    )

    class Meta:
        model = Service
        fields = "__all__"
