from django.urls import path

from . import views

app_name = 'groups'

urlpatterns = [
    path('', views.GroupListView.as_view(), name='list'),
    path('yangi/', views.GroupCreateView.as_view(), name='create'),
    path('<int:pk>/', views.GroupDetailView.as_view(), name='detail'),
    path('<int:pk>/tahrirlash/', views.GroupUpdateView.as_view(), name='update'),
    path('<int:pk>/holat/<str:action>/', views.GroupStatusActionView.as_view(), name='status_action'),
    path('<int:pk>/ochirish/', views.GroupDeleteView.as_view(), name='delete'),
    path('<int:pk>/hodim/', views.GroupStaffAssignView.as_view(), name='staff_assign'),
    path('<int:pk>/oquvchi-qidirish/', views.GroupStudentSearchView.as_view(), name='student_search'),
    path('<int:pk>/oquvchi-qoshish/', views.GroupStudentAddView.as_view(), name='student_add'),
    path('<int:pk>/oquvchi/<int:student_id>/chiqarish/', views.GroupStudentRemoveView.as_view(), name='student_remove'),
    path('<int:pk>/oquvchi/<int:student_id>/kochirish/', views.GroupStudentMoveView.as_view(), name='student_move'),
]
