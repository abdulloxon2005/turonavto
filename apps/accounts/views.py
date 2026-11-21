from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.mixins import AdminRequiredMixin
from apps.core.services import log_action

from .forms import ChangePasswordForm, ForcedPasswordChangeForm, LoginForm, StaffForm
from .models import User
from .services import create_staff, reset_password, set_active, update_staff


class LoginView(View):
    template_name = 'accounts/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        if request.GET.get('expired'):
            messages.info(request, "Uzoq vaqt faol bo'lmaganingiz sababli tizimdan chiqarildingiz. Qayta kiring.")
        return render(request, self.template_name, {'form': LoginForm()})

    def post(self, request):
        form = LoginForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        phone = form.cleaned_data['phone'].strip()
        password = form.cleaned_data['password']

        user = authenticate(request, phone=phone, password=password)
        if user is None:
            messages.error(request, "Telefon raqami yoki parol noto'g'ri")
            return render(request, self.template_name, {'form': form})

        if not user.is_active:
            messages.error(request, 'Hisobingiz bloklangan. Administratorga murojaat qiling.')
            return render(request, self.template_name, {'form': form})

        login(request, user)
        log_action(user, action='auth.login', entity_type='User', entity_id=user.pk)

        if user.must_change_password:
            return redirect('accounts:force_password_change')
        return redirect('core:dashboard')


class LogoutView(LoginRequiredMixin, View):
    def post(self, request):
        log_action(request.user, action='auth.logout', entity_type='User', entity_id=request.user.pk)
        logout(request)
        return redirect('accounts:login')


class ForcedPasswordChangeView(LoginRequiredMixin, View):
    template_name = 'accounts/force_password_change.html'

    def get(self, request):
        if not request.user.must_change_password:
            return redirect('core:dashboard')
        return render(request, self.template_name, {'form': ForcedPasswordChangeForm(request.user)})

    def post(self, request):
        form = ForcedPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.must_change_password = False
            user.save()
            update_session_auth_hash(request, user)
            log_action(user, action='auth.password_changed', entity_type='User', entity_id=user.pk)
            messages.success(request, "Parol muvaffaqiyatli o'zgartirildi")
            return redirect('core:dashboard')
        return render(request, self.template_name, {'form': form})


class ChangePasswordView(LoginRequiredMixin, View):
    template_name = 'accounts/change_password.html'

    def get(self, request):
        return render(request, self.template_name, {'form': ChangePasswordForm(request.user)})

    def post(self, request):
        form = ChangePasswordForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            log_action(user, action='auth.password_changed', entity_type='User', entity_id=user.pk)
            messages.success(request, "Parol muvaffaqiyatli o'zgartirildi")
            return redirect('core:dashboard')
        return render(request, self.template_name, {'form': form})


class StaffListView(AdminRequiredMixin, ListView):
    model = User
    template_name = 'accounts/staff_list.html'
    context_object_name = 'staff_list'
    paginate_by = 20

    def get_queryset(self):
        qs = User.objects.exclude(role=User.Role.ADMIN)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(full_name__icontains=q) | Q(phone__icontains=q))
        role = self.request.GET.get('role', '').strip()
        if role in (User.Role.TEACHER, User.Role.INSTRUCTOR):
            qs = qs.filter(role=role)
        active = self.request.GET.get('active', '').strip()
        if active in ('0', '1'):
            qs = qs.filter(is_active=(active == '1'))
        return qs.order_by('full_name')


class StaffCreateView(AdminRequiredMixin, View):
    template_name = 'accounts/staff_form.html'

    def get(self, request):
        return render(request, self.template_name, {'form': StaffForm()})

    def post(self, request):
        form = StaffForm(request.POST, request.FILES)
        if form.is_valid():
            user, temp_password = create_staff(
                request.user,
                full_name=form.cleaned_data['full_name'],
                phone=form.cleaned_data['phone'],
                role=form.cleaned_data['role'],
                photo=request.FILES.get('photo'),
            )
            messages.success(
                request,
                f"Hodim qo'shildi. Vaqtinchalik parol: {temp_password} "
                "(bu parolni hodimga yetkazing, u birinchi kirishda almashtiradi)",
            )
            return redirect('accounts:staff_detail', pk=user.pk)
        return render(request, self.template_name, {'form': form})


class StaffDetailView(AdminRequiredMixin, DetailView):
    model = User
    template_name = 'accounts/staff_detail.html'
    context_object_name = 'staff'

    def get_queryset(self):
        return User.objects.exclude(role=User.Role.ADMIN)


class StaffUpdateView(AdminRequiredMixin, UpdateView):
    model = User
    form_class = StaffForm
    template_name = 'accounts/staff_form.html'

    def get_queryset(self):
        return User.objects.exclude(role=User.Role.ADMIN)

    def form_valid(self, form):
        update_staff(
            self.request.user,
            self.object,
            full_name=form.cleaned_data['full_name'],
            phone=form.cleaned_data['phone'],
            is_active=form.cleaned_data['is_active'],
            photo=self.request.FILES.get('photo'),
            remove_photo=self.request.POST.get('remove_photo') == '1',
        )
        messages.success(self.request, "Hodim ma'lumotlari yangilandi")
        return redirect('accounts:staff_detail', pk=self.object.pk)


class StaffToggleActiveView(AdminRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User.objects.exclude(role=User.Role.ADMIN), pk=pk)
        set_active(request.user, user, not user.is_active)
        messages.success(request, 'Holat yangilandi')
        return redirect('accounts:staff_detail', pk=user.pk)


class StaffResetPasswordView(AdminRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User.objects.exclude(role=User.Role.ADMIN), pk=pk)
        temp_password = reset_password(request.user, user)
        messages.success(request, f'Yangi vaqtinchalik parol: {temp_password}')
        return redirect('accounts:staff_detail', pk=user.pk)
