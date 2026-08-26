import random
from django.core.mail import send_mail
from django.conf import settings
from .models import EmailOTP, PendingEmailOTP

def send_otp_email(user):
    code = f"{random.randint(0, 999999):06d}"
    EmailOTP.objects.create(user=user, code=code)
    send_mail(
        subject='Your Polaris verification code',
        message=f'Your verification code is: {code}\nThis code expires in 10 minutes.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )

def send_registration_otp(email):
    code = f"{random.randint(0, 999999):06d}"
    PendingEmailOTP.objects.create(email=email, code=code)
    send_mail(
        subject='Your Polaris verification code',
        message=f'Your verification code is: {code}\nThis code expires in 10 minutes.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
    )