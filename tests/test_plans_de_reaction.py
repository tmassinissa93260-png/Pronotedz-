"""Les plans de réaction : distincts du plan parlant, du storyboard au montage.

Ce fichier vérifie l'invariant central de ce soir : une réplique donne 1 ou 2
plans, ce nombre ne bouge plus une fois décidé, et un plan de réaction montre
l'écouteur — pas le parlant — en réagissant à ce qui vient d'être dit.

Tout ici est déterministe : aucun test ne dépend d'un appel réel à un modèle
de langage. Ce que le modèle écrit en texte libre (ShotPromptWriter) est
non-reproductible par nature ; ce que le CODE garantit — quel personnage est
inséré dans le prompt, la description de repli avant enrichissement, la
consigne donnée au modèle — l'est.
"""

from __future__ import annotations

from pathlib import Path

from pdz.production import animation, images, storyboard
from pdz.prompts import charger
from pdz.univers import Univers
from tests.test_chaine_complete import _produire, atelier  # noqa: F401 — fixture réutilisée

FRUITS = Path(__file__).resolve().parent.parent / "univers" / "fruit-island.yaml"


def _repliques(n=4, avec_reaction=True):
    u = Univers.charger(FRUITS)
    a, b = u.personnages[0].id, u.personnages[1].id
    return u, [
        {"numero": i + 1, "personnage": a if i % 2 == 0 else b,
         "replique": "une phrase", "action": "il parle", "emotion": "colere",
         "reaction_de": (b if i % 2 == 0 else a) if avec_reaction else ""}
        for i in range(n)
    ]


# ── 1. Une réplique donne 1 ou 2 plans ──────────────────────────────────

def test_une_replique_peut_produire_un_ou_deux_plans():
    u, repliques = _repliques(1, avec_reaction=False)
    sans_reaction = storyboard.decouper(repliques, [4.0], u)
    assert len(sans_reaction) == 1

    u, repliques = _repliques(1, avec_reaction=True)
    avec_reaction = storyboard.decouper(repliques, [4.0], u)
    assert len(avec_reaction) == 2
    assert sum(1 for p in avec_reaction if p.reaction) == 1


# ── 2. Le nombre de plans ne bouge plus, du découpage au montage ───────

def test_le_nombre_de_plans_reste_identique_du_storyboard_aux_images(atelier):
    """storyboard → images → montage : le nombre de plans ne doit jamais
    varier d'une étape à l'autre. Un plan perdu en route casse le montage
    bien plus tard, sur une erreur ffmpeg incompréhensible — ce test le
    détecte tout de suite, à la source."""
    tmp_path, appels = atelier
    _, resultat = _produire(atelier)
    nb_plans = len(resultat.plans)
    assert nb_plans >= 4   # SCRIPT_FACTICE a deux répliques avec réaction

    # Images : une par plan, plus les 3 fiches de personnages.
    assert appels["images"] == 3 + nb_plans

    # Montage : le fichier existe — la preuve que le zip strict côté
    # animation/montage (`zip(plans, animes, strict=True)`) n'a pas levé.
    assert resultat.video.exists()


def test_le_nombre_de_plans_reste_identique_a_lanimation(tmp_path):
    """Vérifié séparément, en direct sur `animation.animer()` : une entrée
    PlanAnime par plan, animé ou non — c'est cette garantie qui permet au
    montage de zipper plans/animes sans jamais perdre un plan en route."""
    u, repliques = _repliques(3, avec_reaction=True)
    plans = storyboard.decouper(repliques, [4.0, 4.0, 4.0], u)

    fichiers = []
    for p in plans:
        f = tmp_path / f"plan_{p.numero:03d}.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0")  # jamais ouvert par animer() lui-même
        fichiers.append(f)

    animes = animation.animer(
        [p.en_dict() for p in plans], fichiers, u, tmp_path / "anim",
        budget_restant=0.0, profil="economique", vie_pour_le_reste=False,
    )
    assert len(animes) == len(plans)


# ── 3. Un plan de réaction n'emprunte jamais l'identité du parlant ─────

def test_reaction_interdit_la_presence_du_personnage_parlant_dans_le_prompt():
    u, repliques = _repliques(1, avec_reaction=True)
    parlant_id = repliques[0]["personnage"]
    parlant = u.personnage(parlant_id)

    plans = storyboard.decouper(repliques, [4.0], u)
    reaction = next(p for p in plans if p.reaction)

    # Le plan de réaction est construit sur le personnage qui ÉCOUTE...
    assert reaction.personnage != parlant_id

    # ...donc le prompt final ne doit jamais contenir la description
    # physique de celui qui parle : on SAIT qui parle et qui écoute, rien
    # ne justifie que cette information se glisse dans l'image du plan de
    # réaction.
    perso_reaction = u.personnage(reaction.personnage)
    prompt = images.prompt_plan(
        perso_reaction, u, action=reaction.action, emotion=reaction.emotion,
        decor=reaction.decor, fonction=reaction.fonction,
    )
    assert parlant.apparence.strip() not in prompt


# ── 4. Le plan de réaction décrit l'effet de la réplique sur l'écouteur ─

def test_le_prompt_de_reaction_decrit_leffet_de_la_replique_sur_lecouteur():
    u, repliques = _repliques(1, avec_reaction=True)
    parlant = u.personnage(repliques[0]["personnage"])

    plans = storyboard.decouper(repliques, [4.0], u)
    reaction = next(p for p in plans if p.reaction)

    # L'action de repli (avant tout enrichissement par ShotPromptWriter, ou
    # si son prompt manque pour ce plan) doit déjà cadrer l'EFFET de la
    # réplique sur celui qui écoute — jamais une description neutre sans
    # lien avec ce qui vient d'être dit.
    assert "just said" in reaction.action
    assert parlant.nom in reaction.action


def test_le_prompt_actif_instruit_de_montrer_leffet_sur_lecouteur():
    """Le modèle qui écrit le VRAI prompt (ShotPromptWriter) doit recevoir
    cette même consigne — sinon la garantie du dessus ne vaut que pour le
    texte de repli, jamais pour ce que le modèle écrit réellement."""
    prompt = charger("ecriture/plans")
    texte = prompt.systeme_stable.lower()
    assert "reaction" in texte or "réaction" in texte
    assert "écoute" in texte


# ── 5. Personne, en aval, ne redécoupe les plans ────────────────────────

def test_aucune_etape_ulterieure_ne_redecoupe_les_plans(atelier, monkeypatch):
    """Le découpage doit se faire une seule fois par production : le
    refaire plus loin (images, animation, montage) donnerait un jour un
    nombre de plans différent de celui déjà utilisé par les étapes
    précédentes, sans qu'aucune erreur ne le signale avant le montage."""
    appels = {"n": 0}
    original = storyboard.decouper

    def compte(*args, **kwargs):
        appels["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr("pdz.production.episode.storyboard.decouper", compte)

    _, resultat = _produire(atelier)

    assert appels["n"] == 1
    assert resultat.video.exists()
