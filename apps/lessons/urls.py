from django.urls import path

from . import views

app_name = 'lessons'

urlpatterns = [
    path('', views.LessonListView.as_view(), name='list'),
    path('yangi/', views.LessonCreateView.as_view(), name='create'),
    path('<int:pk>/qatnashdi/<str:value>/', views.LessonAttendanceView.as_view(), name='attendance'),
    path('nazariy/', views.TheoryLessonListView.as_view(), name='theory_list'),
    path('nazariy/yangi/', views.TheoryLessonCreateView.as_view(), name='theory_create'),
    path('nazariy/<int:pk>/qatnashdi/<str:value>/', views.TheoryLessonAttendanceView.as_view(), name='theory_attendance'),
]
