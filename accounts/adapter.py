from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    """New sign-ups default to the student role."""

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        if not user.role:
            user.role = user.Role.STUDENT
        if commit:
            user.save()
        return user


def user_display(user):
    """Name shown in allauth's messages and templates.

    Allauth defaults to the username, which here is derived from the email local
    part — so signing in greeted "nideesh" rather than "Nideesh". Wired up via
    ACCOUNT_USER_DISPLAY in settings.
    """
    return getattr(user, "full_name", "") or user.email
