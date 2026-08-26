from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import *

urlpatterns = [
    path('send-registration-otp/', SendRegistrationOTPView.as_view(), name='send_registration_otp'),
    path('verify-registration-otp/', VerifyRegistrationOTPView.as_view(), name='verify_registration_otp'),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('login/refresh/', TokenRefreshView.as_view(), name='login_refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('change-email/request/', RequestEmailChangeView.as_view(), name='change_email_request'),
    path('change-email/confirm/', ConfirmEmailChangeView.as_view(), name='change_email_confirm'),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]