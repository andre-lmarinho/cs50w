import csv
import io
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction as db_transaction
from django.db.models import Case, DecimalField, Q, Sum, Value, When
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)
from django.views.generic.edit import FormView

from .forms import (
    AccountForm,
    BudgetForm,
    CategoryForm,
    PreferencesForm,
    TransactionExportForm,
    TransactionFilterForm,
    TransactionForm,
    TransactionImportForm,
    UserRegistrationForm,
)
from .models import Account, Budget, Category, Transaction, UserPreference
from .utils import convert_amount


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "finance/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["accounts"] = Account.objects.filter(user=user).order_by("name")
        context["recent_transactions"] = (
            user.transactions.select_related("account", "category")[:5]
        )
        summary = _build_dashboard_summary(user)
        context.update(summary)
        context["budget_progress"] = get_budget_progress_data(user, limit=5)
        return context


def signup(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, _("Welcome! Your account has been created."))
            return redirect(reverse("finance:dashboard"))
    else:
        form = UserRegistrationForm()
    return render(request, "registration/signup.html", {"form": form})


class UserQuerySetMixin(LoginRequiredMixin):
    """
    Ensure queryset is limited to current user and pass user to forms.
    """

    model = None

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class AccountListView(UserQuerySetMixin, ListView):
    model = Account
    template_name = "finance/account_list.html"
    context_object_name = "accounts"


class AccountCreateView(UserQuerySetMixin, CreateView):
    model = Account
    form_class = AccountForm
    template_name = "finance/account_form.html"
    success_url = reverse_lazy("finance:account_list")

    def form_valid(self, form):
        messages.success(self.request, _("Account created successfully."))
        return super().form_valid(form)


class AccountUpdateView(UserQuerySetMixin, UpdateView):
    model = Account
    form_class = AccountForm
    template_name = "finance/account_form.html"
    success_url = reverse_lazy("finance:account_list")

    def form_valid(self, form):
        messages.success(self.request, _("Account updated successfully."))
        return super().form_valid(form)


class AccountDeleteView(UserQuerySetMixin, DeleteView):
    model = Account
    template_name = "finance/account_confirm_delete.html"
    success_url = reverse_lazy("finance:account_list")

    def delete(self, request, *args, **kwargs):
        account = self.get_object()
        if account.transactions.exists():
            messages.error(request, _("Cannot delete account with existing transactions."))
            return redirect(self.success_url)
        messages.success(request, _("Account deleted successfully."))
        return super().delete(request, *args, **kwargs)


class CategoryListView(UserQuerySetMixin, ListView):
    model = Category
    template_name = "finance/category_list.html"
    context_object_name = "categories"

    def get_queryset(self):
        qs = super().get_queryset().select_related("parent")
        category_type = self.request.GET.get("type")
        if category_type in dict(Category.CategoryType.choices):
            qs = qs.filter(category_type=category_type)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category_types"] = Category.CategoryType.choices
        return context


