from django import forms
from django.db.models import Sum
from .models import *


class SparePartForm(forms.ModelForm):
    class Meta:
        model = SparePart
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("equipment"):
            self.add_error('equipment',
                           error="Необходимо выбрать оборудование, для данной запчасти")
        # проверка, что существует уже запчасть с таким артикулом
        else:
            for eq in cleaned_data["equipment"]:
                # проверка что запчасть с данным артикулом уже есть у оборудования из списка
                # и что поле с артикулом было изменено
                if SparePart.objects.filter(equipment__full_name=eq.full_name, article=cleaned_data['article']) \
                        .exists() and "article" in self.changed_data:
                    self.add_error('article',
                                   f'Запчасть с артикулом "{cleaned_data["article"]}" для '
                                   f'"{eq.full_name}" уже существует')
        return cleaned_data


class SparePartCountForm(forms.ModelForm):
    class Meta:
        model = SparePartCount
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data['spare_part'].is_expiration and not cleaned_data['expiration_dt']:
            self.add_error('expiration_dt',
                           f'Для "{cleaned_data["spare_part"].name}" необходимо указать срок годности')
        return cleaned_data


class SparePartShipmentM2MForm(forms.ModelForm):
    class Meta:
        model = SparePartShipmentM2M
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Заменяем виджет поля expiration_dt на Select — варианты заполнит JS
        if 'expiration_dt' in self.fields:
            choices = [('', '--')]
            # Если редактируется существующая запись — добавляем текущий срок годности,
            # чтобы он отображался сразу до загрузки опций через JS
            if self.instance and self.instance.pk and self.instance.expiration_dt:
                val = self.instance.expiration_dt
                choices.append((val.isoformat(), val.strftime('%d.%m.%Y')))
            self.fields['expiration_dt'].widget = forms.Select(choices=choices)
            self.fields['expiration_dt'].required = False

    def clean(self):
        cleaned_data = super().clean()
        spare_part = cleaned_data.get('spare_part')
        expiration_dt = cleaned_data.get('expiration_dt')
        quantity = cleaned_data.get('quantity', 0)
        
        if spare_part:
            # Если у запчасти есть срок годности
            if spare_part.is_expiration:
                # Проверяем, что expiration_dt указан
                if not expiration_dt:
                    self.add_error(
                        'expiration_dt',
                        'Необходимо указать срок годности'
                    )
                else:
                    # Получаем доступные сроки годности из SparePartCount (с amount > 0)
                    available_dates = set(
                        SparePartCount.objects.filter(
                            spare_part=spare_part,
                            amount__gt=0
                        ).values_list('expiration_dt', flat=True)
                    )

                    # Для существующей записи: её собственный срок годности всегда валиден
                    # (даже если остаток по нему уже исчерпан — он был отгружен ранее)
                    is_existing = self.instance and self.instance.pk
                    if is_existing and self.instance.expiration_dt:
                        available_dates.add(self.instance.expiration_dt)
                    
                    # Проверяем, есть ли введённая дата среди доступных
                    if expiration_dt not in available_dates:
                        available_dates.discard(None)
                        formatted_dates = []
                        for date in sorted(available_dates):
                            if date:
                                formatted_dates.append(date.strftime('%d.%m.%Y'))
                        
                        if formatted_dates:
                            available_dates_str = ', '.join(formatted_dates)
                            self.add_error(
                                'expiration_dt',
                                f'Указанного срока годности нет на складе. '
                                f'Доступные сроки: {available_dates_str}'
                            )
                        else:
                            self.add_error(
                                'expiration_dt',
                                f'Для запчасти "{spare_part.name}" нет доступных сроков годности на складе'
                            )
            else:
                # Если у запчасти нет срока годности, устанавливаем expiration_dt в None
                cleaned_data['expiration_dt'] = None
            
            # --- Валидация количества: запрет отгрузки при отсутствии / нехватке остатка ---
            if quantity is not None and quantity > 0:
                count_filter = {'spare_part': spare_part}
                if expiration_dt is not None:
                    count_filter['expiration_dt'] = expiration_dt

                real_available = SparePartCount.objects.filter(**count_filter).aggregate(
                    total=Sum('amount')
                )['total'] or 0

                # --- Корректировка для существующих записей ---
                # Если запись уже существует, её текущее количество УЖЕ списано со склада.
                # Поэтому для проверки доступности прибавляем его обратно.
                # Если же запчасть или срок годности изменились — старое количество
                # будет возвращено на старый склад сигналом, поэтому не прибавляем.
                is_existing = self.instance and self.instance.pk
                already_shipped = 0
                if is_existing:
                    part_changed = (self.instance.spare_part_id != spare_part.pk)
                    exp_changed = (self.instance.expiration_dt != expiration_dt)
                    if not part_changed and not exp_changed:
                        # Запчасть и срок не изменились — текущее кол-во уже списано
                        already_shipped = self.instance.quantity or 0

                effective_available = real_available + already_shipped

                # Вспомогательные форматтеры
                exp_suffix = f' (срок {expiration_dt.strftime("%d.%m.%Y")})' if expiration_dt else ''
                fmt_qty = lambda v: int(v) if v % 1 == 0 else v

                if effective_available <= 0:
                    if already_shipped > 0:
                        msg = (f'Недостаточно кол-ва на складе: '
                               f'остаток {fmt_qty(real_available)}, '
                               f'уже отгружено {fmt_qty(already_shipped)}, '
                               f'запрошено {fmt_qty(quantity)}'
                               f'{exp_suffix}')
                    else:
                        msg = (f'Запчасть «{spare_part.name}» отсутствует на складе'
                               f'{exp_suffix} — отгрузка невозможна')
                    self.add_error('quantity', msg)
                elif quantity > effective_available:
                    if already_shipped > 0:
                        msg = (f'Недостаточно кол-ва на складе: '
                               f'остаток {fmt_qty(real_available)}, '
                               f'уже отгружено {fmt_qty(already_shipped)}, '
                               f'запрошено {fmt_qty(quantity)}'
                               f'{exp_suffix}')
                    else:
                        msg = (f'Недостаточно кол-ва на складе: '
                               f'доступно {fmt_qty(effective_available)}, '
                               f'запрошено {fmt_qty(quantity)}'
                               f'{exp_suffix}')
                    self.add_error('quantity', msg)
            elif quantity is not None and quantity <= 0:
                self.add_error('quantity', 'Количество должно быть больше нуля')
        
        return cleaned_data


