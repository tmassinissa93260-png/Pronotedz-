def etablissement(request):
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        return {"etablissement": user.etablissement}
    return {"etablissement": None}
