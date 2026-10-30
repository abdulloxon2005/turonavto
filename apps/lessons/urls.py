from django.urls import path

from . import views

app_name = 'lessons'

urlpatterns = [
    path('', views.LessonListView.as_view(), name='list'),
    path('yangi/', views.LessonCreateView.as_view(), name='create'),
    path('<int:pk>/qatnashdi/<str:value>/', views.LessonAttendanceView.as_view(), name='attendance'),
]
