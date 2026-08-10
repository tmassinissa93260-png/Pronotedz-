"""Le point d'entrée unique pour générer une image.

Même principe que `pdz.ia.texte` côté écriture : un agent d'image demande une
capacité (« images »), jamais un fournisseur. Ce module regarde de quel
fournisseur relève le modèle **résolu** pour cet alias, et choisit
l'adaptateur qui sait lui parler — fal.ai par défaut, Pollinations si le
profil `gratuit` est actif, un troisième demain sans qu'aucun agent n'ait à
changer une ligne.

`pdz.production.images` appelle `images.generer_image()`, jamais
`fal.generer_image()` ou `pollinations.generer_image()` directement — c'est
ce détour qui rend le choix du fournisseur pilotable depuis `modeles.yaml`
seul.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pdz.ia import fal, pollinations
from pdz.ia.registre import registre
from pdz.moteur.erreurs import ErreurConfig

# Un adaptateur par fournisseur d'images. Ajouter un fournisseur = ajouter
# une ligne ici et écrire le module — jamais toucher aux agents.
ADAPTATEURS = {
    "fal": fal.generer_image,
    "pollinations": pollinations.generer_image,
}


def generer_image(
    prompt: str, destination: Path, *,
    alias: str = "images",
    profil: str = "equilibre",
    budget_restant_pct: float = 100.0,
    **kwargs: Any,
) -> tuple[Path, float]:
    """Résout l'alias, puis délègue au bon fournisseur.

    La résolution est refaite ici et à nouveau dans l'adaptateur choisi :
    c'est une simple lecture de dictionnaire, sans coût, et ça évite de
    faire porter à chaque adaptateur la connaissance des autres.
    """
    modele = registre().resoudre(
        alias, profil=profil, budget_restant_pct=budget_restant_pct,
        repli_si_cle_absente=True,
    ).modele

    adaptateur = ADAPTATEURS.get(modele.fournisseur)
    if adaptateur is None:
        raise ErreurConfig(
            f"« {modele.id} » (fournisseur « {modele.fournisseur} ») ne sait "
            f"pas générer d'image. Fournisseurs d'images connus : "
            f"{', '.join(sorted(ADAPTATEURS))}. Vérifie l'alias « {alias} » "
            "dans modeles.yaml."
        )

    return adaptateur(
        prompt, destination, alias=alias, profil=profil,
        budget_restant_pct=budget_restant_pct, **kwargs,
    )
