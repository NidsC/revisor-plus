from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def landing(request):
    return render(request, "pages/landing.html")


@login_required
def after_login(request):
    """Route users to the right home by role."""
    u = request.user
    if u.is_superuser or u.role == u.Role.ADMIN:
        return redirect("/admin/")
    if u.is_tutor:
        return redirect("tutoring:dashboard")
    return redirect("practice:dashboard")
