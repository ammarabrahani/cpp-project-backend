import boto3
import jwt
import datetime
from django.conf import settings
from datetime import datetime, timedelta, timezone
from rest_framework.exceptions import AuthenticationFailed
import requests
from django.http import JsonResponse

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


def send_email(request):
    # The URL of the send_email API
    external_api_url = settings.SEND_EMAIL_URL

    # Data to send to the send_email API
    if request["is_wellcome_email"]:
        
        data = {
            "username": request["username"],
            "email": request["email"],
            "is_wellcome_email": request["is_wellcome_email"]
        }
    else:

        data = {
            "username": request["username"],
            "email": request["email"],
            "post_id": request["post_id"],
            "is_wellcome_email": request["is_wellcome_email"]
        }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        # Make the POST request to the API
        response = requests.post(external_api_url, json=data, headers=headers)
        response.raise_for_status()

        # Parse the JSON response from the API
        api_data = response.json()

        # Return the API's response
        return JsonResponse({
            "success": True,
            "data": api_data
        }, status=response.status_code)

    except requests.exceptions.RequestException as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)
