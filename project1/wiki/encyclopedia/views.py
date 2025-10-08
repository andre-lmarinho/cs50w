import random

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from markdown2 import markdown

from . import util
from .forms import EditEntryForm, NewEntryForm


def index(request):
    return render(request, "encyclopedia/index.html", {
        "entries": util.list_entries()
    })


def entry(request, title):
    entry_markdown = util.get_entry(title)
    if entry_markdown is None:
        return render(
            request,
            "encyclopedia/error.html",
            {"message": f"The entry '{title}' was not found.", "title": title},
            status=404,
        )

    return render(request, "encyclopedia/entry.html", {
        "title": title,
        "content": markdown(entry_markdown)
    })


def search(request):
    query = request.GET.get("q", "").strip()
    if not query:
        return HttpResponseRedirect(reverse("index"))

    entries = util.list_entries()
    matching_exact = next((entry for entry in entries if entry.lower() == query.lower()), None)
    if matching_exact:
        return HttpResponseRedirect(reverse("entry", kwargs={"title": matching_exact}))

    filtered_entries = [entry for entry in entries if query.lower() in entry.lower()]
    return render(request, "encyclopedia/search_results.html", {
        "entries": filtered_entries,
        "query": query
    })


def new_entry(request):
    if request.method == "POST":
        form = NewEntryForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data["title"]
            content = form.cleaned_data["content"]

            existing_titles = [entry.lower() for entry in util.list_entries()]
            if title.lower() in existing_titles:
                form.add_error("title", "An entry with this title already exists.")
            else:
                util.save_entry(title, content)
                return HttpResponseRedirect(reverse("entry", kwargs={"title": title}))
    else:
        form = NewEntryForm()

    return render(request, "encyclopedia/new_entry.html", {"form": form})


def edit_entry(request, title):
    entry_markdown = util.get_entry(title)
    if entry_markdown is None:
        return render(
            request,
            "encyclopedia/error.html",
            {"message": f"The entry '{title}' was not found.", "title": title},
            status=404,
        )

    if request.method == "POST":
        form = EditEntryForm(request.POST)
        if form.is_valid():
            content = form.cleaned_data["content"]
            util.save_entry(title, content)
            return HttpResponseRedirect(reverse("entry", kwargs={"title": title}))
    else:
        form = EditEntryForm(initial={"content": entry_markdown})

    return render(request, "encyclopedia/edit_entry.html", {"form": form, "title": title})


def random_entry(request):
    entries = util.list_entries()
    if not entries:
        return render(
            request,
            "encyclopedia/error.html",
            {"message": "No entries are available yet."},
            status=404,
        )

    title = random.choice(entries)
    return HttpResponseRedirect(reverse("entry", kwargs={"title": title}))
