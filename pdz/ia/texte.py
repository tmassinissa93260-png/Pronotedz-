"""Le point d'entrée unique pour parler à un modèle de texte.

Même principe que le registre : un agent demande une capacité (« qualite »),
jamais un fournisseur. Ce module regarde de quel fournisseur relève le
modèle **résolu** pour cet alias, et choisit l'adaptateur qui sait lui
parler — Anthropic aujourd'hui, Groq si le profil `gratuit` est actif,
un troisième demain sans qu'aucun agent n'ait à changer une ligne.

`pdz.agents.base.Agent` appelle `texte.appeler()`, jamais `claude.appeler()`
ou `groq.appeler()` directement — c'est ce détour qui rend le choix du
fournisseur pilotable depuis `modeles.yaml` seul.
"""

from __future__ import annotations

from typing import Any

from pdz.ia import claude, groq
from pdz.ia.registre import registre
from pdz.moteur.erreurs import ErreurConfig

# Un adaptateur par fournisseur de texte. Ajouter un fournisseur = ajouter
# une ligne ici et écrire le module — jamais toucher aux agents.
ADAPTATEURS = {
    "anthropic": claude.appeler,
    "groq": groq.appeler,
}


async def appeler(
    *,
    alias: str,
    profil: str = "equilibre",
    budget_restant_pct: float = 100.0,
    images: list | None = None,
    **kwargs: Any,
):
    """Résout l'alias, puis délègue au bon fournisseur.

    La résolution est refaite ici et à nouveau dans l'adaptateur choisi :
    c'est une simple lecture de dictionnaire, sans coût, et ça évite de
    faire porter à chaque adaptateur la connaissance des autres.
    """
    # Les images décident du fournisseur autant que l'alias : un agent qui en
    # envoie a besoin d'un modèle qui sache les lire, même si le profil
    # désigne autre chose. La résolution est refaite à l'identique dans
    # l'adaptateur choisi, qui reçoit les mêmes paramètres.
    modele = registre().resoudre(
        alias, profil=profil, budget_restant_pct=budget_restant_pct,
        repli_si_cle_absente=True,
        capacite_requise="vision" if images else None,
    ).modele

    adaptateur = ADAPTATEURS.get(modele.fournisseur)
    if adaptateur is None:
        raise ErreurConfig(
            f"« {modele.id} » (fournisseur « {modele.fournisseur} ») ne sait "
            f"pas écrire de texte. Fournisseurs de texte connus : "
            f"{', '.join(sorted(ADAPTATEURS))}. Vérifie l'alias « {alias} » "
            "dans modeles.yaml."
        )

    return await adaptateur(
        alias=alias, profil=profil, budget_restant_pct=budget_restant_pct,
        images=images, **kwargs,
    )
