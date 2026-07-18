from django.contrib import messages
from django.shortcuts import redirect, render

from accounts.models import Utilisateur
from accounts.permissions import role_required


@role_required(Utilisateur.Role.PARENT)
def preferences_notifications(request):
    if request.method == "POST":
        langue = request.POST.get("langue_notifications")
        if langue in Utilisateur.LangueNotifications.values:
            request.user.langue_notifications = langue
            request.user.save(update_fields=["langue_notifications"])
            messages.success(request, "Préférence enregistrée.")
        return redirect("rapport_parent:preferences_notifications")

    return render(
        request, "rapport_parent/preferences.html",
        {"langues": Utilisateur.LangueNotifications.choices},
    )
