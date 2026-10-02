from accounts.models import Profile

ROLE_SUPER_ADMIN = "super_admin"
ROLE_MANAGER = Profile.ROLE_MANAGER
ROLE_CONTENT_STAFF = Profile.ROLE_CONTENT_STAFF
ROLE_SUPPORT = Profile.ROLE_SUPPORT
ROLE_TEACHER = Profile.ROLE_TEACHER

ROLE_LABELS = {
    ROLE_SUPER_ADMIN: "مدير عام",
    ROLE_MANAGER: "مدير",
    ROLE_CONTENT_STAFF: "مشرف المحتوى",
    ROLE_SUPPORT: "مسؤول خدمة العملاء",
    ROLE_TEACHER: "مدرّس",
}

SECTION_ARTICLES = "articles"
SECTION_TEAM = "team"
SECTION_QUESTIONS = "questions"
SECTION_MESSAGES = "messages"
SECTION_COURSES = "courses"
SECTION_REQUESTS = "requests"
SECTION_USERS = "users"

# None = no access, "read" = view only, "write" = full CRUD.
ROLE_PERMISSIONS = {
    ROLE_SUPER_ADMIN: {
        SECTION_ARTICLES: "write",
        SECTION_TEAM: "write",
        SECTION_QUESTIONS: "write",
        SECTION_MESSAGES: "write",
        SECTION_COURSES: "write",
        SECTION_REQUESTS: "write",
        SECTION_USERS: "write",
    },
    # Administrator levels: manager (everything, incl. members), content staff, customer support.
    ROLE_MANAGER: {
        SECTION_ARTICLES: "write",
        SECTION_TEAM: "write",
        SECTION_QUESTIONS: "write",
        SECTION_MESSAGES: "write",
        SECTION_COURSES: "write",
        SECTION_REQUESTS: "write",
        SECTION_USERS: "write",
    },
    ROLE_SUPPORT: {
        SECTION_ARTICLES: None,
        SECTION_TEAM: None,
        SECTION_QUESTIONS: None,
        SECTION_MESSAGES: "write",
        SECTION_COURSES: "read",
        SECTION_REQUESTS: "write",
        SECTION_USERS: None,
    },
    ROLE_CONTENT_STAFF: {
        SECTION_ARTICLES: "write",
        SECTION_TEAM: "write",
        SECTION_QUESTIONS: "write",
        SECTION_MESSAGES: "write",
        SECTION_COURSES: "write",
        SECTION_REQUESTS: "write",
        SECTION_USERS: None,
    },
    ROLE_TEACHER: {
        SECTION_ARTICLES: None,
        SECTION_TEAM: None,
        SECTION_QUESTIONS: "read",
        SECTION_MESSAGES: "read",
        SECTION_COURSES: "read",
        SECTION_REQUESTS: "read",
        SECTION_USERS: None,
    },
}


def get_dashboard_role(user):
    """Return the dashboard role for a user, or None if they have no dashboard access."""
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return None
    if user.is_superuser:
        return ROLE_SUPER_ADMIN
    if not user.is_staff:
        return None
    profile = getattr(user, "profile", None)
    role = getattr(profile, "role", "") or None
    if role not in ROLE_PERMISSIONS:
        return None
    return role


def get_access_level(role, section):
    """Return None / "read" / "write" for a given role + section."""
    if role is None:
        return None
    return ROLE_PERMISSIONS.get(role, {}).get(section)


def can_access(role, section, mode="read"):
    level = get_access_level(role, section)
    if level is None:
        return False
    if mode == "write":
        return level == "write"
    return True


def role_label(role):
    return ROLE_LABELS.get(role, "")
