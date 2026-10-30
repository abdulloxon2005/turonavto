from django import forms
from django.forms import formset_factory

from apps.groups.models import Group

from .models import Payment


class BootstrapFieldsMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class EnrollmentForm(BootstrapFieldsMixin, forms.Form):
    group = forms.ModelChoiceField(queryset=Group.objects.none(), label='Guruh')
    price = forms.IntegerField(label="Kurs narxi (so'm)", min_value=0)
    discount = forms.IntegerField(label='Chegirma', min_value=0, required=False, initial=0)
    discount_reason = forms.CharField(label='Chegirma sababi', required=False, widget=forms.TextInput)

    def __init__(self, *args, student=None, **kwargs):
        super().__init__(*args, **kwargs)
        if student is not None:
            self.fields['group'].queryset = Group.objects.filter(
                group_students__student=student, group_students__left_at__isnull=True
            ).distinct()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('discount') and not cleaned.get('discount_reason'):
            self.add_error('discount_reason', "Chegirma sababi ko'rsatilishi shart")
        return cleaned


class ScheduleItemForm(BootstrapFieldsMixin, forms.Form):
    amount = forms.IntegerField(label='Summa', min_value=1)
    due_date = forms.DateField(label='Muddat', widget=forms.DateInput(attrs={'type': 'date'}))


ScheduleFormSet = formset_factory(ScheduleItemForm, extra=3, can_delete=True)


class DiscountForm(BootstrapFieldsMixin, forms.Form):
    discount = forms.IntegerField(label='Chegirma', min_value=0)
    discount_reason = forms.CharField(label='Sabab', widget=forms.Textarea(attrs={'rows': 2}))


class PaymentForm(BootstrapFieldsMixin, forms.Form):
    enrollment = forms.ChoiceField(label='Guruh (enrollment)')
    amount = forms.IntegerField(label='Summa', min_value=1)
    method = forms.ChoiceField(label='Usul', choices=Payment.Method.choices)
    note = forms.CharField(label='Izoh', required=False, widget=forms.TextInput)

    def __init__(self, *args, enrollment_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['enrollment'].choices = enrollment_choices


class CancelPaymentForm(BootstrapFieldsMixin, forms.Form):
    reason = forms.CharField(label='Sabab', widget=forms.Textarea(attrs={'rows': 2}))


class RefundPaymentForm(BootstrapFieldsMixin, forms.Form):
    amount = forms.IntegerField(label='Qaytariladigan summa', min_value=1)
    note = forms.CharField(label='Izoh', required=False, widget=forms.TextInput)


class CashCloseForm(BootstrapFieldsMixin, forms.Form):
    declared_amount = forms.IntegerField(label="Qo'lingizdagi naqd summa", min_value=0)


class CashApproveForm(BootstrapFieldsMixin, forms.Form):
    note = forms.CharField(label='Izoh', required=False, widget=forms.Textarea(attrs={'rows': 2}))
