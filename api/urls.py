"""
URL configuration for api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from .views import CreatePostView, DeletePostView, GetAllCommentsView, GetCommentsByPostIdView, GetPostByUsernameView, GetPostsView, RegisterView, LoginView, LikePostView, CommentPostView, UnLikePostView, UpdatePostAPI, filterPostByLikeView

urlpatterns = [
    path('register', RegisterView.as_view(), name='register'),
    path('login', LoginView.as_view(), name='login'),
    path('posts', GetPostsView.as_view(), name='get_posts'),
    path('posts/create', CreatePostView.as_view(), name='create_post'),
    path('posts/<str:username>', GetPostByUsernameView.as_view(), name='get_post_by_username'),
    path('posts/<str:post_id>/delete', DeletePostView.as_view(), name='delete_post'),
    path('posts/<str:post_id>/update', UpdatePostAPI.as_view(), name='update_post'),
    path('posts/<str:post_id>/like', LikePostView.as_view(), name='add_like'),
    path('posts/<str:post_id>/unlike', UnLikePostView.as_view(), name='un_like'),
    path('posts/<str:post_id>/comment/create', CommentPostView.as_view(), name='add_comment'),
    path('posts/<str:post_id>/comments', GetCommentsByPostIdView.as_view(), name='add_comment'),
    path('posts/comments/all', GetAllCommentsView.as_view(), name='all_comments'),
    path('trending/posts', filterPostByLikeView.as_view(), name='sorted_post'),
]