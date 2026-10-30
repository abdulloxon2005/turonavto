from django.contrib import admin

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('category', 'amount', 'expense_date', 'recipient_display', 'created_by')
    list_filter = ('category', 'expense_date')
    search_fields = ('description', 'paid_to_name', 'paid_to_user__full_name')
    date_hierarchy = 'expense_date'
