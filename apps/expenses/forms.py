from django import forms

from apps.accounts.models import User

from .models import Expense


class ExpenseForm(forms.Form):
    category = forms.ChoiceField(label='Turi', choices=Expense.Category.choices)
    amount = forms.IntegerField(label='Summa', min_value=1)
    expense_date = forms.DateField(label='Sana', widget=forms.DateInput(attrs={'type': 'date'}))
    description = forms.CharField(label='Izoh', max_length=255)
    paid_to_user = forms.ModelChoiceField(
        label='Xodim (agar bo\'lsa)', queryset=User.objects.exclude(role=User.Role.ADMIN),
        required=False,
    )
    paid_to_name = forms.CharField(label='Qabul qiluvchi (xodim bo\'lmasa)', max_length=150, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('paid_to_user') and cleaned.get('paid_to_name'):
            raise forms.ValidationError(
                "Xodim yoki ism, ikkalasini birga kiritmang"
            )
        return cleaned


class ExpenseFilterForm(forms.Form):
    category = forms.ChoiceField(label='Turi', choices=[('', 'Barcha turlar')] + list(Expense.Category.choices), required=False)
    paid_to_user = forms.ModelChoiceField(
        label='Xodim', queryset=User.objects.exclude(role=User.Role.ADMIN), required=False,
    )
    date_from = forms.DateField(label='Sanadan', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(label='Sanagacha', required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-select' if isinstance(field, forms.ChoiceField) else 'form-control')
