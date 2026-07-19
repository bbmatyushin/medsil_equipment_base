from django import forms

from business_trip.models import BusinessTrip


class BusinessTripForm(forms.ModelForm):
    """Форма командировки.

    Текстовые поля (задание, примечание, отчёт и т.д.) уменьшены до размера,
    аналогичного полю «Описание неисправности» на форме ремонта (rows=3).
    """

    class Meta:
        model = BusinessTrip
        fields = "__all__"
        widgets = {
            "task": forms.Textarea(attrs={"rows": 3}),
            "take_with": forms.Textarea(attrs={"rows": 3}),
            "comment": forms.Textarea(attrs={"rows": 3}),
            "report": forms.Textarea(attrs={"rows": 3}),
        }
