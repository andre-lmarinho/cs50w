import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, Paginator
from django.db import IntegrityError
from django.db.models import Exists, OuterRef
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import Follow, Like, Post, User

POSTS_PER_PAGE = 10


def index(request):
    return render(request, "network/index.html", {"feed": "all"})


@login_required
def following(request):
    return render(request, "network/index.html", {"feed": "following"})


def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    return render(
        request,
        "network/index.html",
        {
            "feed": "profile",
            "profile_username": profile_user.username,
        },
    )


def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))

        return render(
            request, "network/login.html", {"message": "Invalid username and/or password."}
        )

    return render(request, "network/login.html")


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
            return render(
                request,
                "network/register.html",
                {"message": "Passwords must match."},
            )

        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(
                request,
                "network/register.html",
                {"message": "Username already taken."},
            )
        login(request, user)
        return HttpResponseRedirect(reverse("index"))

    return render(request, "network/register.html")


def serialize_post(post, viewing_user=None):
    liked = False
    can_edit = False

    if viewing_user and viewing_user.is_authenticated:
        liked = getattr(post, "is_liked", None)
        if liked is None:
            liked = Like.objects.filter(user=viewing_user, post=post).exists()
        can_edit = post.author_id == viewing_user.id

    return {
        "id": post.id,
        "author": post.author.username,
        "author_id": post.author.id,
        "content": post.content,
        "created_at": post.created_at.isoformat(),
        "created_at_display": post.created_at.strftime("%b %d %Y, %I:%M %p"),
        "updated_at": post.updated_at.isoformat(),
        "like_count": post.like_count,
        "liked": liked,
        "can_edit": can_edit,
    }


def paginate_queryset(queryset, page_number, per_page=POSTS_PER_PAGE):
    paginator = Paginator(queryset, per_page)
    try:
        page_obj = paginator.page(page_number or 1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)
    return page_obj, paginator


@require_http_methods(["GET", "POST"])
def api_posts(request):
    if request.method == "GET":
        feed = request.GET.get("feed", "all")
        page = request.GET.get("page", 1)
        username = request.GET.get("username")

        posts = Post.objects.select_related("author").all()

        if feed == "following":
            if not request.user.is_authenticated:
                return JsonResponse({"error": "Authentication required."}, status=401)
            posts = posts.filter(author__followers__follower=request.user)

        elif feed == "profile":
            profile_user = get_object_or_404(User, username=username)
            posts = posts.filter(author=profile_user)
        elif feed != "all":
            return JsonResponse({"error": "Invalid feed."}, status=400)

        if request.user.is_authenticated:
            posts = posts.annotate(
                is_liked=Exists(
                    Like.objects.filter(user=request.user, post=OuterRef("pk"))
                )
            )

        page_obj, paginator = paginate_queryset(posts, page)

        return JsonResponse(
            {
                "page": page_obj.number,
                "total_pages": paginator.num_pages,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
                "results": [serialize_post(post, request.user) for post in page_obj],
            }
        )

    # POST: create a new post
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    content = (data.get("content") or "").strip()
    if not content:
        return JsonResponse({"error": "Post content cannot be empty."}, status=400)
    if len(content) > 1024:
        return JsonResponse({"error": "Post content exceeds 1024 characters."}, status=400)

    post = Post.objects.create(author=request.user, content=content)
    return JsonResponse(serialize_post(post, request.user), status=201)


@require_http_methods(["GET", "PUT"])
def api_post_detail(request, post_id):
    post = get_object_or_404(Post.objects.select_related("author"), pk=post_id)

    if request.method == "GET":
        return JsonResponse(serialize_post(post, request.user))

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    updated = False

    if "content" in data:
        if post.author_id != request.user.id:
            return JsonResponse({"error": "You cannot edit this post."}, status=403)
        new_content = (data.get("content") or "").strip()
        if not new_content:
            return JsonResponse(
                {"error": "Post content cannot be empty."},
                status=400,
            )
        if len(new_content) > 1024:
            return JsonResponse(
                {"error": "Post content exceeds 1024 characters."},
                status=400,
            )
        if new_content != post.content:
            post.content = new_content
            post.save(update_fields=["content", "updated_at"])
            updated = True

    if data.get("toggle_like"):
        like, created = Like.objects.get_or_create(user=request.user, post=post)
        if not created:
            like.delete()
        updated = True

    if updated:
        post.refresh_from_db()

    return JsonResponse(serialize_post(post, request.user))


@require_GET
def api_profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    followers_count = profile_user.followers.count()
    following_count = profile_user.following.count()

    is_self = request.user.is_authenticated and request.user.username == username
    is_following = False
    if request.user.is_authenticated and not is_self:
        is_following = Follow.objects.filter(
            follower=request.user, following=profile_user
        ).exists()

    return JsonResponse(
        {
            "username": profile_user.username,
            "followers": followers_count,
            "following": following_count,
            "is_self": is_self,
            "is_following": is_following,
        }
    )


@require_POST
@login_required
def api_toggle_follow(request, username):
    target = get_object_or_404(User, username=username)
    if target == request.user:
        return JsonResponse({"error": "You cannot follow yourself."}, status=400)

    follow, created = Follow.objects.get_or_create(
        follower=request.user, following=target
    )
    if not created:
        follow.delete()
        is_following = False
    else:
        is_following = True

    return JsonResponse(
        {
            "is_following": is_following,
            "followers": target.followers.count(),
            "following": target.following.count(),
        }
    )
