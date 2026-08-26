from .models import *
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.conf import settings
import requests

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    recaptcha_token = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number', 'password', 'confirm_password', 'recaptcha_token']

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': "Passwords don't match."})

        result = requests.post('https://www.google.com/recaptcha/api/siteverify', data={
            'secret': settings.RECAPTCHA_SECRET_KEY,
            'response': data['recaptcha_token'],
        }).json()
        if not result.get('success'):
            raise serializers.ValidationError({'recaptcha_token': "Captcha verification failed."})

        verified_otp = PendingEmailOTP.objects.filter(email=data['email'], is_verified=True).order_by('-created_at').first()
        if not verified_otp or verified_otp.is_expired():
            raise serializers.ValidationError({'email': "Please verify your email before creating an account."})

        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        validated_data.pop('recaptcha_token')
        user = User.objects.create_user(**validated_data)
        user.is_email_verified = True
        user.save()
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.is_email_verified:
            raise serializers.ValidationError("Please verify your email before logging in.")
        return data


class UserSerializer(serializers.ModelSerializer):
    onboarding_completed = serializers.BooleanField(source='profile.onboarding_completed', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 'profile_picture', 'date_joined', 'onboarding_completed']
        read_only_fields = ['id', 'email', 'date_joined', 'onboarding_completed']