import boto3
import jwt
import datetime
from django.conf import settings
from datetime import datetime, timedelta, timezone
from rest_framework.exceptions import AuthenticationFailed

# Secret key for encoding and decoding JWT tokens
SECRET_KEY = settings.SECRET_KEY

def create_jwt_token(username):
    """Generate JWT token with custom payload"""
    payload = {
        "username": username,
        'exp': datetime.now(timezone.utc) + timedelta(hours=5),
        'iat': datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token

def decode_jwt_token(token):
    """Decode JWT token and validate payload"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationFailed("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthenticationFailed("Invalid token")

def s3_client():
    client = boto3.client(
                's3', 
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                aws_session_token = settings.AWS_SESSION_TOKEN
            )
    return client

def dynamodb_client():
    client = boto3.resource(
                'dynamodb',
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                aws_session_token = settings.AWS_SESSION_TOKEN
            )
    return client