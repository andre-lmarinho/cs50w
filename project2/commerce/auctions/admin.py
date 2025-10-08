from django.contrib import admin

from .models import Bid, Category, Comment, Listing, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "is_staff")
    search_fields = ("username", "email")
    filter_horizontal = ("groups", "user_permissions", "watchlist")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "current_price", "is_active", "created_at")
    list_filter = ("is_active", "category")
    search_fields = ("title", "description")
    autocomplete_fields = ("owner", "category")


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ("listing", "bidder", "amount", "placed_at")
    autocomplete_fields = ("listing", "bidder")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("listing", "author", "created_at")
    search_fields = ("body",)
