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
        request.lang = lang
        return self.get_response(request)
