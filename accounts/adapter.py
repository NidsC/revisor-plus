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
