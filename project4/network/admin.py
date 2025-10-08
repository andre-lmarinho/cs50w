from django.contrib import admin

from .models import Follow, Like, Post, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "is_staff")
    search_fields = ("username", "email")


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "short_content", "created_at", "like_count")
    list_filter = ("created_at",)
    search_fields = ("content", "author__username")
    autocomplete_fields = ("author",)

    def short_content(self, obj):
        return obj.content[:60]


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("follower", "following", "created_at")
    search_fields = ("follower__username", "following__username")
    autocomplete_fields = ("follower", "following")


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "created_at")
    search_fields = ("user__username", "post__content")
    autocomplete_fields = ("user", "post")
