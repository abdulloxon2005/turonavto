from django import forms


class SettingsForm(forms.Form):
    center_name = forms.CharField(label='Markaz nomi', max_length=255)
    payment_methods = forms.MultipleChoiceField(
        label="To'lov usullari",
        choices=[('cash', 'Naqd'), ('card', 'Karta'), ('transfer', "O'tkazma"), ('click', 'Click'), ('payme', 'Payme')],
        widget=forms.CheckboxSelectMultiple,
    )
    reminder_days_before = forms.IntegerField(label="Muddat o'tish kunlari (eslatma)", min_value=1, max_value=30)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'payment_methods':
                field.widget.attrs.setdefault('class', 'form-control')
