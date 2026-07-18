from django.contrib import admin

from academics.admin_mixins import EtablissementScopedAdmin

from .models import BudgetIA, Conversation, MessageConversation


@admin.register(BudgetIA)
class BudgetIAAdmin(EtablissementScopedAdmin, admin.ModelAdmin):
    list_display = ("etablissement", "plafond_mensuel_tokens", "tokens_utilises", "mois_courant")


class MessageInline(admin.TabularInline):
    model = MessageConversation
    extra = 0
    readonly_fields = ("role", "contenu", "date_creation", "tokens_utilises")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("titre", "eleve", "date_creation")
    inlines = [MessageInline]
