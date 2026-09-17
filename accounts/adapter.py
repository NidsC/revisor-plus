from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    """New sign-ups choose Parent or Tutor via SignupExtrasForm's
    ``account_type`` field; Parent is the default and pupils never
    self-register through this form (pupils are created by their parent,
    see accounts/views.py add_child)."""

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        account_type = getattr(form, "cleaned_data", {}).get("account_type")
        if account_type == user.Role.TUTOR:
            user.role = user.Role.TUTOR
        else:
            user.role = user.Role.PARENT
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
