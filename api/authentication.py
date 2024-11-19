# your_app/authentication.py

import jwt
from rest_framework import authentication, exceptions
from django.conf import settings
from .utils import dynamodb_client, decode_jwt_token
from .dynamodb_models import DynamoDBUserManager

dynamodb_client = dynamodb_client()
db_user = DynamoDBUserManager(settings.DYNAMODB_USER_TABLE_NAME, dynamodb_client)

class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        """
        Extract the JWT token from the Authorization header and decode it.
        """
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = decode_jwt_token(token)
                user = db_user.get_user(payload['username'])
            except (jwt.DecodeError, jwt.ExpiredSignatureError):
                raise exceptions.AuthenticationFailed('Invalid or expired token')
            except KeyError:
                raise exceptions.AuthenticationFailed('Token missing username')

            return (user, token)
        return None
