from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("signup/", views.signup, name="signup"),
    # Accounts
    path("accounts/list/", views.AccountListView.as_view(), name="account_list"),
    path("accounts/new/", views.AccountCreateView.as_view(), name="account_create"),
    path("accounts/<int:pk>/edit/", views.AccountUpdateView.as_view(), name="account_update"),
    path("accounts/<int:pk>/delete/", views.AccountDeleteView.as_view(), name="account_delete"),
    # Budgets
    path("budgets/", views.BudgetListView.as_view(), name="budget_list"),
    path("budgets/new/", views.BudgetCreateView.as_view(), name="budget_create"),
    path("budgets/<int:pk>/edit/", views.BudgetUpdateView.as_view(), name="budget_update"),
    path(
        "budgets/<int:pk>/delete/",
        views.BudgetDeleteView.as_view(),
        name="budget_delete",
    ),
    # Categories
    path("categories/", views.CategoryListView.as_view(), name="category_list"),
    path("categories/new/", views.CategoryCreateView.as_view(), name="category_create"),
    path("categories/<int:pk>/edit/", views.CategoryUpdateView.as_view(), name="category_update"),
    path(
        "categories/<int:pk>/delete/",
        views.CategoryDeleteView.as_view(),
        name="category_delete",
    ),
    # Transactions
    path("transactions/", views.TransactionListView.as_view(), name="transaction_list"),
    path("transactions/import/", views.TransactionImportView.as_view(), name="transaction_import"),
    path("transactions/export/", views.TransactionExportView.as_view(), name="transaction_export"),
    path("transactions/new/", views.TransactionCreateView.as_view(), name="transaction_create"),
    path(
        "transactions/<int:pk>/edit/",
        views.TransactionUpdateView.as_view(),
        name="transaction_update",
    ),
    path(
        "transactions/<int:pk>/delete/",
        views.TransactionDeleteView.as_view(),
        name="transaction_delete",
    ),
    path("settings/preferences/", views.PreferencesUpdateView.as_view(), name="preferences"),
    # Dashboard APIs
    path("api/dashboard/summary/", views.dashboard_summary_api, name="api_dashboard_summary"),
    path("api/dashboard/accounts/", views.dashboard_accounts_api, name="api_dashboard_accounts"),
    path("api/dashboard/spending/", views.dashboard_spending_api, name="api_dashboard_spending"),
    path("api/dashboard/cashflow/", views.dashboard_cashflow_api, name="api_dashboard_cashflow"),
]
