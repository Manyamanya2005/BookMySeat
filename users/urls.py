from django.urls import path
from django.contrib.auth import views as auth_views

from . import views


urlpatterns = [

    # Home
    path('', views.home, name='home'),

    # Register
    path('register/', views.register, name='register'),

    # Login
   path('login/', views.login_view, name='login'),

    # Logout
    path('logout/', views.logout_view, name='logout'),

    # Profile
    path('profile/', views.profile, name='profile'),
  path(
        "reset-password/",
        views.reset_password,
        name="reset_password"
    ),


    # Change password
    path(
        'reset-password/',
        views.reset_password,
        name='reset_password'
    ),

    # Password reset - request email
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='users/password_reset.html',
            email_template_name='users/password_reset_email.html',
            subject_template_name='users/password_reset_subject.txt',
            success_url='/password-reset/done/'
        ),
        name='password_reset'
    ),

    # Password reset email sent
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='users/password_reset_done.html'
        ),
        name='password_reset_done'
    ),

    # New password form
    path(
        'password-reset-confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='users/password_reset_confirm.html',
            success_url='/password-reset-complete/'
        ),
        name='password_reset_confirm'
    ),

    # Password successfully changed
    path(
        'password-reset-complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='users/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),
]