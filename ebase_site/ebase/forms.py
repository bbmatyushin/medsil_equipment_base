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
            'equipment': forms.TextInput(attrs={'style': 'width: 100px;'}),
        }
