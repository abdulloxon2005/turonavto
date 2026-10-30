from django import forms

from .models import Group


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'category', 'start_date', 'end_date', 'price', 'max_students', 'schedule']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name not in ('start_date', 'end_date'):
                field.widget.attrs.setdefault('class', 'form-control')
