from django import forms

from .models import ExamAttempt


class ExamAttemptForm(forms.Form):
    exam_type = forms.ChoiceField(
        label='Imtihon turi', choices=ExamAttempt.ExamType.choices,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    exam_date = forms.DateField(
        label='Sana', widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    passed = forms.ChoiceField(
        label='Natija', choices=[('1', "O'tdi"), ('0', "O'tmadi")],
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    note = forms.CharField(label='Izoh', required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}))
