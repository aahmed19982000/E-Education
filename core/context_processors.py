from .translations import get_translations


def site_language(request):
    lang = getattr(request, "lang", "ar")
    other_lang = "en" if lang == "ar" else "ar"
    return {
        "LANG": lang,
        "OTHER_LANG": other_lang,
        "DIR": "rtl" if lang == "ar" else "ltr",
        "IS_RTL": lang == "ar",
        "t": get_translations(lang),
    }
