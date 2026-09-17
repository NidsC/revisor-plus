from django import forms

from .models import User


class SignupExtrasForm(forms.Form):
    """Extra field rendered on allauth's stock signup form.

    Adults choose Parent or Tutor at sign-up; Parent is the default and a
    pupil is never offered here (pupils are created by their parent, see
    accounts/views.py add_child).
    """

    account_type = forms.ChoiceField(
        choices=[
            (User.Role.PARENT, "Parent"),
            (User.Role.TUTOR, "Tutor"),
        ],
        initial=User.Role.PARENT,
        required=False,
        widget=forms.RadioSelect,
        label="I am a",
    )

    def signup(self, request, user):
        """Required by allauth's custom-signup-form contract.

        The actual role assignment happens in AccountAdapter.save_user, which
        reads this same form's cleaned_data before the user row is first
        saved, so there is nothing further to do here.
        """
