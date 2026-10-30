from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mixins import AdminRequiredMixin

from .forms import ExpenseFilterForm, ExpenseForm
from .models import Expense
from .services import create_expense, expenses_queryset, total_amount


class ExpenseListView(AdminRequiredMixin, ListView):
    model = Expense
    template_name = 'expenses/expense_list.html'
    context_object_name = 'expenses'
    paginate_by = 30

    def get_filter_form(self):
        return ExpenseFilterForm(self.request.GET or None)

    def get_queryset(self):
        form = self.get_filter_form()
        filters = {}
        if form.is_valid():
            filters = {
                'category': form.cleaned_data.get('category') or None,
                'paid_to_user': form.cleaned_data.get('paid_to_user') or None,
                'date_from': form.cleaned_data.get('date_from') or None,
                'date_to': form.cleaned_data.get('date_to') or None,
            }
        return expenses_queryset(**filters)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.get_filter_form()
        context['total'] = total_amount(self.get_queryset())
        return context


class ExpenseDetailView(AdminRequiredMixin, DetailView):
    model = Expense
    template_name = 'expenses/expense_detail.html'
    context_object_name = 'expense'


class ExpenseCreateView(AdminRequiredMixin, View):
    template_name = 'expenses/expense_form.html'

    def get(self, request):
        return render(request, self.template_name, {'form': ExpenseForm()})

    def post(self, request):
        form = ExpenseForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})
        try:
            create_expense(
                request.user,
                category=form.cleaned_data['category'],
                amount=form.cleaned_data['amount'],
                expense_date=form.cleaned_data['expense_date'],
                description=form.cleaned_data['description'],
                paid_to_user=form.cleaned_data.get('paid_to_user'),
                paid_to_name=form.cleaned_data.get('paid_to_name', ''),
            )
        except ValidationError as exc:
            messages.error(request, getattr(exc, 'message', str(exc)))
            return render(request, self.template_name, {'form': form})
        messages.success(request, "Xarajat qo'shildi")
        return redirect('expenses:list')
