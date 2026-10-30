from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('qarzdorlar/', views.DebtorsListView.as_view(), name='debtors'),
    path('kassa/', views.CashClosingListView.as_view(), name='cash_list'),
    path('kassa/yopish/', views.CashClosingCreateView.as_view(), name='cash_create'),
    path('kassa/<int:pk>/', views.CashClosingDetailView.as_view(), name='cash_detail'),
    path('kassa/<int:pk>/tasdiqlash/', views.CashClosingApproveView.as_view(), name='cash_approve'),
    path('oquvchi/<int:student_id>/kursga-yozish/', views.EnrollmentCreateView.as_view(), name='enrollment_create'),
    path('oquvchi/<int:student_id>/tolov/', views.PaymentCreateView.as_view(), name='payment_create'),
    path('enrollment/<int:pk>/', views.EnrollmentDetailView.as_view(), name='enrollment_detail'),
    path('enrollment/<int:pk>/grafik/', views.EnrollmentScheduleView.as_view(), name='enrollment_schedule'),
    path('enrollment/<int:pk>/chegirma/', views.EnrollmentDiscountView.as_view(), name='enrollment_discount'),
    path('<int:pk>/', views.PaymentDetailView.as_view(), name='detail'),
    path('<int:pk>/chek/', views.PaymentReceiptView.as_view(), name='receipt'),
    path('<int:pk>/bekor-qilish/', views.PaymentCancelView.as_view(), name='cancel'),
    path('<int:pk>/qaytarish/', views.PaymentRefundView.as_view(), name='refund'),
]
