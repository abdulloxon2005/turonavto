from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('jurnal/', views.AuditLogListView.as_view(), name='audit_log'),
    path('zaxira/', views.BackupListView.as_view(), name='backup_list'),
    path('zaxira/<str:filename>/', views.BackupDownloadView.as_view(), name='backup_download'),

    path('arxiv/', views.ArchiveView.as_view(), name='archive'),
    path('arxiv/oquvchi/<int:pk>/tiklash/', views.ArchiveRestoreStudentView.as_view(), name='archive_restore_student'),
    path('arxiv/oquvchi/<int:pk>/ochirish/', views.ArchiveDeleteStudentView.as_view(), name='archive_delete_student'),
    path('arxiv/guruh/<int:pk>/tiklash/', views.ArchiveRestoreGroupView.as_view(), name='archive_restore_group'),
    path('arxiv/guruh/<int:pk>/ochirish/', views.ArchiveDeleteGroupView.as_view(), name='archive_delete_group'),
    path('arxiv/xodim/<int:pk>/tiklash/', views.ArchiveRestoreStaffView.as_view(), name='archive_restore_staff'),
    path('arxiv/xodim/<int:pk>/ochirish/', views.ArchiveDeleteStaffView.as_view(), name='archive_delete_staff'),
]
