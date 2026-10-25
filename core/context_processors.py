from django.conf import settings

from .models import SiteSettings
from .translations import get_translations


META_DESCRIPTION = {
    "ar": "أكاديمية E-Education: كورسات إنجليزي مباشرة أونلاين (جماعي وخاص) مع مدرسين متخصصين، واختبار مستوى مجاني.",
    "en": "E-Education Academy: live online English courses (group and private) with expert teachers, plus a free level test.",
}


def site_language(request):
    lang = getattr(request, "lang", "ar")
    site = SiteSettings.load()
    other_lang = "en" if lang == "ar" else "ar"
    return {
        "LANG": lang,
        "LANG_LOCKED": getattr(request, "lang_locked", False),
        "OTHER_LANG": other_lang,
        "DIR": "rtl" if lang == "ar" else "ltr",
        "IS_RTL": lang == "ar",
        "t": get_translations(lang),
        "SITE_URL": settings.SITE_URL,
        "CANONICAL_URL": settings.SITE_URL + request.path,
        "META_DESCRIPTION": META_DESCRIPTION[lang],
        "SITE_WHATSAPP_URL": site.whatsapp_url,
        "PLAN_FEATURES": site.plan_features(lang),
    }
