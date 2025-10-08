from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register"),
    path("listings/create/", views.create_listing, name="create_listing"),
    path("listings/<int:listing_id>/", views.listing_detail, name="listing_detail"),
    path("listings/<int:listing_id>/watch/", views.toggle_watchlist, name="toggle_watchlist"),
    path("watchlist/", views.watchlist, name="watchlist"),
    path("categories/", views.categories, name="categories"),
    path("categories/<int:category_id>/", views.category_detail, name="category_detail"),
]