class SparePartShipmentV2Form(forms.ModelForm):
    comment = forms.CharField(
        label='Комментарий',
        required=False,
        widget=forms.widgets.Textarea(attrs={
            'rows': 4,  # уменьшаем высоту до 4 строк
            "cols": 60,
            'style': 'resize: both; max-width: 600px; max-height: 250px;',  # разрешаем изменять только по высоте
            'placeholder': "Введите комментарий к отгрузке...",
        })
    )

    class Meta:
        model = SparePartShipmentV2
        exclude = ("id", "is_auto_comment",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # запрещаем редактировать поле комментарий, если оно было создано автоматически
        if self.instance.is_auto_comment:
            self.fields['comment'].widget.attrs.pop('placeholder')
            self.fields['comment'].widget.attrs['disabled'] = True


class SparePartShipmentForm(forms.ModelForm):
    comment = forms.CharField(
        label='Комментарий',
        required=False,
        widget=forms.widgets.Textarea(attrs={
            'rows': 4,  # уменьшаем высоту до 4 строк
            "cols": 60,
            'style': 'resize: both; max-width: 600px; max-height: 250px;',  # разрешаем изменять только по высоте
            'placeholder': "Введите комментарий к отгрузке...",
        })
    )

    class Meta:
        model = SparePartShipment
        fields = '__all__'
        # exclude = ('is_auto_comment',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # запрещаем редактировать поле комментарий, если оно было создано автоматически
        if self.instance.is_auto_comment:
            self.fields['comment'].widget.attrs.pop('placeholder')
            self.fields['comment'].widget.attrs['disabled'] = True

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


class SparePartSupplyV2Form(forms.ModelForm):
    note = forms.CharField(
        label='Примечание',
        required=False,
        widget=forms.widgets.Textarea(attrs={
            'rows': 2,
            'cols': 60,
            'style': 'resize: vertical; max-width: 600px; max-height: 150px;',
            'placeholder': "Введите примечание к поставке...",
        })
    )

    class Meta:
        model = SparePartSupplyV2
        fields = '__all__'


class SparePartSupplyForm(forms.ModelForm):
    class Meta:
        model = SparePartSupply
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data['spare_part'].is_expiration and not cleaned_data['expiration_dt']:
            self.add_error('expiration_dt',
                           f'Для "{cleaned_data["spare_part"].name}" необходимо указать срок годности')
        return cleaned_data
