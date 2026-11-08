from django.urls import path

from . import views

app_name = 'site_settings'

urlpatterns = [
    path('', views.SettingsEditView.as_view(), name='edit'),
    path('kirish-nazorati/', views.AccessControlView.as_view(), name='access_control'),
    path('kirish-nazorati/<int:pk>/holat/', views.StaffAccessToggleView.as_view(), name='staff_access_toggle'),
]
