from django.utils import timezone, translation


class PreferenceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            prefs = getattr(user, "preferences", None)
            if prefs:
                if prefs.timezone:
                    timezone.activate(prefs.timezone)
                if prefs.language:
                    translation.activate(prefs.language)
                    request.LANGUAGE_CODE = prefs.language
        response = self.get_response(request)
        timezone.deactivate()
        translation.deactivate()
        return response
