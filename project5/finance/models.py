from decimal import Decimal
import calendar

from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models, transaction as db_transaction
from django.db.models import F, Sum
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

User = settings.AUTH_USER_MODEL


def adjust_account_balance(account, delta):
    """
    Apply delta (can be negative) to account current balance atomically.
    """
    account.__class__.objects.filter(pk=account.pk).update(
        current_balance=F("current_balance") + delta
    )
    # Keep instance in sync for subsequent operations.
    account.refresh_from_db(fields=["current_balance"])


class Account(models.Model):
    class AccountType(models.TextChoices):
        ASSET = "ASSET", "Asset"
        LIABILITY = "LIABILITY", "Liability"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="accounts")
    name = models.CharField(max_length=100)
    account_type = models.CharField(
        max_length=20, choices=AccountType.choices, default=AccountType.ASSET
    )
    currency = models.CharField(max_length=3, default="USD")
    initial_balance = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    current_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "name")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.currency})"

    def save(self, *args, **kwargs):
        if self.pk is None:
            # Align current balance with initial value on creation.
            self.current_balance = self.initial_balance
        super().save(*args, **kwargs)
        # Ensure current balance is always at least initial balance for liability?
        # No-op; additional logic handled via transactions.


class Category(models.Model):
    class CategoryType(models.TextChoices):
        INCOME = "INCOME", "Income"
        EXPENSE = "EXPENSE", "Expense"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=120)
    category_type = models.CharField(
        max_length=10,
        choices=CategoryType.choices,
        default=CategoryType.EXPENSE,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "name", "parent")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.parent:
            if self.parent.user_id != self.user_id:
                raise models.ValidationError(_("Parent category must belong to the same user."))
            if self.parent.category_type != self.category_type:
                raise models.ValidationError(
                    _("Parent and child categories must share the same type.")
                )


class Budget(models.Model):
    class Period(models.TextChoices):
        MONTHLY = "MONTHLY", _("Monthly")
        YEARLY = "YEARLY", _("Yearly")
        CUSTOM = "CUSTOM", _("Custom")

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="budgets")
    name = models.CharField(max_length=120)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="budgets",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    period = models.CharField(
        max_length=10, choices=Period.choices, default=Period.MONTHLY
    )
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.category and self.category.user_id != self.user_id:
            raise models.ValidationError(_("Category must belong to the same user."))
        if self.category and self.category.category_type != Category.CategoryType.EXPENSE:
            raise models.ValidationError(_("Budgets can only target expense categories."))
        if self.period == self.Period.CUSTOM and not self.end_date:
            raise models.ValidationError(
                {"end_date": _("Custom budgets require an end date.")}
            )
        if self.period == self.Period.CUSTOM and self.end_date and self.end_date < self.start_date:
            raise models.ValidationError({"end_date": _("End date must be after the start date.")})

    def current_period_range(self):
        today = timezone.localdate()
        if self.period == self.Period.MONTHLY:
            start = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            end = today.replace(day=last_day)
        elif self.period == self.Period.YEARLY:
            start = today.replace(month=1, day=1)
            end = today.replace(month=12, day=31)
        else:
            start = self.start_date
            end = self.end_date or self.start_date
        return start, end

    def spent_amount(self):
        start, end = self.current_period_range()
        qs = self.user.transactions.filter(date__gte=start, date__lte=end)
        if self.category:
            qs = qs.filter(category=self.category)
        qs = qs.filter(category__category_type=Category.CategoryType.EXPENSE)
        total = qs.aggregate(total=Coalesce(Sum("amount"), Decimal("0")))
        return total["total"]

    def progress_percentage(self):
        spent = self.spent_amount()
        if not self.amount:
            return 0.0
        return float(min(spent / self.amount * 100, 999))

    def remaining_amount(self):
        return self.amount - self.spent_amount()


class UserPreference(models.Model):
    class Theme(models.TextChoices):
        LIGHT = "light", _("Light")
        DARK = "dark", _("Dark")

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="preferences"
    )
    currency = models.CharField(max_length=3, default="USD")
    timezone = models.CharField(max_length=50, default="UTC")
    language = models.CharField(max_length=5, choices=settings.LANGUAGES, default="en")
    theme = models.CharField(max_length=10, choices=Theme.choices, default=Theme.LIGHT)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("User preference")
        verbose_name_plural = _("User preferences")

    def __str__(self):
        return f"Preferences for {self.user}"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_preferences(sender, instance, created, **kwargs):
    if created:
        UserPreference.objects.create(user=instance)


class Transaction(models.Model):
    class RecurrenceInterval(models.TextChoices):
        NONE = "NONE", "Does not repeat"
        DAILY = "DAILY", "Daily"
        WEEKLY = "WEEKLY", "Weekly"
        MONTHLY = "MONTHLY", "Monthly"
        YEARLY = "YEARLY", "Yearly"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="transactions")
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="transactions"
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, related_name="transactions", null=True
    )
    date = models.DateField()
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3, default="USD")
    description = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated tags")
    attachment = models.FileField(
        upload_to="receipts/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "pdf"])],
    )
    is_recurring = models.BooleanField(default=False)
    recurrence_interval = models.CharField(
        max_length=10,
        choices=RecurrenceInterval.choices,
        default=RecurrenceInterval.NONE,
    )
    recurrence_end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.date} - {self.amount} {self.currency}"

    @property
    def is_expense(self):
        if self.category:
            return self.category.category_type == Category.CategoryType.EXPENSE
        return False

    def signed_amount(self):
        return -self.amount if self.is_expense else self.amount

    def clean(self):
        super().clean()
        if self.account.user_id != self.user_id:
            raise models.ValidationError(_("Account must belong to the same user."))
        if self.category and self.category.user_id != self.user_id:
            raise models.ValidationError(_("Category must belong to the same user."))
        if self.is_recurring and self.recurrence_interval == self.RecurrenceInterval.NONE:
            raise models.ValidationError(
                {"recurrence_interval": _("Select an interval for recurring transactions.") }
            )
        if (
            self.recurrence_interval != self.RecurrenceInterval.NONE
            and self.recurrence_end_date
            and self.recurrence_end_date < self.date
        ):
            raise models.ValidationError(
                {"recurrence_end_date": _("End date cannot be before the transaction date.") }
            )

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_transaction = None
        self.currency = (self.currency or "USD").upper()
        if not is_new:
            old_transaction = Transaction.objects.select_related("account", "category").get(
                pk=self.pk
            )

        self.full_clean()

        with db_transaction.atomic():
            super().save(*args, **kwargs)

            if is_new:
                adjust_account_balance(self.account, self.signed_amount())
            else:
                # Reverse previous impact then apply new values.
                if old_transaction.account_id == self.account_id:
                    delta = self.signed_amount() - old_transaction.signed_amount()
                    if delta:
                        adjust_account_balance(self.account, delta)
                else:
                    adjust_account_balance(old_transaction.account, -old_transaction.signed_amount())
                    adjust_account_balance(self.account, self.signed_amount())

    def delete(self, *args, **kwargs):
        with db_transaction.atomic():
            adjust_account_balance(self.account, -self.signed_amount())
            super().delete(*args, **kwargs)
