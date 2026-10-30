from django.urls import path

from . import views

app_name = 'expenses'

urlpatterns = [
    path('', views.ExpenseListView.as_view(), name='list'),
    path('yangi/', views.ExpenseCreateView.as_view(), name='create'),
    path('<int:pk>/', views.ExpenseDetailView.as_view(), name='detail'),
]
