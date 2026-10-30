from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='list'),
    path('<int:pk>/oqildi/', views.NotificationMarkReadView.as_view(), name='mark_read'),
    path('barchasi-oqildi/', views.NotificationMarkAllReadView.as_view(), name='mark_all_read'),
]
