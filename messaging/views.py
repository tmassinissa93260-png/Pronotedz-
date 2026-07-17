from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render

from accounts.contacts import contacts_autorises

from .models import Conversation, Message


@login_required
def boite_reception(request):
    conversations = (
        Conversation.objects.filter(participants=request.user)
        .annotate(dernier_message=Max("messages__date_envoi"))
        .order_by("-dernier_message")
    )
    return render(request, "messaging/boite_reception.html", {"conversations": conversations})


@login_required
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(Conversation, pk=conversation_id, participants=request.user)

    if request.method == "POST":
        contenu = request.POST.get("contenu", "").strip()
        if contenu:
            Message.objects.create(conversation=conversation, expediteur=request.user, contenu=contenu)
        return redirect("messaging:conversation_detail", conversation_id=conversation.pk)

    return render(
        request,
        "messaging/conversation_detail.html",
        {"conversation": conversation, "messages_liste": conversation.messages.select_related("expediteur")},
    )


@login_required
def nouvelle_conversation(request):
    contacts = contacts_autorises(request.user)

    if request.method == "POST":
        sujet = request.POST.get("sujet", "").strip()
        contenu = request.POST.get("contenu", "").strip()
        destinataire_ids = set(request.POST.getlist("destinataires"))
        destinataires = contacts.filter(pk__in=destinataire_ids)

        if sujet and contenu and destinataires:
            conversation = Conversation.objects.create(sujet=sujet, createur=request.user)
            conversation.participants.add(request.user, *destinataires)
            Message.objects.create(conversation=conversation, expediteur=request.user, contenu=contenu)
            return redirect("messaging:conversation_detail", conversation_id=conversation.pk)

    return render(request, "messaging/nouvelle_conversation.html", {"contacts": contacts})
