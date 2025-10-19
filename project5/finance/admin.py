from django.contrib import admin

from .models import Account, Budget, Category, Transaction, UserPreference


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "user",
        "account_type",
        "currency",
        "initial_balance",
        "current_balance",
    )
    list_filter = ("account_type", "currency")
    search_fields = ("name", "user__username")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "category_type", "parent")
    list_filter = ("category_type",)
    search_fields = ("name", "user__username")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "user",
        "account",
        "category",
        "amount",
        "currency",
        "is_recurring",
    )
    list_filter = ("currency", "is_recurring", "recurrence_interval", "account")
    search_fields = ("description", "notes", "user__username")
    autocomplete_fields = ("account", "category")
    date_hierarchy = "date"


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "amount", "period", "category")
    list_filter = ("period",)
    search_fields = ("name", "user__username")
    autocomplete_fields = ("category",)


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "currency", "timezone", "language", "theme", "updated_at")
    search_fields = ("user__username", "user__email")
