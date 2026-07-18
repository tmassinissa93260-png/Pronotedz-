from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from academics.models import Etablissement
from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve

from .models import BudgetIA, Conversation, MessageConversation
from .services import MESSAGE_BUDGET_EPUISE, MESSAGE_NON_CONFIGURE, envoyer_message, generer_fiche_revision


def _fake_response(texte="Voici une explication.", input_tokens=15, output_tokens=25):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=texte)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class AssistantIAServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.eleve = Eleve.objects.get(matricule="202600001")
        cls.conversation = Conversation.objects.create(eleve=cls.eleve)

    def test_without_api_key_returns_graceful_fallback(self):
        with override_settings(ANTHROPIC_API_KEY=""):
            reponse = envoyer_message(self.conversation, "Peux-tu m'expliquer les fractions ?")
        self.assertEqual(reponse.role, MessageConversation.Role.ASSISTANT)
        self.assertEqual(reponse.contenu, MESSAGE_NON_CONFIGURE)
        self.assertEqual(reponse.tokens_utilises, 0)

    def test_user_message_is_always_recorded_even_without_api_key(self):
        with override_settings(ANTHROPIC_API_KEY=""):
            envoyer_message(self.conversation, "Une question")
        self.assertTrue(
            self.conversation.messages.filter(role=MessageConversation.Role.UTILISATEUR, contenu="Une question").exists()
        )

    @override_settings(ANTHROPIC_API_KEY="fake-key-for-tests")
    @patch("assistant_ia.services._client")
    def test_successful_call_consumes_budget_and_saves_response(self, mock_client_factory):
        mock_client = mock_client_factory.return_value
        mock_client.messages.create.return_value = _fake_response("Les fractions représentent une partie d'un tout.")

        reponse = envoyer_message(self.conversation, "Explique les fractions")

        self.assertEqual(reponse.role, MessageConversation.Role.ASSISTANT)
        self.assertEqual(reponse.contenu, "Les fractions représentent une partie d'un tout.")
        self.assertEqual(reponse.tokens_utilises, 40)

        budget = BudgetIA.objects.get(etablissement=self.eleve.user.etablissement)
        self.assertEqual(budget.tokens_utilises, 40)

    @override_settings(ANTHROPIC_API_KEY="fake-key-for-tests")
    @patch("assistant_ia.services._client")
    def test_exhausted_budget_blocks_further_calls(self, mock_client_factory):
        etablissement = self.eleve.user.etablissement
        BudgetIA.objects.update_or_create(
            etablissement=etablissement, defaults={"plafond_mensuel_tokens": 10, "tokens_utilises": 10},
        )
        reponse = envoyer_message(self.conversation, "Une autre question")
        self.assertEqual(reponse.contenu, MESSAGE_BUDGET_EPUISE)
        mock_client_factory.return_value.messages.create.assert_not_called()

    @override_settings(ANTHROPIC_API_KEY="fake-key-for-tests")
    @patch("assistant_ia.services._client")
    def test_api_error_is_handled_gracefully(self, mock_client_factory):
        mock_client_factory.return_value.messages.create.side_effect = RuntimeError("boom")
        reponse = envoyer_message(self.conversation, "Question")
        self.assertEqual(reponse.role, MessageConversation.Role.ASSISTANT)
        self.assertIn("erreur", reponse.contenu.lower())

    @override_settings(ANTHROPIC_API_KEY="fake-key-for-tests")
    @patch("assistant_ia.services._client")
    def test_generer_fiche_revision_includes_cahier_de_texte_content(self, mock_client_factory):
        mock_client = mock_client_factory.return_value
        mock_client.messages.create.return_value = _fake_response("Fiche de révision : ...")

        generer_fiche_revision(self.conversation, "Mathématiques")

        appel = mock_client.messages.create.call_args
        dernier_message_utilisateur = appel.kwargs["messages"][-1]["content"]
        self.assertIn("Mathématiques", dernier_message_utilisateur)


class AssistantIAViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def _login(self, username):
        self.assertTrue(self.client.login(username=username, password=DEMO_PASSWORD))

    def test_non_eleve_cannot_access_assistant(self):
        self._login("prof.mathématiques")
        response = self.client.get("/assistant-ia/")
        self.assertEqual(response.status_code, 403)

    def test_eleve_can_create_and_view_conversation(self):
        self._login("eleve.202600001")
        response = self.client.post("/assistant-ia/nouvelle/")
        conversation = Conversation.objects.get(eleve__matricule="202600001")
        self.assertRedirects(response, f"/assistant-ia/{conversation.pk}/")

    def test_eleve_cannot_view_another_eleves_conversation(self):
        autre_eleve = Eleve.objects.get(matricule="202600002")
        conversation = Conversation.objects.create(eleve=autre_eleve)

        self._login("eleve.202600001")
        response = self.client.get(f"/assistant-ia/{conversation.pk}/")
        self.assertEqual(response.status_code, 404)

    @override_settings(ANTHROPIC_API_KEY="")
    def test_posting_a_message_without_api_key_shows_fallback(self):
        self._login("eleve.202600001")
        eleve = Eleve.objects.get(matricule="202600001")
        conversation = Conversation.objects.create(eleve=eleve)

        response = self.client.post(f"/assistant-ia/{conversation.pk}/", {"message": "Bonjour"})
        self.assertRedirects(response, f"/assistant-ia/{conversation.pk}/")
        self.assertTrue(conversation.messages.filter(contenu=MESSAGE_NON_CONFIGURE).exists())
