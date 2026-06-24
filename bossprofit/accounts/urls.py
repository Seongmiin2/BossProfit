from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    path("register/", views.register, name="auth-register"),
    path("login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("logout/", views.logout, name="auth-logout"),
    path("me/", views.current_user, name="auth-me"),
    path("profile/", views.update_profile, name="auth-profile-update"),
    path("password/", views.change_password, name="auth-password-change"),
    path("store/", views.create_store, name="auth-store-create"),
    path("store/update/", views.update_store, name="auth-store-update"),
    path("onboarding/", views.onboarding_status, name="auth-onboarding"),
]
