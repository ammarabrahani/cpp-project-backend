from datetime import datetime
from io import BytesIO
from uuid import uuid4
import uuid
from rest_framework.views import APIView
from django.contrib.auth.hashers import check_password, make_password
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .utils import create_jwt_token, s3_client, dynamodb_client, send_email
from .dynamodb_models import DynamoDBCommentManager, DynamoDBLikeManager, DynamoDBUserManager, DynamoDBPostManager
from rest_framework.permissions import AllowAny, IsAuthenticated
from botocore.exceptions import ClientError
from PIL import Image

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
                response_email = send_email({
                        "email": data.get('email'),
                        "username": data.get('username'),
                        "is_wellcome_email": True
                    })
                if response_email:
                    return Response({"message": "User created successfully"}, status=status.HTTP_201_CREATED)
                else:
                    return Response({"error": "User created but couldn't send email"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
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
    permission_classes = [IsAuthenticated]
    def post(self, request):
        username = request.user.username  # Get user details from request
        caption = request.data.get('caption', '')
        image = request.FILES.get('image')

        if not image:
            return Response({"error": "Image is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate and convert the uploaded image to JPEG
        try:
            img = Image.open(image)
            img.verify()  # Validate the image
            img = Image.open(image)  # Reopen image for further operations
            img = img.convert('RGB')  # Ensure the image is in RGB mode

            # Save the image in memory in JPEG format
            image_buffer = BytesIO()
            img.save(image_buffer, format='JPEG')
            image_buffer.seek(0)

            # Use a standardized name for the converted image
            image_name = f"{uuid4()}.jpg"

        except Exception:
            return Response({"error": "Invalid image file or unsupported format"}, status=status.HTTP_400_BAD_REQUEST)

        # Generate unique post ID and S3 key
        post_id = str(uuid4())
        s3_bucket_name = settings.AWS_S3_BUCKET_NAME
        s3_key = f"posts/{post_id}/{image_name}"
        mime_type = 'image/jpeg'

        try:
            # Upload the converted image to S3
            s3_client.upload_fileobj(
                image_buffer,
                s3_bucket_name,
                s3_key,
                ExtraArgs={"ACL": "public-read", "ContentType": mime_type}
            )

            s3_url = f"https://{s3_bucket_name}.s3.amazonaws.com/{s3_key}"
            
            # Create timestamps
            current_time = datetime.utcnow().isoformat()

            # Save post details in DynamoDB
            post_data = {
                'post_id': post_id,
                'username': username,
                'caption': caption,
                'image_url': s3_url,
                'likes_count': 0,
                'comments_count': 0,
                'created_at': current_time,
                'updated_at': current_time,
            }
            db_post.create_post(post_data)

            return Response(post_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class UpdatePostView(APIView):
    permission_classes = [IsAuthenticated]
    def put(self, request, post_id):
        # Extract user and post details
        username = request.user.username  # Logged-in user's username
        new_caption = request.data.get('caption')
        new_image = request.FILES.get('image')
        s3_bucket_name = settings.AWS_S3_BUCKET_NAME
        # Check if both fields are missing
        if not new_caption and not new_image:
            return Response(
                {"error": "At least one field (caption or image) must be provided to update"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Fetch the post from DynamoDB or database
        post = db_post.get_post_by_post_id(post_id)

        if not post:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

        # Ensure the logged-in user is the owner of the post
        if post.get('username') != username:
            return Response(
                {"error": "You are not authorized to edit this post"},
                status=status.HTTP_403_FORBIDDEN
            )

        updates = {}  # Initialize updates dictionary

        try:
            # Add caption to updates if provided
            if new_caption is not None:
                updates['caption'] = new_caption

            # Process and add image to updates if provided
            if new_image:
                try:
                    img = Image.open(new_image)
                    img.verify()  # Validate image
                    img = Image.open(new_image)
                    img = img.convert('RGB')  # Convert to RGB

                    # Save new image in memory as JPEG
                    image_buffer = BytesIO()
                    img.save(image_buffer, format='JPEG')
                    image_buffer.seek(0)

                    # Generate a new image name and S3 key
                    new_image_name = f"{uuid4()}.jpg"
                    s3_key = f"posts/{post_id}/{new_image_name}"

                    # Upload the new image to S3
                    s3_client.upload_fileobj(
                        image_buffer,
                        s3_bucket_name,
                        s3_key,
                        ExtraArgs={"ACL": "public-read", "ContentType": "image/jpeg"}
                    )

                    # Generate the new S3 URL
                    new_s3_url = f"https://{s3_bucket_name}.s3.amazonaws.com/{s3_key}"
                    updates['image_url'] = new_s3_url

                except Exception as e:
                    return Response({"error": f"Image upload failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

            # Update timestamps
            current_time = datetime.utcnow().isoformat()
            updates['updated_at'] = current_time

            # Update the post in the database
            db_post.update_post(post_id, username, updates)

            # Fetch the updated post to return
            updated_post = db_post.get_post_by_post_id(post_id)

            return Response(updated_post, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetPostsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        print(f"Authenticated User: {request.user}")
        print(f"Authentication Token: {request.auth}")
        posts = db_post.get_all_post()
        return Response(posts, status=status.HTTP_200_OK)

class GetUsersView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        print(f"Authenticated User: {request.user}")
        print(f"Authentication Token: {request.auth}")
        users = db_user.get_all_user()
        return Response(users, status=status.HTTP_200_OK)

class DeleteUserView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, username):
        # Ensure the authenticated user is the one being deleted
        if username != request.user.username:
            return Response(
                {"error": "You can only delete your own account"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Attempt to delete the user from the database
        try:
            user_delete_response = db_user.delete_user(username)
        except Exception as e:
            return Response(
                {"error": f"Failed to delete user: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Check if the user was actually deleted
        if not user_delete_response or "Attributes" not in user_delete_response:
            return Response(
                {"error": "User not found or could not be deleted"},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {"message": "User deleted successfully"},
            status=status.HTTP_200_OK
        )

class UpdateUserView(APIView):
    permission_classes = [IsAuthenticated]
    def put(self, request, username):
        # Ensure the authenticated user is the one being updated
        if username != request.user.username:
            return Response(
                {"error": "You can only update your own account"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Extract the data from the request
        data = request.data
        
        # Validate that at least one field is provided for updating
        allowed_fields = ['password', 'email']
        if not any(field in data for field in allowed_fields):
            return Response(
                {"error": "No valid fields provided for update"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Prepare the updated data
        updated_data = {}
        if 'password' in data:
            updated_data['password'] = make_password(data['password'])
        if 'email' in data:
            updated_data['email'] = data['email']
        
        # Attempt to update the user in the database
        try:
            update_response = db_user.update_user(username, updated_data)
        except Exception as e:
            return Response(
                {"error": f"Failed to update user: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Check if the update was successful
        if not update_response or "Attributes" not in update_response:
            return Response(
                {"error": "User not found or update failed"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(
            {"message": "User updated successfully", "updated_data": update_response["Attributes"]},
            status=status.HTTP_200_OK
        )


class GetPostByUsernameView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, username):
        posts = db_post.get_all_post()
        all_post = [post for post in posts if post.get('username') == username]
        if not all_post:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(all_post, status=status.HTTP_200_OK)

# Users can delete a post by its post_id.
class DeletePostView(APIView):
    permission_classes = [IsAuthenticated]
    def delete(self, request, post_id):
        username = request.user.username
        post_response = db_post.delete_post(post_id, username=username)
        like_response = db_like.delete_like_by_post_id(post_id, username)
        comment_response = db_comment.delete_comments_by_post_id(post_id, username)


        if not all(isinstance(resp, dict) and 'Attributes' in resp for resp in [post_response, comment_response]):
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response({"message": "Post deleted successfully"}, status=status.HTTP_200_OK)

class GetLikeView(APIView): 
    permission_classes = [IsAuthenticated]
    def get(self, request, post_id):
        print(f"post_id, {post_id}")
        likes = db_like.get_all_likes_by_post(post_id)
        return Response(likes, status=status.HTTP_200_OK)
    
class LikePostView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, post_id):
        current_time = datetime.utcnow().isoformat()
        username = request.user.username  # Ensure request.user has 'username' attribute
        post_username = db_post.get_post_by_post_id(post_id)
        email = db_user.get_user(post_username["username"]).get("email")
        if not username:
            return Response({"error": "username is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Add the like to the Likes table
            like_data = {
                    'post_id': post_id,
                    'username': username,
                    'liked_at': current_time,
                    'like_post': True,
                }
            response_like = db_like.add_like(like_data)

            if response_like['ResponseMetadata']['HTTPStatusCode'] == 200:
                # Increment like count in Posts table
                post_response = db_post.update_post_like_count(post_id, post_username["username"], increment=True)

                if post_response['ResponseMetadata']['HTTPStatusCode'] == 200:
                    response_email = send_email({
                        "email": email,
                        "username": username,
                        "post_id": post_id,
                        "is_wellcome_email": False
                    })
                    if response_email:
                        return Response({"message": "Post liked successfully"}, status=status.HTTP_201_CREATED)
                    else:
                        return Response({"error": "Post liked but couldn't send email"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                return Response({"error": "Failed to update like count."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return Response({"error": "User has already liked this post"}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class filterPostByLikeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        posts = db_post.filter_all_post_by_likes()
        if not posts:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(posts, status=status.HTTP_200_OK)

class UnLikePostView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, post_id):
        username = request.user.username  # Ensure request.user has 'username' attribute
        post_username = db_post.get_post_by_post_id(post_id)
        if not username:
            return Response({"error": "username is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Remove the like to the Likes table
            response_like = db_like.delete_like_by_post_id(post_id, username)

            if response_like['ResponseMetadata']['HTTPStatusCode'] == 200:
                # Decrease like count in Posts table
                post_response = db_post.update_post_like_count(post_id, post_username["username"], increment=False)

                if post_response['ResponseMetadata']['HTTPStatusCode'] == 200:
                    return Response({"message": "Post Unliked successfully"}, status=status.HTTP_201_CREATED)

                return Response({"error": "Failed to update like count."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return Response({"error": "User has already Unliked this post"}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CommentPostView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, post_id):
        current_time = datetime.utcnow().isoformat()
        username = request.user.username  # Ensure request.user has 'username' attribute
        content = request.data.get('content')
        post_username = db_post.get_post_by_post_id(post_id)
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
                post_response = db_post.update_post_comment_count(post_id, post_username["username"])

                if post_response['ResponseMetadata']['HTTPStatusCode'] == 200:
                    return Response({"message": "Comment added successfully"}, status=status.HTTP_201_CREATED)

                return Response({"error": "Failed to update comment count."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except ClientError as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetCommentsByPostIdView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, post_id):
        comments = db_comment.get_all_comments()
        all_comment = [comment for comment in comments if comment.get('post_id') == post_id]
        if not all_comment:
            return Response({"error": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(all_comment, status=status.HTTP_200_OK)
    
class GetAllCommentsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        posts = db_comment.get_all_comments()
        return Response(posts, status=status.HTTP_200_OK)