from django.urls import path

from . import views

app_name = 'exams'

urlpatterns = [
    path('<int:student_pk>/qoshish/', views.ExamAttemptCreateView.as_view(), name='create'),
    path('<int:pk>/ochirish/', views.ExamAttemptDeleteView.as_view(), name='delete'),
]
