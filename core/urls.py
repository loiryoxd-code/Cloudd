from django.urls import path
from . import views

urlpatterns = [
    path('', views.LandingView.as_name() if hasattr(views, 'LandingView') else views.landing, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('owasp/', views.owasp_dashboard, name='owasp_dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('admin-users/', views.admin_users_view, name='admin_users'),
    path('db-diagnostic/', views.db_diagnostic_view, name='db_diagnostic'),
]
