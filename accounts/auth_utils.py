from django.contrib.auth import authenticate, get_user_model

UserModel = get_user_model()


def authenticate_by_email(request, email, password):
    """Authenticate an account by its email field, independent of whatever its
    username happens to be (accounts created via `createsuperuser` may have a
    username that differs from their email).

    Still preserves Django's built-in timing-attack mitigation: when no account
    matches the email, a dummy password hash is computed anyway so that
    "unknown email" and "wrong password" take the same amount of time to
    reject, preventing account enumeration via response time.
    """
    try:
        candidate = UserModel._default_manager.get(email__iexact=email)
    except UserModel.DoesNotExist:
        UserModel().set_password(password)
        return None
    return authenticate(request, username=candidate.get_username(), password=password)