class CategoryCreateView(UserQuerySetMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "finance/category_form.html"
    success_url = reverse_lazy("finance:category_list")

    def form_valid(self, form):
        messages.success(self.request, _("Category created successfully."))
        return super().form_valid(form)


class CategoryUpdateView(UserQuerySetMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "finance/category_form.html"
    success_url = reverse_lazy("finance:category_list")

    def form_valid(self, form):
        messages.success(self.request, _("Category updated successfully."))
        return super().form_valid(form)


class CategoryDeleteView(UserQuerySetMixin, DeleteView):
    model = Category
    template_name = "finance/category_confirm_delete.html"
    success_url = reverse_lazy("finance:category_list")

    def delete(self, request, *args, **kwargs):
        category = self.get_object()
        if category.children.exists():
            messages.error(request, _("Cannot delete a category that has sub-categories."))
            return redirect(self.success_url)
        if category.transactions.exists():
            messages.error(request, _("Cannot delete a category linked to transactions."))
            return redirect(self.success_url)
        messages.success(request, _("Category deleted successfully."))
        return super().delete(request, *args, **kwargs)


class BudgetListView(UserQuerySetMixin, ListView):
    model = Budget
    template_name = "finance/budget_list.html"
    context_object_name = "budgets"

    def get_queryset(self):
        return super().get_queryset().select_related("category").order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["budget_data"] = get_budget_progress_data(self.request.user)
        return context


class BudgetCreateView(UserQuerySetMixin, CreateView):
    model = Budget
    form_class = BudgetForm
    template_name = "finance/budget_form.html"
    success_url = reverse_lazy("finance:budget_list")

    def form_valid(self, form):
        messages.success(self.request, _("Budget created successfully."))
        return super().form_valid(form)


class BudgetUpdateView(UserQuerySetMixin, UpdateView):
    model = Budget
    form_class = BudgetForm
    template_name = "finance/budget_form.html"
    success_url = reverse_lazy("finance:budget_list")

    def form_valid(self, form):
        messages.success(self.request, _("Budget updated successfully."))
        return super().form_valid(form)


class BudgetDeleteView(UserQuerySetMixin, DeleteView):
    model = Budget
    template_name = "finance/budget_confirm_delete.html"
    success_url = reverse_lazy("finance:budget_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Budget deleted successfully."))
        return super().delete(request, *args, **kwargs)


class PreferencesUpdateView(LoginRequiredMixin, UpdateView):
    model = UserPreference
    form_class = PreferencesForm
    template_name = "finance/preferences_form.html"
    success_url = reverse_lazy("finance:preferences")

    def get_object(self, queryset=None):
        return self.request.user.preferences

    def form_valid(self, form):
        response = super().form_valid(form)
        prefs = form.instance
        if prefs.language:
            translation.activate(prefs.language)
            self.request.LANGUAGE_CODE = prefs.language
            self.request.session[LANGUAGE_SESSION_KEY] = prefs.language
        if prefs.timezone:
            timezone.activate(prefs.timezone)
            self.request.session["django_timezone"] = prefs.timezone
        messages.success(self.request, _("Preferences updated successfully."))
        return response

class TransactionListView(UserQuerySetMixin, ListView):
    model = Transaction
    template_name = "finance/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 20

    def get_queryset(self):
        qs, form = build_transaction_queryset(self.request, self.request.user)
        self.filter_form = form
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = getattr(self, "filter_form", TransactionFilterForm(user=self.request.user))
        query_params = self.request.GET.copy()
        if "page" in query_params:
            query_params.pop("page")
        context["querystring"] = urlencode(query_params, doseq=True)
        context["export_form"] = TransactionExportForm(self.request.GET or None, user=self.request.user)
        return context

class TransactionCreateView(UserQuerySetMixin, CreateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "finance/transaction_form.html"
    success_url = reverse_lazy("finance:transaction_list")

    def form_valid(self, form):
        messages.success(self.request, _("Transaction created successfully."))
        return super().form_valid(form)


class TransactionUpdateView(UserQuerySetMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "finance/transaction_form.html"
    success_url = reverse_lazy("finance:transaction_list")

    def form_valid(self, form):
        messages.success(self.request, _("Transaction updated successfully."))
        return super().form_valid(form)


class TransactionDeleteView(UserQuerySetMixin, DeleteView):
    model = Transaction
    template_name = "finance/transaction_confirm_delete.html"
    success_url = reverse_lazy("finance:transaction_list")

class TransactionImportView(LoginRequiredMixin, FormView):
    template_name = "finance/transaction_import.html"
    form_class = TransactionImportForm
    success_url = reverse_lazy("finance:transaction_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        uploaded_file = form.cleaned_data["file"]
        delimiter = form.cleaned_data["delimiter"]
        date_format = form.cleaned_data["date_format"]
        columns = {
            key: form.cleaned_data[key]
            for key in [
                "date_column",
                "amount_column",
                "description_column",
                "account_column",
                "category_column",
                "currency_column",
                "tags_column",
                "notes_column",
            ]
        }
        default_account = form.cleaned_data.get("default_account")
        default_category = form.cleaned_data.get("default_category")

        try:
            decoded = uploaded_file.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            form.add_error("file", _("Could not decode the uploaded file. Please upload a UTF-8 encoded CSV."))
            return self.form_invalid(form)

        reader = csv.DictReader(io.StringIO(decoded), delimiter=delimiter)
        if not reader.fieldnames:
            form.add_error("file", _("The CSV file must include a header row."))
            return self.form_invalid(form)

        missing = [col for col in [columns["date_column"], columns["amount_column"]] if col and col not in reader.fieldnames]
        if missing:
            form.add_error("file", _("Missing required columns: %s") % ", ".join(missing))
            return self.form_invalid(form)

        accounts = {acc.name.lower(): acc for acc in Account.objects.filter(user=self.request.user)}
        categories = {cat.name.lower(): cat for cat in Category.objects.filter(user=self.request.user)}

        created = 0
        skipped = 0
        errors = []

        with db_transaction.atomic():
            for row_number, row in enumerate(reader, start=2):
                try:
                    date_value = row.get(columns["date_column"], "").strip()
                    if not date_value:
                        raise ValueError("missing date")
                    parsed_date = datetime.strptime(date_value, date_format).date()

                    raw_amount = row.get(columns["amount_column"], "").strip()
                    if not raw_amount:
                        raise ValueError("missing amount")
                    amount_str = raw_amount
                    if "," in amount_str and "." not in amount_str:
                        amount_str = amount_str.replace(".", "").replace(",", ".")
                    else:
                        amount_str = amount_str.replace(",", "")
                    amount = Decimal(amount_str)

                    account = default_account
                    account_name = row.get(columns["account_column"], "").strip() if columns["account_column"] else ""
                    if account_name:
                        account = accounts.get(account_name.lower())
                    if not account:
                        raise ValueError(_("Unknown account: %s") % (account_name or _("(empty)")))

                    category = default_category
                    category_name = row.get(columns["category_column"], "").strip() if columns["category_column"] else ""
                    if category_name:
                        category = categories.get(category_name.lower())
                        if category and category.category_type != Category.CategoryType.EXPENSE:
                            raise ValueError(_("Category must be an expense: %s") % category_name)
                        if not category:
                            raise ValueError(_("Unknown category: %s") % category_name)

                    currency = row.get(columns["currency_column"], "").strip().upper() if columns["currency_column"] else ""
                    if not currency:
                        currency = account.currency or getattr(getattr(self.request.user, "preferences", None), "currency", "USD")

                    description = row.get(columns["description_column"], "").strip() if columns["description_column"] else ""
                    notes = row.get(columns["notes_column"], "").strip() if columns["notes_column"] else ""
                    tags_value = row.get(columns["tags_column"], "") if columns["tags_column"] else ""
                    tags = ", ".join([tag.strip() for tag in tags_value.split(",") if tag.strip()])

                    Transaction.objects.create(
                        user=self.request.user,
                        account=account,
                        category=category,
                        date=parsed_date,
                        amount=amount,
                        currency=currency,
                        description=description,
                        notes=notes,
                        tags=tags,
                    )
                    created += 1
                except Exception as exc:
                    skipped += 1
                    errors.append(_("Row %(row)s: %(error)s") % {"row": row_number, "error": exc})

        if created:
            messages.success(self.request, _("Imported %(count)d transactions." ) % {"count": created})
        if skipped:
            messages.warning(self.request, _("Skipped %(count)d rows due to errors." ) % {"count": skipped})
            for message in errors[:5]:
                messages.warning(self.request, message)
        return super().form_valid(form)


class TransactionExportView(LoginRequiredMixin, View):
    def get(self, request):
        qs, form = build_transaction_queryset(request, request.user, form_class=TransactionExportForm)
        export_format = 'csv'
        if form.is_valid():
            export_format = form.cleaned_data.get('format', 'csv').lower()
        else:
            export_format = request.GET.get('format', 'csv').lower()

        if export_format == 'json':
            data = [
                {
                    'date': txn.date.isoformat(),
                    'account': txn.account.name,
                    'category': txn.category.name if txn.category else None,
                    'amount': float(txn.amount),
                    'currency': txn.currency,
                    'description': txn.description,
                    'notes': txn.notes,
                    'tags': txn.tags,
                }
                for txn in qs
            ]
            return JsonResponse(data, safe=False)

        response = HttpResponse(content_type='text/csv')
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename="transactions_{timestamp}.csv"'
        writer = csv.writer(response)
        writer.writerow(['date', 'account', 'category', 'amount', 'currency', 'description', 'notes', 'tags'])
        for txn in qs:
            writer.writerow([
                txn.date.isoformat(),
                txn.account.name,
                txn.category.name if txn.category else '',
                txn.amount,
                txn.currency,
                txn.description,
                txn.notes,
                txn.tags,
            ])
        return response




    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Transaction deleted successfully."))
        return super().delete(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Dashboard API helpers and endpoints
# ---------------------------------------------------------------------------


def _first_day_months_ago(reference_date, months):
    year = reference_date.year
    month = reference_date.month - months
    while month <= 0:
        month += 12
        year -= 1
    return reference_date.replace(year=year, month=month, day=1)


def _decimal_to_float(value):
    if value is None:
        return 0.0
    return float(value)


def _monthly_breakdown_queryset(user, start_date):
    income_case = Case(
        When(
            category__category_type=Category.CategoryType.INCOME,
            then="amount",
        ),
        default=Value(Decimal("0")),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )
    expense_case = Case(
        When(
            category__category_type=Category.CategoryType.EXPENSE,
            then="amount",
        ),
        default=Value(Decimal("0")),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )
    return (
        user.transactions.filter(date__gte=start_date)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(
            income=Sum(income_case),
            expense=Sum(expense_case),
        )
        .order_by("month")
    )


def get_budget_progress_data(user, limit=None):
    budgets = user.budgets.select_related("category").order_by("name")
    if limit:
        budgets = budgets[:limit]
    data = []
    for budget in budgets:
        spent = budget.spent_amount()
        remaining = budget.amount - spent
        percentage = 0.0 if not budget.amount else float(min(spent / budget.amount * 100, 999))
        data.append(
            {
                "budget": budget,
                "spent": spent,
                "remaining": remaining,
                "percentage": percentage,
                "over": spent > budget.amount,
            }
        )
    return data




def build_transaction_queryset(request, user, form_class=TransactionFilterForm):
    qs = user.transactions.select_related('account', 'category').order_by('-date', '-created_at')
    form = form_class(request.GET or None, user=user)
    if form.is_valid():
        data = form.cleaned_data
        account = data.get('account')
        category = data.get('category')
        if account:
            qs = qs.filter(account=account)
        if category:
            qs = qs.filter(category=category)
        if data.get('start_date'):
            qs = qs.filter(date__gte=data['start_date'])
        if data.get('end_date'):
            qs = qs.filter(date__lte=data['end_date'])
        tags = data.get('tags')
        if tags:
            tags_list = [tag.strip().lower() for tag in tags.split(',') if tag.strip()]
            for tag in tags_list:
                qs = qs.filter(tags__iregex=rf'(^|,\s*){tag}(,|$)')
        search = data.get('search')
        if search:
            qs = qs.filter(Q(description__icontains=search) | Q(notes__icontains=search))
    return qs, form

def _build_dashboard_summary(user):
    accounts = user.accounts.all()
    total_accounts = accounts.count()
    total_transactions = user.transactions.count()
    prefs = getattr(user, "preferences", None)
    preferred_currency = getattr(prefs, "currency", None) if prefs else None
    fallback_currency = accounts.first().currency if total_accounts else "USD"
    primary_currency = preferred_currency or fallback_currency

    total_balance = Decimal("0")
    for account in accounts:
        total_balance += convert_amount(
            account.current_balance, account.currency, primary_currency
        )

    today = timezone.localdate()
    start_month = today.replace(day=1)
    monthly_transactions = (
        user.transactions.filter(date__gte=start_month, date__lte=today)
        .select_related("category")
    )
    income = Decimal("0")
    expense = Decimal("0")
    for txn in monthly_transactions:
        amount = convert_amount(txn.amount, txn.currency, primary_currency)
        if txn.category and txn.category.category_type == Category.CategoryType.EXPENSE:
            expense += amount
        else:
            income += amount

    return {
        "total_accounts": total_accounts,
        "total_transactions": total_transactions,
        "total_balance": _decimal_to_float(total_balance),
        "monthly_income": _decimal_to_float(income),
        "monthly_expense": _decimal_to_float(expense),
        "monthly_net": _decimal_to_float(income - expense),
        "primary_currency": primary_currency,
    }


@login_required
def dashboard_summary_api(request):
    return JsonResponse(_build_dashboard_summary(request.user))


@login_required
def dashboard_accounts_api(request):
    accounts = (
        request.user.accounts.order_by("name")
        .values("name", "current_balance", "currency", "account_type")
    )
    data = [
        {
            "name": account["name"],
            "current_balance": _decimal_to_float(account["current_balance"]),
            "currency": account["currency"],
            "account_type": Account.AccountType(account["account_type"]).label,
        }
        for account in accounts
    ]
    return JsonResponse({"accounts": data})


@login_required
def dashboard_spending_api(request):
    try:
        months = max(1, min(12, int(request.GET.get("months", 1))))
    except ValueError:
        months = 1
    today = timezone.localdate()
    start_date = _first_day_months_ago(today, months - 1)
    transactions = (
        request.user.transactions.filter(
            date__gte=start_date, category__category_type=Category.CategoryType.EXPENSE
        )
        .exclude(category__isnull=True)
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    labels = [item["category__name"] for item in transactions]
    values = [_decimal_to_float(item["total"]) for item in transactions]
    return JsonResponse(
        {
            "labels": labels,
            "values": values,
            "months": months,
            "start_date": start_date.isoformat(),
        }
    )


@login_required
def dashboard_cashflow_api(request):
    try:
        months = max(1, min(12, int(request.GET.get("months", 6))))
    except ValueError:
        months = 6
    today = timezone.localdate()
    start_date = _first_day_months_ago(today, months - 1)

    monthly_data = _monthly_breakdown_queryset(request.user, start_date)
    month_map = {}
    for entry in monthly_data:
        month_value = entry["month"]
        month_key = month_value.date() if hasattr(month_value, "date") else month_value
        month_map[month_key] = {
            "income": _decimal_to_float(entry["income"]),
            "expense": _decimal_to_float(entry["expense"]),
        }

    labels = []
    incomes = []
    expenses = []

    current = start_date
    for _ in range(months):
        labels.append(current.strftime("%b %Y"))
        data = month_map.get(current, {"income": 0.0, "expense": 0.0})
        incomes.append(data["income"])
        expenses.append(data["expense"])
        # move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return JsonResponse(
        {
            "labels": labels,
            "income": incomes,
            "expense": expenses,
            "start_date": start_date.isoformat(),
        }
    )
