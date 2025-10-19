from .models import UserPreference


def user_preferences(request):
    prefs = None
    if getattr(request, "user", None) and request.user.is_authenticated:
        prefs, _ = UserPreference.objects.get_or_create(user=request.user)
    theme = getattr(prefs, "theme", "light") if prefs else "light"
    currency = getattr(prefs, "currency", "USD") if prefs else "USD"
    return {
        "user_preferences": prefs,
        "user_theme": theme,
        "user_currency": currency,
    }
