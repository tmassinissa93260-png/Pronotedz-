from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """View decorator restricting access to the given Utilisateur.Role values."""

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied(
                    "Vous n'avez pas les droits pour accéder à cette page."
                )
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


class RoleRequiredMixin:
    """CBV mixin restricting access to the given Utilisateur.Role values."""

    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())
        if request.user.role not in self.allowed_roles:
            raise PermissionDenied(
                "Vous n'avez pas les droits pour accéder à cette page."
            )
        return super().dispatch(request, *args, **kwargs)
