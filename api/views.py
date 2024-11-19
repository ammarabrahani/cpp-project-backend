from datetime import datetime
from uuid import uuid4
import uuid
from rest_framework.views import APIView
from django.contrib.auth.hashers import check_password, make_password
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .utils import create_jwt_token, s3_client, dynamodb_client
from .dynamodb_models import DynamoDBCommentManager, DynamoDBLikeManager, DynamoDBUserManager, DynamoDBPostManager
from rest_framework.permissions import AllowAny
from botocore.exceptions import ClientError

# Initialize Client for S3, DynamoDB
s3_client = s3_client()
dynamodb_client = dynamodb_client()

# Initialize Database Classes
db_user = DynamoDBUserManager(settings.DYNAMODB_USER_TABLE_NAME, dynamodb_client)
db_post = DynamoDBPostManager(settings.DYNAMODB_POST_TABLE_NAME, dynamodb_client)
db_like = DynamoDBLikeManager(settings.DYNAMODB_LIKE_TABLE_NAME, dynamodb_client)
db_comment = DynamoDBCommentManager(settings.DYNAMODB_COMMENT_TABLE_NAME, dynamodb_client)

class RegisterView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        data = request.data

        user = db_user.get_user(data['username'])

        if not user:
            if data.get('username') and data.get('password') and data.get('email'):
                db_user.create_user(data['username'], make_password(data['password']), data['email'])
                return Response({"message": "User created successfully"}, status=status.HTTP_201_CREATED)
            return Response("Invalid Form details", status=status.HTTP_400_BAD_REQUEST)
        
        return Response("User already exist", status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        # Extract username and password from request data
        username = request.data.get('username')
        password = request.data.get('password')

        # Fetch user data from DynamoDB
        user_data = db_user.get_user(username)
        print(f"USER DATA: ", user_data)
        if not user_data:
            return Response({"error": "Invalid username or password"}, status=status.HTTP_401_UNAUTHORIZED)
        check_password
        if user_data and check_password(password, user_data['password']):  # Implement proper password checking
            token = create_jwt_token(user_data['username'])
            return Response({'token': token}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
class CreatePostView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        # Get user details from request
        username = request.user['username']  # The user object returned by the authentication class
        caption = request.data.get('caption', '')
        image = request.FILES.get('image')

        if not image:
            return Response({"error": "Image is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Generate unique post ID and upload image to S3
        post_id = str(uuid4())
        s3_bucket_name = 'social-media-store'
        s3_key = f"posts/{post_id}/{image.name}"
        s3_client.upload_fileobj(image, s3_bucket_name, s3_key)

        # Get image URL
        image_url = f"https://{s3_bucket_name}.s3.amazonaws.com/{s3_key}"

        # Create timestamps
        current_time = datetime.utcnow().isoformat()

        # Save post details in DynamoDB
        post_data = {
            'post_id': post_id,
            'username': username,
            'caption': caption,
            'image_url': image_url,
            'likes_count': 0,
            'comments_count': 0,
            'created_at': current_time,
            'updated_at': current_time,
        }
        db_post.create_post(post_data)

        return Response(post_data, status=status.HTTP_201_CREATED)

class GetPostsView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        posts = db_post.get_all_post()
        return Response(posts, status=status.HTTP_200_OK)

class GetPostByUsernameView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, username):
        posts = db_post.get_all_post()
        all_post = [post for post in posts if post.get('username') == username]
        if not all_post:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(all_post, status=status.HTTP_200_OK)

# Users can delete a post by its post_id.
class DeletePostView(APIView):
    permission_classes = [AllowAny]
    def delete(self, request, post_id):
        username = request.user.get('username')
        post_response = db_post.delete_post(post_id, username=username)
        like_response = db_like.delete_like_by_post_id(post_id, username)
        comment_response = db_comment.delete_comments_by_post_id(post_id, username)


        if not all(isinstance(resp, dict) and 'Attributes' in resp for resp in [post_response, comment_response]):
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response({"message": "Post deleted successfully"}, status=status.HTTP_200_OK)

class LikePostView(APIView):
    permission_classes = [AllowAny]
    def post(self, request, post_id):
        current_time = datetime.utcnow().isoformat()
        username = request.user.get('username')  # Ensure request.user has 'username' attribute

        if not username:
            return Response({"error": "username is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Add the like to the Likes table
            like_data = {
                    'post_id': post_id,
                    'username': username,
                    'liked_at': current_time,
                }
            response_like = db_like.add_like(like_data)

            if response_like['ResponseMetadata']['HTTPStatusCode'] == 200:
                # Increment like count in Posts table
                post_response = db_post.update_post_like_count(post_id, username, increment=True)

                if post_response['ResponseMetadata']['HTTPStatusCode'] == 200:
                    return Response({"message": "Post liked successfully"}, status=status.HTTP_201_CREATED)

                return Response({"error": "Failed to update like count."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return Response({"error": "User has already liked this post"}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class filterPostByLikeView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        posts = db_post.filter_all_post_by_likes()
        if not posts:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(posts, status=status.HTTP_200_OK)

class UnLikePostView(APIView):
    permission_classes = [AllowAny]
    def post(self, request, post_id):
        username = request.user.get('username')  # Ensure request.user has 'username' attribute

        if not username:
            return Response({"error": "username is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Remove the like to the Likes table
            response_like = db_like.delete_like_by_post_id(post_id, username)

            if response_like['ResponseMetadata']['HTTPStatusCode'] == 200:
                # Decrease like count in Posts table
                post_response = db_post.update_post_like_count(post_id, username, increment=False)

                if post_response['ResponseMetadata']['HTTPStatusCode'] == 200:
                    return Response({"message": "Post Unliked successfully"}, status=status.HTTP_201_CREATED)

                return Response({"error": "Failed to update like count."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return Response({"error": "User has already Unliked this post"}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CommentPostView(APIView):
    permission_classes = [AllowAny]
    def post(self, request, post_id):
        current_time = datetime.utcnow().isoformat()
        username = request.user.get('username')  # Ensure request.user has 'username' attribute
        content = request.data.get('content')
        
        if not username or not content:
            return Response({"error": "Username and content are required."}, status=status.HTTP_400_BAD_REQUEST)


        try:
            # Add the comment to the Comments table
            comment_data =  {
                    'post_id': post_id,
                    'username': username,
                    'content': content,
                    'created_at': current_time,
                    'comment_id': str(uuid.uuid4())
                }
            response_comment = db_comment.add_comment(comment_data)

            if response_comment['ResponseMetadata']['HTTPStatusCode'] == 200:
                # Increment comment count in Posts table
                post_response = db_post.update_post_comment_count(post_id, username)

                if post_response['ResponseMetadata']['HTTPStatusCode'] == 200:
                    return Response({"message": "Comment added successfully"}, status=status.HTTP_201_CREATED)

                return Response({"error": "Failed to update comment count."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except ClientError as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetCommentsByPostIdView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, post_id):
        comments = db_comment.get_all_comments_by_postId()
        all_comment = [comment for comment in comments if comment.get('post_id') == post_id]
        if not all_comment:
            return Response({"error": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(all_comment, status=status.HTTP_200_OK)