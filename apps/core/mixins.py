"""RBAC "Guard" qatlami: rol tekshiruvi view darajasida.

Qoida (texnik topshiriq, 10-bo'lim): rol mos kelmasa -> 403.
Egalik (ownership) mos kelmasa -> 404 (tegishli view/service'da Http404
ko'tariladi, bu yerda emas — chunki yozuvning mavjudligi oshkor bo'lmasligi kerak).
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles: tuple[str, ...] = ()

    def test_role(self):
        user = self.request.user
        return user.is_authenticated and user.role in self.allowed_roles

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not self.test_role():
            raise PermissionDenied("Bu amal uchun ruxsatingiz yo'q")
        return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = ('admin',)


class TeacherRequiredMixin(RoleRequiredMixin):
    allowed_roles = ('teacher',)


class InstructorRequiredMixin(RoleRequiredMixin):
    allowed_roles = ('instructor',)


class StaffRequiredMixin(RoleRequiredMixin):
    """O'qituvchi yoki instruktor (admin bo'lmagan hodimlar)."""

    allowed_roles = ('teacher', 'instructor')


class AnyRoleRequiredMixin(RoleRequiredMixin):
    allowed_roles = ('admin', 'teacher', 'instructor')


class AdminOrInstructorRequiredMixin(RoleRequiredMixin):
    allowed_roles = ('admin', 'instructor')
