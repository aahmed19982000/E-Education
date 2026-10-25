# The level test is taken in English only, whatever language the rest of the site is in.
ENGLISH_ONLY_PREFIXES = ("/test/",)


class LanguageMiddleware:
    """Reads the visitor's chosen UI language from the session.

    We keep this separate from Django's own i18n machinery because the
    original design's copy lives in plain AR/EN dicts (core.translations),
    not in .po catalogs.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = request.session.get("lang", "ar")
        if lang not in ("ar", "en"):
            lang = "ar"
        request.lang_locked = request.path.startswith(ENGLISH_ONLY_PREFIXES)
        if request.lang_locked:
            lang = "en"
        request.lang = lang
        return self.get_response(request)


NOINDEX_PREFIXES = ("/dashboard/", "/admin/", "/accounts/", "/exams/", "/courses/mine/", "/courses/checkout/",
                    "/courses/lesson/", "/courses/attachment/", "/courses/payments/", "/courses/certificate/")


class NoIndexMiddleware:
    """Private pages (dashboard, student area, checkout) must never appear in search results."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(NOINDEX_PREFIXES):
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response
