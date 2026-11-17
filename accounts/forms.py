from django import forms
from django.utils.safestring import mark_safe

from .models import User


def accept_terms_field():
    """The Terms agreement checkbox: identical on the sign-up form and on accounts/accept_terms.html."""
    return forms.BooleanField(
        required=True,
        label_suffix="",
        label=mark_safe(
            'I agree to the <a href="/terms/" target="_blank" rel="noopener">Terms of Service</a> '
            'and I have read the <a href="/privacy/" target="_blank" rel="noopener">Privacy Policy</a>'
        ),
        error_messages={"required": "Please tick the box to agree to the Terms of Service."},
    )


class SignupExtrasForm(forms.Form):
    """Extra field rendered on allauth's stock signup form.

    Adults choose Parent or Tutor at sign-up; Parent is the default and a
    pupil is never offered here (pupils are created by their parent, see
    accounts/views.py add_child). The agreement is recorded by AccountAdapter.save_user.
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
    accept_terms = accept_terms_field()

    def signup(self, request, user):
        """Required by allauth's custom-signup-form contract.

        The actual role assignment happens in AccountAdapter.save_user, which
        reads this same form's cleaned_data before the user row is first
        saved, so there is nothing further to do here.
        """


class AcceptTermsForm(forms.Form):
    """Just the Terms agreement, for accounts that pre-date the published Terms."""

    accept_terms = accept_terms_field()
