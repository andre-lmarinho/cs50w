from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("wiki/<str:title>/", views.entry, name="entry"),
    path("search/", views.search, name="search"),
    path("new/", views.new_entry, name="new_entry"),
    path("wiki/<str:title>/edit/", views.edit_entry, name="edit_entry"),
    path("random/", views.random_entry, name="random_entry"),
]
