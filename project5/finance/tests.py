import csv
import io

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Account, Budget, Category, Transaction, UserPreference


class FinanceModelsTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="alice",
            password="complexpassword123",
            email="alice@example.com",
        )
        self.account = Account.objects.create(
            user=self.user,
            name="Checking",
            account_type=Account.AccountType.ASSET,
            currency="USD",
            initial_balance=1000,
        )
        self.income_category = Category.objects.create(
            user=self.user,
            name="Salary",
            category_type=Category.CategoryType.INCOME,
        )
        self.expense_category = Category.objects.create(
            user=self.user,
            name="Groceries",
            category_type=Category.CategoryType.EXPENSE,
        )

    def test_account_creation_sets_current_balance(self):
        self.assertEqual(self.account.current_balance, self.account.initial_balance)

    def test_transactions_update_account_balance(self):
        income = Transaction.objects.create(
            user=self.user,
            account=self.account,
            category=self.income_category,
            date=date.today(),
            amount=500,
            currency="USD",
        )
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, 1500)

        # Update to expense and ensure balance adjusts accordingly.
        income.category = self.expense_category
        income.amount = 200
        income.save()
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, 800)

        # Delete transaction
        income.delete()
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, 1000)

    def test_transaction_requires_matching_user(self):
        other_user = get_user_model().objects.create_user(
            username="bob",
            password="otherpassword456",
            email="bob@example.com",
        )
        other_account = Account.objects.create(
            user=other_user,
            name="Other",
            account_type=Account.AccountType.ASSET,
            currency="USD",
            initial_balance=100,
        )
        with self.assertRaises(Exception):
            Transaction.objects.create(
                user=self.user,
                account=other_account,
                category=self.income_category,
                date=date.today(),
                amount=50,
                currency="USD",
            )


class FinanceViewsTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="charlie",
            password="password789",
            email="charlie@example.com",
        )
        self.client.login(username="charlie", password="password789")

    def test_account_list_requires_authentication(self):
        self.client.logout()
        response = self.client.get(reverse("finance:account_list"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))

    def test_authenticated_user_sees_only_their_accounts(self):
        Account.objects.create(
            user=self.user,
            name="My account",
            account_type=Account.AccountType.ASSET,
            currency="USD",
            initial_balance=100,
        )
        other = get_user_model().objects.create_user(
            username="diana",
            password="secret12345",
            email="diana@example.com",
        )
        Account.objects.create(
            user=other,
            name="External",
            account_type=Account.AccountType.ASSET,
            currency="USD",
            initial_balance=50,
        )
        response = self.client.get(reverse("finance:account_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My account")
        self.assertNotContains(response, "External")


class FinanceAPITestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="eve",
            password="securepass123",
            email="eve@example.com",
        )
        self.client.force_login(self.user)

        self.account = Account.objects.create(
            user=self.user,
            name="Main",
            account_type=Account.AccountType.ASSET,
            currency="USD",
            initial_balance=Decimal("1500.00"),
        )
        income_category = Category.objects.create(
            user=self.user,
            name="Consulting",
            category_type=Category.CategoryType.INCOME,
        )
        expense_category = Category.objects.create(
            user=self.user,
            name="Utilities",
            category_type=Category.CategoryType.EXPENSE,
        )
        today = timezone.localdate()
        Transaction.objects.create(
            user=self.user,
            account=self.account,
            category=income_category,
            date=today,
            amount=Decimal("800.00"),
            currency="USD",
        )
        Transaction.objects.create(
            user=self.user,
            account=self.account,
            category=expense_category,
            date=today,
            amount=Decimal("120.00"),
            currency="USD",
        )

    def test_dashboard_summary_api(self):
        response = self.client.get(reverse("finance:api_dashboard_summary"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_accounts", data)
        self.assertIn("total_balance", data)
        self.assertIn("monthly_income", data)
        self.assertGreaterEqual(data["total_accounts"], 1)

    def test_dashboard_accounts_api(self):
        response = self.client.get(reverse("finance:api_dashboard_accounts"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("accounts", payload)
        self.assertTrue(any(acc["name"] == "Main" for acc in payload["accounts"]))

    def test_dashboard_spending_api(self):
        response = self.client.get(reverse("finance:api_dashboard_spending"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("labels", payload)
        self.assertIn("values", payload)

    def test_dashboard_cashflow_api(self):
        response = self.client.get(reverse("finance:api_dashboard_cashflow"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("labels", payload)
        self.assertIn("income", payload)
        self.assertEqual(len(payload["labels"]), len(payload["income"]))


class BudgetPreferenceTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="frank",
            password="securepass456",
            email="frank@example.com",
        )
        self.account = Account.objects.create(
            user=self.user,
            name="Wallet",
            account_type=Account.AccountType.ASSET,
            currency="USD",
            initial_balance=Decimal("300.00"),
        )
        self.category = Category.objects.create(
            user=self.user,
            name="Dining",
            category_type=Category.CategoryType.EXPENSE,
        )

    def test_budget_progress_computation(self):
        budget = Budget.objects.create(
            user=self.user,
            name="Dining out",
            category=self.category,
            amount=Decimal("200.00"),
        )
        today = timezone.localdate()
        Transaction.objects.create(
            user=self.user,
            account=self.account,
            category=self.category,
            date=today,
            amount=Decimal("40.00"),
            currency="USD",
        )
        self.assertEqual(budget.spent_amount(), Decimal("40.00"))
        self.assertGreater(budget.progress_percentage(), 0)

    def test_user_preference_signal(self):
        prefs = self.user.preferences
        self.assertIsNotNone(prefs)
        self.assertEqual(prefs.theme, UserPreference.Theme.LIGHT)


class TransactionImportExportTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="iris",
            password="strongpass",
            email="iris@example.com",
        )
        self.client.force_login(self.user)
        self.account = Account.objects.create(
            user=self.user,
            name="Everyday",
            account_type=Account.AccountType.ASSET,
            currency="USD",
            initial_balance=Decimal("500.00"),
        )
        self.category = Category.objects.create(
            user=self.user,
            name="Groceries",
            category_type=Category.CategoryType.EXPENSE,
        )

    def _build_csv(self):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["date", "amount", "account", "category", "description", "currency", "tags"])
        writer.writerow(["2025-01-01", "42.50", "Everyday", "Groceries", "Market", "USD", "food, weekly"])
        writer.writerow(["2025-01-02", "15.00", "", "", "Snacks", "USD", "food"])
        return buffer.getvalue().encode("utf-8")

    def test_import_csv_creates_transactions(self):
        upload = SimpleUploadedFile("import.csv", self._build_csv(), content_type="text/csv")
        response = self.client.post(
            reverse("finance:transaction_import"),
            {
                "file": upload,
                "delimiter": ",",
                "date_format": "%Y-%m-%d",
                "date_column": "date",
                "amount_column": "amount",
                "description_column": "description",
                "account_column": "account",
                "category_column": "category",
                "currency_column": "currency",
                "tags_column": "tags",
                "notes_column": "",
                "default_account": self.account.pk,
                "default_category": self.category.pk,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 2)

    def test_export_csv(self):
        Transaction.objects.create(
            user=self.user,
            account=self.account,
            category=self.category,
            date=timezone.localdate(),
            amount=Decimal("10.00"),
            currency="USD",
            description="Test",
        )
        response = self.client.get(reverse("finance:transaction_export"), {"format": "csv"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        content = response.content.decode("utf-8")
        self.assertIn("Test", content)

    def test_export_json(self):
        Transaction.objects.create(
            user=self.user,
            account=self.account,
            category=self.category,
            date=timezone.localdate(),
            amount=Decimal("12.50"),
            currency="USD",
            description="Json test",
        )
        response = self.client.get(reverse("finance:transaction_export"), {"format": "json"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(any(item["description"] == "Json test" for item in data))
