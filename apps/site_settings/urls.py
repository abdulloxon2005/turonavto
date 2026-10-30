from django.urls import path

from . import views

app_name = 'site_settings'

urlpatterns = [
    path('', views.SettingsEditView.as_view(), name='edit'),
]
