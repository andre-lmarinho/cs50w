from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("following/", views.following, name="following"),
    path("profile/<str:username>/", views.profile, name="profile"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register"),
    path("api/posts", views.api_posts, name="api_posts"),
    path("api/posts/<int:post_id>", views.api_post_detail, name="api_post_detail"),
    path("api/profile/<str:username>", views.api_profile, name="api_profile"),
    path(
        "api/profile/<str:username>/follow",
        views.api_toggle_follow,
        name="api_toggle_follow",
    ),
]
