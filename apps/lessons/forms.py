from django import forms

from apps.students.models import Student


class LessonForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.none(), label="O'quvchi")
    lesson_date = forms.DateField(label='Sana', widget=forms.DateInput(attrs={'type': 'date'}))
    start_time = forms.TimeField(label='Vaqt', widget=forms.TimeInput(attrs={'type': 'time'}))
    hours = forms.DecimalField(label='Soat', max_digits=4, decimal_places=1, min_value=0.5, initial=1)

    def __init__(self, *args, student_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if student_queryset is not None:
            self.fields['student'].queryset = student_queryset
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')
