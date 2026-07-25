def subscription_flags(request):
    """Expose {{ is_subscribed }} to all templates."""
    sub = None
    if request.user.is_authenticated:
        sub = getattr(request.user, "subscription", None)
    return {"is_subscribed": bool(sub and sub.is_active)}
