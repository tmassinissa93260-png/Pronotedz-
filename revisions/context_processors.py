from accounts.models import Utilisateur

from .services import est_classe_examen


def classe_examen(request):
    user = getattr(request, "user", None)
    if user and user.is_authenticated and user.role == Utilisateur.Role.ELEVE:
        return {"eleve_classe_examen": est_classe_examen(user.eleve)}
    return {"eleve_classe_examen": False}
