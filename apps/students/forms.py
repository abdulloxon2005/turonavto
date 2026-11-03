from django import forms

from apps.groups.models import Group

from .models import DeleteRequest, Student


class StudentForm(forms.ModelForm):
    group = forms.ModelChoiceField(
        queryset=Group.objects.none(), required=False, label='Guruh',
        help_text="Qo'shilayotgan guruh",
    )
    confirm_duplicate = forms.BooleanField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Student
        fields = ['full_name', 'phone', 'phone2', 'passport_no', 'birth_date', 'address', 'photo', 'note']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, user=None, group_required=False, is_create=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        for name, field in self.fields.items():
            if name not in ('birth_date', 'photo', 'confirm_duplicate'):
                field.widget.attrs.setdefault('class', 'form-control')

        if is_create and user is not None:
            if user.is_admin():
                self.fields['group'].queryset = Group.objects.filter(status=Group.Status.OPEN)
            elif user.is_teacher():
                self.fields['group'].queryset = Group.objects.filter(
                    status=Group.Status.OPEN, group_teachers__user=user
                ).distinct()
                self.fields['group'].required = True
            elif user.is_instructor():
                self.fields['group'].queryset = Group.objects.filter(status=Group.Status.OPEN)
                self.fields['group'].required = True
        else:
            del self.fields['group']


class DeleteRequestForm(forms.Form):
    reason = forms.CharField(label='Sabab', widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))


class DeleteRequestDecisionForm(forms.Form):
    note = forms.CharField(
        label='Izoh', required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )


class StudentExcelImportForm(forms.Form):
    group = forms.ModelChoiceField(
        queryset=Group.objects.none(),
        required=True,
        label='Guruh',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    excel_file = forms.FileField(
        label='Excel fayl (.xlsx)',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.xlsx'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            if user.is_admin() or user.is_instructor():
                self.fields['group'].queryset = Group.objects.filter(status=Group.Status.OPEN)
            elif user.is_teacher():
                self.fields['group'].queryset = Group.objects.filter(
                    status=Group.Status.OPEN, group_teachers__user=user
                ).distinct()

