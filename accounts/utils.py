import random
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django_rq import job
from .models import EmailOTP, PendingEmailOTP

@job('emails')
def send_async_email(subject, template_name, context, recipient_list):
    """
    Renders an HTML template and sends it via Brevo.
    Includes a plain-text fallback for maximum deliverability.
    """
    html_message = render_to_string(f'emails/{template_name}', context)
    plain_message = strip_tags(html_message) 
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            html_message=html_message,  
            fail_silently=False,
        )
    except Exception as e:
        print(f"Brevo SMTP Error: {e}")


def send_otp_email(user):
    """For general authenticated actions like resending an OTP."""
    code = f"{random.randint(0, 999999):06d}"
    EmailOTP.objects.create(user=user, code=code)
    
    send_async_email.delay(
        subject='Your Polaris verification code',
        template_name='otp.html',
        context={
            'title': 'Account Verification',
            'message': 'Use the code below to verify your action. It expires in 10 minutes.',
            'code': code
        },
        recipient_list=[user.email]
    )

def send_registration_otp(email):
    """For new account sign-ups."""
    code = f"{random.randint(0, 999999):06d}"
    PendingEmailOTP.objects.create(email=email, code=code)
    
    send_async_email.delay(
        subject='Verify your Polaris account',
        template_name='otp.html',
        context={
            'title': 'Welcome to Polaris',
            'message': 'Use the code below to verify your email address. It expires in 10 minutes.',
            'code': code
        },
        recipient_list=[email]
    )

def send_password_reset_otp(email):
    """For forgotten passwords."""
    code = f"{random.randint(0, 999999):06d}"
    PendingEmailOTP.objects.create(email=email, code=code)
    
    send_async_email.delay(
        subject='Polaris Password Reset Request',
        template_name='otp.html',
        context={
            'title': 'Password Reset Request',
            'message': 'We received a request to reset your password. If you did not request this, you can safely ignore this email.',
            'code': code
        },
        recipient_list=[email]
    )

def send_email_change_otp(new_email):
    """For users updating their email address from their profile."""
    code = f"{random.randint(0, 999999):06d}"
    PendingEmailOTP.objects.create(email=new_email, code=code)
    
    send_async_email.delay(
        subject='Verify your new email address',
        template_name='otp.html',
        context={
            'title': 'Email Update Request',
            'message': 'You requested to change your Polaris account email to this address. Your verification code is below.',
            'code': code
        },
        recipient_list=[new_email]
    )


def send_welcome_email(email, first_name):
    send_async_email.delay(
        subject='Welcome to Polaris!',
        template_name='welcome.html',
        context={'first_name': first_name},
        recipient_list=[email]
    )

def send_password_changed_alert(email):
    send_async_email.delay(
        subject='Security Alert: Your Polaris password was changed',
        template_name='alert.html',
        context={
            'title': 'Password Updated',
            'message': 'Your Polaris password was recently changed. If you did not authorize this, please contact support immediately.'
        },
        recipient_list=[email]
    )

def send_email_changed_alerts(old_email, new_email):
    send_async_email.delay(
        subject='Security Alert: Email address removed',
        template_name='alert.html',
        context={
            'title': 'Email Address Removed',
            'message': f'Your Polaris account email has been changed to {new_email}. If you did not authorize this, contact support immediately.'
        },
        recipient_list=[old_email]
    )
    
    send_async_email.delay(
        subject='Email update successful',
        template_name='alert.html',
        context={
            'title': 'Email Successfully Updated',
            'message': 'Your Polaris account email has been successfully updated to this address. You will now use this email to log in.'
        },
        recipient_list=[new_email]
    )