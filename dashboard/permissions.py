from accounts.models import Profile

ROLE_SUPER_ADMIN = "super_admin"
ROLE_CONTENT_STAFF = Profile.ROLE_CONTENT_STAFF
ROLE_TEACHER = Profile.ROLE_TEACHER

ROLE_LABELS = {
    ROLE_SUPER_ADMIN: "مدير عام",
    ROLE_CONTENT_STAFF: "موظف محتوى",
    ROLE_TEACHER: "مدرّس",
}

SECTION_LEVELS = "levels"
SECTION_ARTICLES = "articles"
SECTION_QUESTIONS = "questions"
SECTION_MESSAGES = "messages"
SECTION_USERS = "users"

# None = no access, "read" = view only, "write" = full CRUD.
ROLE_PERMISSIONS = {
    ROLE_SUPER_ADMIN: {
        SECTION_LEVELS: "write",
        SECTION_ARTICLES: "write",
        SECTION_QUESTIONS: "write",
        SECTION_MESSAGES: "write",
        SECTION_USERS: "write",
    },
    ROLE_CONTENT_STAFF: {
        SECTION_LEVELS: "write",
        SECTION_ARTICLES: "write",
        SECTION_QUESTIONS: "write",
        SECTION_MESSAGES: "write",
        SECTION_USERS: None,
    },
    ROLE_TEACHER: {
        SECTION_LEVELS: None,
        SECTION_ARTICLES: None,
        SECTION_QUESTIONS: "read",
        SECTION_MESSAGES: "read",
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
    if role not in (ROLE_CONTENT_STAFF, ROLE_TEACHER):
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
