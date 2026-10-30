from django.urls import path

from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.ReportsIndexView.as_view(), name='index'),
    path('tushum/', views.RevenueReportView.as_view(), name='revenue'),
    path('guruhlar/', views.GroupsReportView.as_view(), name='groups'),
    path('hodimlar/', views.StaffReportView.as_view(), name='staff'),
    path('qarzdorlar/', views.DebtorsReportView.as_view(), name='debtors'),
    path('kutilayotgan/', views.UpcomingRevenueReportView.as_view(), name='upcoming'),
    path('kassa/', views.CashReportView.as_view(), name='cash'),
]
