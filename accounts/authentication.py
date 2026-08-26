import datetime
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

class CustomJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        issued_at = validated_token.get('iat')
        if issued_at is not None and user.password_changed_at:
            issued_at_dt = datetime.datetime.fromtimestamp(issued_at, tz=datetime.timezone.utc)
            if issued_at_dt < user.password_changed_at:
                raise AuthenticationFailed('Session invalidated by a password change. Please log in again.')
        return user