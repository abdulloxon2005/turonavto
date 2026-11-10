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


class TheoryLessonForm(forms.Form):
    group = forms.ModelChoiceField(queryset=None, label='Guruh')
    teacher = forms.ModelChoiceField(queryset=None, label="O'qituvchi")
    topic = forms.CharField(label='Mavzu', required=False, max_length=255)
    lesson_date = forms.DateField(label='Sana', widget=forms.DateInput(attrs={'type': 'date'}))
    start_time = forms.TimeField(label='Vaqt', widget=forms.TimeInput(attrs={'type': 'time'}))
    hours = forms.DecimalField(label='Soat', max_digits=4, decimal_places=1, min_value=0.5, initial=2)

    def __init__(self, *args, group_queryset=None, teacher_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.groups.models import Group

        self.fields['group'].queryset = group_queryset if group_queryset is not None else Group.objects.all()
        self.fields['teacher'].queryset = teacher_queryset
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')
