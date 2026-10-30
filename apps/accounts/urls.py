from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('parolni-almashtirish/majburiy/', views.ForcedPasswordChangeView.as_view(), name='force_password_change'),
    path('parolni-almashtirish/', views.ChangePasswordView.as_view(), name='change_password'),

    path('hodimlar/', views.StaffListView.as_view(), name='staff_list'),
    path('hodimlar/yangi/', views.StaffCreateView.as_view(), name='staff_create'),
    path('hodimlar/<int:pk>/', views.StaffDetailView.as_view(), name='staff_detail'),
    path('hodimlar/<int:pk>/tahrirlash/', views.StaffUpdateView.as_view(), name='staff_update'),
    path('hodimlar/<int:pk>/holat/', views.StaffToggleActiveView.as_view(), name='staff_toggle_active'),
    path('hodimlar/<int:pk>/parol-tiklash/', views.StaffResetPasswordView.as_view(), name='staff_reset_password'),
]
