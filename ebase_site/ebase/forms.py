from django import forms
from django.forms.widgets import URLInput
from django.db.models import Value, CharField, Q
from django.db.models.functions import Concat
from .models import *
from directory.models import MedDirection


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
