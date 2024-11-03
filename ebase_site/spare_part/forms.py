from django import forms
from .models import *


class SparePartCountForm(forms.ModelForm):
    class Meta:
        model = SparePartCount
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data['spare_part'].is_expiration and not cleaned_data['expiration_dt']:
            self.add_error('expiration_dt',
                           f'Для "{cleaned_data["spare_part"].name}" неоходимо указать срок годности')
        return cleaned_data


class SparePartShipmentForm(forms.ModelForm):
    # spare_part_available = forms.CharField(label='Доступно')
    class Meta:
        model = SparePartShipment
        fields = '__all__'

    # Отрабатывает после нажатия кнопки "Сохранить"
    def clean(self):
        cleaned_data = super().clean()
        count_shipment = cleaned_data.get('count_shipment')
        spare_part_count = cleaned_data.get('spare_part_count')

        try:
            # spare_part_count = SparePartCount.objects.get(spare_part=spare_part_id, expiration_dt=expiration_dt,)
            if count_shipment > spare_part_count.amount:
                self.add_error('count_shipment',
                               'Количество запчастей для отгрузки не может превышать доступное количество.')
            elif count_shipment == 0:
                self.add_error('count_shipment',
                               'Количество запчастей для отгрузки не может быть равно нулю.')
        except SparePartCount.DoesNotExist:
            # не используется, т.к. экземпляр spare_part_count всегда будет получен
            self.add_error('count_shipment', 'Остаток для данной запчасти отсутствуют.')

        return cleaned_data


class SparePartSupplyForm(forms.ModelForm):
    class Meta:
        model = SparePartSupply
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data['spare_part'].is_expiration and not cleaned_data['expiration_dt']:
            self.add_error('expiration_dt',
                           f'Для "{cleaned_data["spare_part"].name}" неоходимо указать срок годности')
        return cleaned_data
