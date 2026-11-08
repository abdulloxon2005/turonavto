from django.urls import path

from . import views

app_name = 'students'

urlpatterns = [
    path('', views.StudentListView.as_view(), name='list'),
    path('olib-kelganlarim/', views.MyBroughtStudentsView.as_view(), name='my_brought'),
    path('yangi/', views.StudentCreateView.as_view(), name='create'),
    path('word-import/', views.StudentWordImportView.as_view(), name='import_word'),
    path('word-namuna/', views.StudentWordSampleView.as_view(), name='import_sample'),
    path('ochirish-sorovlari/', views.DeleteRequestListView.as_view(), name='delete_requests'),
    path('ochirish-sorovlari/<int:pk>/<str:decision>/', views.DeleteRequestDecideView.as_view(), name='delete_request_decide'),
    path('<int:pk>/', views.StudentDetailView.as_view(), name='detail'),
    path('<int:pk>/tahrirlash/', views.StudentUpdateView.as_view(), name='update'),
    path('<int:pk>/arxiv/', views.StudentArchiveView.as_view(), name='archive_toggle'),
    path('<int:pk>/chetlatish/', views.StudentExpelView.as_view(), name='expel_toggle'),
    path('<int:pk>/ochirish/', views.StudentDeleteView.as_view(), name='delete'),
    path('<int:pk>/egasi/', views.StudentOwnerChangeView.as_view(), name='change_owner'),
    path('<int:pk>/instruktor/', views.StudentInstructorAssignView.as_view(), name='assign_instructor'),
    path('<int:pk>/instruktor/<int:instructor_id>/ajratish/', views.StudentInstructorUnassignView.as_view(), name='unassign_instructor'),
    path('<int:pk>/ochirish-sorovi/', views.DeleteRequestCreateView.as_view(), name='delete_request_create'),
]
