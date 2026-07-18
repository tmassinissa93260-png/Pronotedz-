from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Utilisateur
from accounts.permissions import role_required
from timetable.models import EmploiDuTempsEntry

from .models import Conversation
from .services import envoyer_message, generer_fiche_revision


@role_required(Utilisateur.Role.ELEVE)
def conversation_liste(request):
    conversations = Conversation.objects.filter(eleve=request.user.eleve)
    return render(request, "assistant_ia/conversation_liste.html", {"conversations": conversations})


@role_required(Utilisateur.Role.ELEVE)
def conversation_nouvelle(request):
    conversation = Conversation.objects.create(eleve=request.user.eleve)
    return redirect("assistant_ia:conversation_detail", conversation_id=conversation.pk)


@role_required(Utilisateur.Role.ELEVE)
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(Conversation, pk=conversation_id, eleve=request.user.eleve)

    if request.method == "POST":
        matiere = request.POST.get("fiche_revision_matiere")
        if matiere:
            generer_fiche_revision(conversation, matiere)
        else:
            texte = request.POST.get("message", "").strip()
            if texte:
                envoyer_message(conversation, texte)
            else:
                messages.error(request, "Le message ne peut pas être vide.")
        return redirect("assistant_ia:conversation_detail", conversation_id=conversation.pk)

    matieres = sorted({
        e.matiere.nom
        for e in EmploiDuTempsEntry.objects.filter(classe=request.user.eleve.classe).select_related("matiere")
    })
    return render(
        request, "assistant_ia/conversation_detail.html",
        {"conversation": conversation, "matieres": matieres},
    )
