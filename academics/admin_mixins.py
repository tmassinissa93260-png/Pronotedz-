class EtablissementScopedAdmin:
    """Scopes a ModelAdmin's queryset to the logged-in admin's établissement.

    Applies even to is_superuser accounts: our ADMIN role reuses
    is_superuser to unlock full CRUD in Django admin, but that flag only
    bypasses Django's *permission* checks — get_queryset is plain code we
    control, so tenant isolation still holds here.
    """

    etablissement_lookup = "etablissement"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        etablissement = getattr(request.user, "etablissement", None)
        if etablissement is None:
            return qs.none()
        return qs.filter(**{self.etablissement_lookup: etablissement})

    def save_model(self, request, obj, form, change):
        if not change and hasattr(obj, "etablissement_id") and not obj.etablissement_id:
            obj.etablissement = request.user.etablissement
        super().save_model(request, obj, form, change)
