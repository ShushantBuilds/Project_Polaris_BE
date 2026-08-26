# accounts/views.py
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.contrib.auth import get_user_model
from .models import *
from .utils import *
from .serializers import *
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('otp_code')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Invalid email or code.'}, status=400)

        otp = EmailOTP.objects.filter(user=user, code=code, is_used=False).order_by('-created_at').first()
        if not otp:
            return Response({'error': 'Invalid or already-used code.'}, status=400)
        if otp.is_expired():
            return Response({'error': 'Code expired. Please request a new one.'}, status=400)

        otp.is_used = True
        otp.save()
        user.is_email_verified = True
        user.save()
        return Response({'message': 'Email verified successfully. You can now log in.'})


class ResendOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'No account with that email.'}, status=400)
        if user.is_email_verified:
            return Response({'error': 'Email already verified.'}, status=400)
        send_otp_email(user)
        return Response({'message': 'A new code has been sent.'})

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class SendRegistrationOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        if not email:
            return Response({'error': 'Email is required.'}, status=400)
        if User.objects.filter(email=email).exists():
            return Response({'error': 'An account with this email already exists.'}, status=400)
        send_registration_otp(email)
        return Response({'message': 'Verification code sent.'})


class VerifyRegistrationOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        code = request.data.get('otp_code')
        otp = PendingEmailOTP.objects.filter(email=email, code=code, is_verified=False).order_by('-created_at').first()
        if not otp:
            return Response({'error': 'Invalid code.'}, status=400)
        if otp.is_expired():
            return Response({'error': 'Code expired. Please request a new one.'}, status=400)
        otp.is_verified = True
        otp.save()
        return Response({'message': 'Email verified.'})


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class RequestEmailChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        new_email = request.data.get('new_email', '').strip().lower()
        if not new_email:
            return Response({'error': 'New email is required.'}, status=400)
        if new_email == request.user.email:
            return Response({'error': 'That is already your current email.'}, status=400)
        if User.objects.filter(email=new_email).exists():
            return Response({'error': 'That email is already in use.'}, status=400)
        send_registration_otp(new_email)
        return Response({'message': 'Verification code sent to the new email.'})


class ConfirmEmailChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        new_email = request.data.get('new_email', '').strip().lower()
        code = request.data.get('otp_code')
        otp = PendingEmailOTP.objects.filter(email=new_email, code=code, is_verified=False).order_by('-created_at').first()
        if not otp:
            return Response({'error': 'Invalid code.'}, status=400)
        if otp.is_expired():
            return Response({'error': 'Code expired. Please request a new one.'}, status=400)
        otp.is_verified = True
        otp.save()

        if User.objects.filter(email=new_email).exclude(id=request.user.id).exists():
            return Response({'error': 'That email is already in use.'}, status=400)

        request.user.email = new_email
        request.user.save()
        return Response(UserSerializer(request.user, context={'request': request}).data)


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        if email:
            try:
                User.objects.get(email=email)
                send_registration_otp(email)  
            except User.DoesNotExist:
                print(f"DEBUG: Someone tried to reset the password for {email}, but they don't exist in the DB!")
                pass  
                
        return Response({'message': 'If an account exists with that email, a reset code has been sent.'})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        code = request.data.get('otp_code')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_new_password')

        if not new_password or len(new_password) < 8:
            return Response({'error': 'Password must be at least 8 characters.'}, status=400)
        if new_password != confirm_password:
            return Response({'error': "Passwords don't match."}, status=400)

        otp = PendingEmailOTP.objects.filter(email=email, code=code, is_verified=False).order_by('-created_at').first()
        if not otp:
            return Response({'error': 'Invalid code.'}, status=400)
        if otp.is_expired():
            return Response({'error': 'Code expired. Please request a new one.'}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Invalid request.'}, status=400)

        otp.is_verified = True
        otp.save()
        user.set_password(new_password)
        user.password_changed_at = timezone.now()
        user.save()

        for token in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=token)

        send_mail(
            subject='Your Polaris password was changed',
            message="Your password was just reset. If this wasn't you, contact support immediately.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
        return Response({'message': 'Password reset successfully. You can now log in.'})