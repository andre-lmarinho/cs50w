from django import forms
import pytz
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Account, Budget, Category, Transaction, UserPreference


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
            if isinstance(field.widget, forms.PasswordInput):
                field.widget.attrs["autocomplete"] = "new-password"

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class BaseUserModelForm(forms.ModelForm):
    """
    Base form that injects bootstrap classes and stores request user for queryset filtering.
    """

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-control"
            if isinstance(field.widget, forms.CheckboxInput):
                css_class = "form-check-input"
            field.widget.attrs.setdefault("class", css_class)


class AccountForm(BaseUserModelForm):
    class Meta:
        model = Account
        fields = ("name", "account_type", "currency", "initial_balance", "description")

    def save(self, commit=True):
        account = super().save(commit=False)
        if self.user:
            account.user = self.user
        if account.pk:
            original = Account.objects.get(pk=account.pk)
            delta = account.initial_balance - original.initial_balance
            account.current_balance = original.current_balance + delta
        else:
            account.current_balance = account.initial_balance
        if commit:
            account.save()
        return account


class CategoryForm(BaseUserModelForm):
    class Meta:
        model = Category
        fields = ("name", "category_type", "parent")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        if self.user:
            self.fields["parent"].queryset = Category.objects.filter(user=self.user)
        self.fields["parent"].required = False
        self.fields["parent"].empty_label = "No parent"

    def save(self, commit=True):
        category = super().save(commit=False)
        if self.user:
            category.user = self.user
        if commit:
            category.save()
        return category


class TransactionForm(BaseUserModelForm):
    class Meta:
        model = Transaction
        fields = (
            "account",
            "category",
            "date",
            "amount",
            "currency",
            "description",
            "notes",
            "tags",
            "attachment",
            "is_recurring",
            "recurrence_interval",
            "recurrence_end_date",
        )
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "recurrence_end_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        if self.user:
            self.fields["account"].queryset = Account.objects.filter(user=self.user)
            self.fields["category"].queryset = Category.objects.filter(user=self.user)
        self.fields["category"].required = False
        self.fields["tags"].help_text = "Separate tags with commas (e.g. groceries, family)."

    def clean_recurrence_end_date(self):
        end_date = self.cleaned_data.get("recurrence_end_date")
        interval = self.cleaned_data.get("recurrence_interval")
        date_value = self.cleaned_data.get("date")
        if interval and interval != Transaction.RecurrenceInterval.NONE and not end_date:
            return end_date
        if end_date and date_value and end_date < date_value:
            raise forms.ValidationError("End date cannot be earlier than the transaction date.")
        return end_date

    def clean(self):
        cleaned_data = super().clean()
        is_recurring = cleaned_data.get("is_recurring")
        interval = cleaned_data.get("recurrence_interval")
        if not is_recurring:
            cleaned_data["recurrence_interval"] = Transaction.RecurrenceInterval.NONE
            cleaned_data["recurrence_end_date"] = None
            self.instance.recurrence_interval = Transaction.RecurrenceInterval.NONE
            self.instance.recurrence_end_date = None
        elif interval == Transaction.RecurrenceInterval.NONE:
            self.add_error("recurrence_interval", "Select how often the transaction repeats.")
        return cleaned_data

    def save(self, commit=True):
        transaction = super().save(commit=False)
        if self.user:
            transaction.user = self.user
        if commit:
            transaction.save()
        return transaction


class TransactionImportForm(forms.Form):
    file = forms.FileField(label=_("CSV file"))
    delimiter = forms.CharField(label=_("Delimiter"), max_length=1, initial=",")
    date_format = forms.CharField(label=_("Date format"), initial="%Y-%m-%d")
    date_column = forms.CharField(label=_("Date column"), initial="date")
    amount_column = forms.CharField(label=_("Amount column"), initial="amount")
    description_column = forms.CharField(
        label=_("Description column"), initial="description", required=False
    )
    account_column = forms.CharField(
        label=_("Account column"), initial="account", required=False
    )
    category_column = forms.CharField(
        label=_("Category column"), initial="category", required=False
    )
    currency_column = forms.CharField(
        label=_("Currency column"), initial="currency", required=False
    )
    tags_column = forms.CharField(
        label=_("Tags column"), initial="tags", required=False
    )
    notes_column = forms.CharField(
        label=_("Notes column"), initial="notes", required=False
    )
    default_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        required=False,
        label=_("Default account"),
        help_text=_("Used when the account column is empty."),
    )
    default_category = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        required=False,
        label=_("Default category"),
        help_text=_("Used when the category column is empty."),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user:
            self.fields["default_account"].queryset = Account.objects.filter(user=user)
            self.fields["default_category"].queryset = Category.objects.filter(
                user=user, category_type=Category.CategoryType.EXPENSE
            )
        for name, field in self.fields.items():
            if name == "file":
                continue
            css_class = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs.setdefault("class", css_class)
        self.fields["file"].widget.attrs.setdefault("class", "form-control")

    def clean_delimiter(self):
        delim = self.cleaned_data["delimiter"]
        if len(delim) != 1:
            raise forms.ValidationError(_("Delimiter must be a single character."))
        return delim


class TransactionFilterForm(forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.none(), required=False)
    category = forms.ModelChoiceField(queryset=Category.objects.none(), required=False)
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    tags = forms.CharField(required=False)
    search = forms.CharField(required=False, label="Description")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs.setdefault("class", css_class)
        if user:
            self.fields["account"].queryset = Account.objects.filter(user=user)
            self.fields["category"].queryset = Category.objects.filter(user=user)



class BudgetForm(BaseUserModelForm):
    class Meta:
        model = Budget
        fields = ("name", "category", "amount", "period", "start_date", "end_date")
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        if self.user:
            self.fields["category"].queryset = Category.objects.filter(
                user=self.user, category_type=Category.CategoryType.EXPENSE
            )
        self.fields["category"].required = False

    def clean(self):
        cleaned_data = super().clean()
        period = cleaned_data.get("period")
        if period != Budget.Period.CUSTOM:
            cleaned_data["end_date"] = None
            self.instance.end_date = None
        return cleaned_data

    def save(self, commit=True):
        budget = super().save(commit=False)
        if self.user:
            budget.user = self.user
        if commit:
            budget.save()
        return budget


class PreferencesForm(forms.ModelForm):
    timezone = forms.ChoiceField(choices=[(tz, tz) for tz in pytz.common_timezones])

    class Meta:
        model = UserPreference
        fields = ("currency", "timezone", "language", "theme")
        widgets = {
            "currency": forms.TextInput(attrs={"maxlength": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs.setdefault("class", css)
        self.fields["currency"].widget.attrs.setdefault("placeholder", "USD")

    def clean_currency(self):
        currency = self.cleaned_data.get("currency", "USD").upper()
        if len(currency) != 3:
            raise forms.ValidationError(_("Use a three-letter currency code (e.g. USD)."))
        return currency


class TransactionExportForm(TransactionFilterForm):
    format = forms.ChoiceField(choices=(("csv", "CSV"), ("json", "JSON")), initial="csv")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        self.fields["format"].widget.attrs.setdefault("class", "form-select")
