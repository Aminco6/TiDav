from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('activate/', views.activation_view, name='activation'),
    path('activate/<uuid:token>/', views.activation_view, name='activation_token'),
    path('activate/success/', views.activation_success_view, name='activation_success'),
    path('activate/resend/', views.resend_activation_view, name='resend_activation'),
    path('check-email/', views.check_email_view, name='check_email'),
    path('check-password/', views.check_password_strength_view, name='check_password'),
    
    
    
    
    
    path('login/google/', views.google_login_view, name='google_login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    path('check-email/', views.check_email_view, name='check_email'),
    path('check-password/', views.check_password_strength_view, name='check_password'),

]