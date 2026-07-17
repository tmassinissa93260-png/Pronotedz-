from django.db.models import Q

from .models import Enseignant, Utilisateur


def classes_enseignees(enseignant):
    from academics.models import Classe

    return Classe.objects.filter(emploi_du_temps__enseignant=enseignant).distinct()


def enseignants_de_classe(classe):
    return Enseignant.objects.filter(emploi_du_temps__classe=classe).distinct()


def contacts_autorises(user):
    """Utilisateur queryset this user may message or book a rendez-vous with.

    Scoped by role so a parent can only reach the teachers of their own
    children (or the administration), a teacher can only reach the
    élèves/parents of the classes they actually teach, etc.
    """
    if user.role == Utilisateur.Role.ADMIN:
        return Utilisateur.objects.exclude(pk=user.pk)

    if user.role == Utilisateur.Role.ENSEIGNANT:
        classes = classes_enseignees(user.enseignant)
        return (
            Utilisateur.objects.filter(
                Q(eleve__classe__in=classes)
                | Q(parent__enfants__classe__in=classes)
                | Q(role=Utilisateur.Role.ADMIN)
            )
            .exclude(pk=user.pk)
            .distinct()
        )

    if user.role == Utilisateur.Role.ELEVE:
        enseignants = enseignants_de_classe(user.eleve.classe)
        return Utilisateur.objects.filter(
            Q(enseignant__in=enseignants) | Q(role=Utilisateur.Role.ADMIN)
        ).distinct()

    if user.role == Utilisateur.Role.PARENT:
        enfants = user.parent.enfants.all()
        enseignants = Enseignant.objects.filter(emploi_du_temps__classe__eleves__in=enfants).distinct()
        return Utilisateur.objects.filter(
            Q(enseignant__in=enseignants) | Q(role=Utilisateur.Role.ADMIN)
        ).distinct()

    return Utilisateur.objects.none()
