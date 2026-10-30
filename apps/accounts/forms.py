from django import forms
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.core.exceptions import ValidationError

from .models import User


class LoginForm(forms.Form):
    phone = forms.CharField(label='Telefon raqami', max_length=20)
    password = forms.CharField(label='Parol', widget=forms.PasswordInput)


class BootstrapFieldsMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class ForcedPasswordChangeForm(BootstrapFieldsMixin, SetPasswordForm):
    """Birinchi kirishda majburiy parol almashtirish (eski parol so'ralmaydi,
    chunki foydalanuvchi allaqachon shu parol bilan autentifikatsiyadan o'tgan)."""


class ChangePasswordForm(BootstrapFieldsMixin, PasswordChangeForm):
    """Ixtiyoriy parol almashtirish (sozlamalardan), eski parol talab qilinadi."""


class StaffForm(forms.ModelForm):
    is_active = forms.BooleanField(label='Faol', required=False, initial=True)

    class Meta:
        model = User
        fields = ['full_name', 'phone', 'role', 'is_active']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_role(self):
        role = self.cleaned_data['role']
        if role == User.Role.ADMIN:
            raise ValidationError("Admin hisobini bu shaklda yaratish mumkin emas")
        return role
