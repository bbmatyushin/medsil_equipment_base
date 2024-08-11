from django import forms
from django.forms.widgets import URLInput
from django.db.models import Value, CharField, Q
from django.db.models.functions import Concat
from .models import *
from directory.models import MedDirection


class EquipmentAccountingForm(forms.ModelForm):
    dept = forms.ModelChoiceField(queryset=EquipmentAccounting.objects
                                  .annotate(n=Concat('equipment_acc_department_equipment_accounting__department__name',
                                                     Value(' ('),
                                                     'equipment_acc_department_equipment_accounting__department__city__name',
                                                     Value(')'),
                                                     output_field=CharField(),
                                                     )
                                            )
                                  # .filter(equipment_acc_department_equipment_accounting__isnull=False)
                                  .filter(Q(equipment_acc_department_equipment_accounting__department__isnull=False))
                                  .values_list('n', flat=True)
                                  .order_by('n')
                                  .distinct(),
                                  label='Подразделение'
                                  )
    engineer = forms.ModelChoiceField(queryset=EquipmentAccounting.objects
                                      .values_list('equipment_acc_department_equipment_accounting__engineer__name',
                                                   flat=True)
                                      .filter(equipment_acc_department_equipment_accounting__engineer__isnull=False)
                                      .order_by('equipment_acc_department_equipment_accounting__engineer__name')
                                      .distinct(),
                                      label='Инженер',
                                      help_text='Инженер, который запускал оборудование',
                                      required=False
                                      )

    department = forms.ModelChoiceField(queryset=Department.objects.all())

    url = forms.URLField(label='Ссылка на сайт')

    strip = forms.CharField(label='Строка', initial='http://109.172.114.134/')

    class Meta:
        model = EquipmentAccounting
        fields = '__all__'
