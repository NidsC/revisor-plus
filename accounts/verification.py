"""Login stage that exempts pupils from allauth's email verification.

Pupils have no email address and log in by the username their parent chose, so under
ACCOUNT_EMAIL_VERIFICATION = "mandatory" allauth's own stage would hold every one of them
at the verification page forever. Parents and tutors go through the stock stage unchanged.
"""
from allauth.account.stages import EmailVerificationStage


class PupilAwareEmailVerificationStage(EmailVerificationStage):
    def handle(self):
        user = self.login.user
        if user is not None and (user.role == user.Role.STUDENT or not user.email):
            return None, True
        return super().handle()
