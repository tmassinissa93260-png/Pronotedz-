from django.shortcuts import redirect
from django.urls import reverse


class ForceChangePasswordMiddleware:
    """Redirects users with must_change_password=True to the password change
    form before they can reach anything else — enforced server-side on every
    request, not just by hiding navigation links.

    Compares against request.path (not request.resolver_match, which is only
    populated once URL resolution happens deeper in the middleware chain, so
    it wouldn't be reliably set yet at this point).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and user.must_change_password:
            chemins_exemptes = (reverse("changer_mot_de_passe"), reverse("logout"))
            if (
                request.path not in chemins_exemptes
                and not request.path.startswith("/static/")
                and not request.path.startswith("/media/")
            ):
                return redirect("changer_mot_de_passe")
        return self.get_response(request)
