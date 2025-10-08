from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import BidForm, CommentForm, ListingForm
from .models import Bid, Category, Listing, User


def index(request):
    listings = (
        Listing.objects.filter(is_active=True)
        .select_related("owner", "category")
        .prefetch_related("bids")
    )
    return render(
        request,
        "auctions/index.html",
        {"listings": listings},
    )


def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))

        messages.error(request, "Invalid username and/or password.")
        return render(request, "auctions/login.html")

    return render(request, "auctions/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]

        if password != confirmation:
            messages.error(request, "Passwords must match.")
            return render(request, "auctions/register.html")

        try:
            user = User.objects.create_user(username, email, password)
        except IntegrityError:
            messages.error(request, "Username already taken.")
            return render(request, "auctions/register.html")

        login(request, user)
        messages.success(request, "Welcome! Your account has been created.")
        return HttpResponseRedirect(reverse("index"))

    return render(request, "auctions/register.html")


@login_required
def create_listing(request):
    if request.method == "POST":
        form = ListingForm(request.POST)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.owner = request.user
            category_name = form.cleaned_data.get("category", "").strip()
            if category_name:
                existing = Category.objects.filter(name__iexact=category_name).first()
                listing.category = existing or Category.objects.create(name=category_name)
            listing.save()
            messages.success(request, "Listing created successfully.")
            return redirect("listing_detail", listing_id=listing.id)
    else:
        form = ListingForm()

    return render(request, "auctions/create_listing.html", {"form": form})


def listing_detail(request, listing_id):
    listing = get_object_or_404(
        Listing.objects.select_related("owner", "category"),
        pk=listing_id,
    )
    bids = listing.bids.select_related("bidder")
    comments = listing.comments.select_related("author")

    bid_form = BidForm()
    comment_form = CommentForm()
    current_price = listing.current_price
    is_owner = request.user.is_authenticated and request.user == listing.owner
    is_watching = (
        request.user.is_authenticated
        and request.user.watchlist.filter(pk=listing_id).exists()
    )
    winning_bidder = listing.winning_bidder

    if request.method == "POST":
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to take that action.")
            return redirect("login")

        action = request.POST.get("action")

        if action == "bid":
            bid_form = BidForm(request.POST)
            if not listing.is_active:
                messages.error(request, "This listing is closed.")
            elif bid_form.is_valid():
                amount = bid_form.cleaned_data["amount"]
                if amount <= listing.current_price:
                    bid_form.add_error(
                        "amount",
                        "Bid must be greater than the current price.",
                    )
                else:
                    Bid.objects.create(
                        listing=listing,
                        bidder=request.user,
                        amount=amount,
                    )
                    messages.success(request, "Bid placed successfully.")
                    return redirect("listing_detail", listing_id=listing_id)

        elif action == "comment":
            comment_form = CommentForm(request.POST)
            if not listing.is_active:
                messages.error(request, "This listing is closed.")
            elif comment_form.is_valid():
                listing.comments.create(
                    author=request.user,
                    body=comment_form.cleaned_data["body"],
                )
                messages.success(request, "Comment added.")
                return redirect("listing_detail", listing_id=listing_id)

        elif action == "close":
            if not is_owner:
                messages.error(request, "Only the listing owner can close the auction.")
            elif not listing.is_active:
                messages.info(request, "This listing is already closed.")
            else:
                listing.is_active = False
                listing.save(update_fields=["is_active"])
                messages.success(request, "You have closed this auction.")
                return redirect("listing_detail", listing_id=listing_id)

    return render(
        request,
        "auctions/listing_detail.html",
        {
            "listing": listing,
            "bids": bids,
            "comments": comments,
            "bid_form": bid_form,
            "comment_form": comment_form,
            "current_price": current_price,
            "bid_count": bids.count(),
            "is_owner": is_owner,
            "is_watching": is_watching,
            "winning_bidder": winning_bidder,
        },
    )


@login_required
def toggle_watchlist(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id)

    if request.method != "POST":
        return redirect("listing_detail", listing_id=listing_id)

    redirect_target = request.POST.get("next") or reverse(
        "listing_detail",
        kwargs={"listing_id": listing_id},
    )

    if request.user.watchlist.filter(pk=listing_id).exists():
        request.user.watchlist.remove(listing)
        messages.info(request, "Listing removed from your watchlist.")
    else:
        request.user.watchlist.add(listing)
        messages.success(request, "Listing added to your watchlist.")

    return HttpResponseRedirect(redirect_target)


@login_required
def watchlist(request):
    listings = (
        request.user.watchlist.select_related("owner", "category")
        .prefetch_related("bids")
    )
    return render(request, "auctions/watchlist.html", {"listings": listings})


def categories(request):
    categories_qs = Category.objects.annotate(
        active_count=Count("listings", filter=Q(listings__is_active=True))
    ).order_by("name")
    return render(request, "auctions/categories.html", {"categories": categories_qs})


def category_detail(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    listings = (
        category.listings.filter(is_active=True)
        .select_related("owner")
        .prefetch_related("bids")
    )
    return render(
        request,
        "auctions/category_detail.html",
        {"category": category, "listings": listings},
    )
