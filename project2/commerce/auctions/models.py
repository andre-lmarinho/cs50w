from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    watchlist = models.ManyToManyField(
        "Listing",
        blank=True,
        related_name="watched_by",
    )


class Category(models.Model):
    name = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Listing(models.Model):
    title = models.CharField(max_length=128)
    description = models.TextField()
    starting_bid = models.DecimalField(max_digits=12, decimal_places=2)
    image_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="listings",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="listings",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["-is_active", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def current_price(self):
        top_bid = self.bids.order_by("-amount").first()
        return top_bid.amount if top_bid else self.starting_bid

    @property
    def winning_bidder(self):
        top_bid = self.bids.order_by("-amount").first()
        return top_bid.bidder if top_bid else None


class Bid(models.Model):
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="bids",
    )
    bidder = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="bids",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    placed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-amount", "placed_at"]

    def __str__(self):
        return f"{self.bidder} bid {self.amount} on {self.listing}"


class Comment(models.Model):
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author}: {self.body[:24]}..."
