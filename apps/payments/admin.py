from django.contrib import admin

from .models import CashClosing, Enrollment, Payment, PaymentSchedule


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'group', 'price', 'discount', 'total_due', 'created_at')
    search_fields = ('student__full_name',)


@admin.register(PaymentSchedule)
class PaymentScheduleAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'due_date', 'amount', 'paid_amount', 'status')
    list_filter = ('status',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('receipt_no', 'student', 'amount', 'method', 'status', 'paid_at')
    list_filter = ('status', 'method', 'is_refund')
    search_fields = ('receipt_no', 'student__full_name')


@admin.register(CashClosing)
class CashClosingAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'expected_amount', 'declared_amount', 'status')
    list_filter = ('status',)
