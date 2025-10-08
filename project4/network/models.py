from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    def followers_count(self):
        return self.followers.count()

    def following_count(self):
        return self.following.count()


class Post(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    content = models.TextField(max_length=1024)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author.username}: {self.content[:30]}"

    @property
    def like_count(self):
        return self.likes.count()


class Follow(models.Model):
    follower = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="following",
    )
    following = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("follower", "following")

    def __str__(self):
        return f"{self.follower} follows {self.following}"


class Like(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="liked_posts",
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "post")

    def __str__(self):
        return f"{self.user} likes Post #{self.post_id}"
