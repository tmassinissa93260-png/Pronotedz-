"""Ce qui décide de la dépense et de la ressemblance.

Rien ici n'appelle un fournisseur : on teste les décisions prises AVANT
l'appel — combien de plans on peut payer, quel prompt part, quelle voix est
retenue. Ce sont ces décisions qui coûtent de l'argent, pas le transport HTTP.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from pdz.agents.analyse.charte import (
    CharteVisuelle,
    _graine,
    _identifiant,
    _nettoyer_rendu,
    vers_univers,
)
from pdz.analyse.visuel import AnalyseVisuelle, Couleur
from pdz.analyse.voix import ProfilVoix
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.production import animation, images
from pdz.production.appariement_voix import POIDS_HAUTEUR_SEULE, Candidat, profil_suppose
from pdz.univers import Univers

FRUITS = Path(__file__).resolve().parent.parent / "univers" / "fruit-island.yaml"


def _contexte():
    return Contexte(job_id="job_test", etape_cle="test", profil="equilibre",
                    budget_restant=1.0)


def _visuel(palette=("#FF4D6D", "#118AB2", "#FFD166")):
    return AnalyseVisuelle(
        images_cles=[], palette=[Couleur(h, 0.3, 10.0, 0.8, 0.7) for h in palette],
        luminosite=0.5, contraste=0.25, saturation=0.6, temperature=0.15,
        nettete=0.6, grain=0.05, cadrage_x=0.5, cadrage_y=0.5,
        echelle_sujet=0.4, densite_mouvement=0.3, confiance=0.85,
    )


def _charte(nb=2):
    return {
        "rendu": "flat 2D vector animation, thick black outlines, no gradients",
        "eclairage": "even front lighting",
        "ambiance": "comédie de bureau",
        "personnages": [
            {
                "id": f"perso{i}", "nom": f"Perso {i}", "espece": "agrafeuse",
                "apparence": ("a chunky red desktop stapler with two round googly "
                              "eyes glued on its hinge, chipped chrome jaw, small "
                              "paper clip arms, wobbling on a wooden desk"),
                "caractere": "autoritaire", "images": [1, 2],
                "voix_percue": {"registre": "grave", "ton": "posé et las"},
            }
            for i in range(nb)
        ],
        "decors": [{"id": "bureau", "nom": "Le bureau",
                    "description": "grey open space office, fluorescent ceiling lights"}],
        "regles_du_monde": ["Les objets de bureau parlent", "Personne ne sort jamais"],
        "transposition": [{"personnage": "Perso 0", "garde": "l'archétype",
                           "change": "l'espèce"}],
        "incertitudes": [],
    }


# ── De la charte à l'univers ─────────────────────────────────────────────

def test_la_palette_de_lunivers_vient_des_mesures_pas_du_modele():
    """Le modèle nomme mal les couleurs ; l'histogramme non.

    C'est la règle de partage du module : mesuré d'un côté, interprété de
    l'autre, jamais mélangés.
    """
    visuel = _visuel()
    u = vers_univers(_charte(), visuel, identifiant="test", nom="Test")
    assert u.style.palette == visuel.palette_hex[:5]


def test_la_graine_est_stable_dune_execution_a_lautre():
    """`hash()` est salé à chaque lancement : deux runs, deux styles."""
    assert _graine("fruit-island") == _graine("fruit-island")
    assert _graine("fruit-island") != _graine("garage-42")


def test_une_reference_a_une_oeuvre_est_retiree_du_rendu():
    nettoye = _nettoyer_rendu("cel-shaded anime, in the style of Studio Ghibli")
    assert "ghibli" not in nettoye.lower()
    assert "cel-shaded" in nettoye


def test_lunivers_produit_passe_le_validateur_de_style():
    """Le validateur refuserait un nom d'œuvre : la charte ne doit pas en produire."""
    u = vers_univers(_charte(), _visuel(), identifiant="test", nom="Test")
    assert u.style.rendu


def test_les_identifiants_sont_utilisables_comme_noms_de_fichiers():
    assert _identifiant("Éric l'Agrafeuse !") == "eric_l_agrafeuse"
    assert _identifiant("  ") == "sans_nom"


def test_les_personnages_arrivent_sans_voix_mais_avec_des_reglages():
    """La voix se choisit en mesurant, pas en devinant — mais le ton perçu
    donne déjà les réglages de jeu."""
    u = vers_univers(_charte(), _visuel(), identifiant="t", nom="T")
    perso = u.personnages[0]
    assert perso.voix.voice_id == ""
    assert perso.voix.stabilite > 0.6      # « posé et las »


# ── Les vérifications de la charte ───────────────────────────────────────

def test_une_charte_sans_personnage_est_refusee():
    charte = _charte()
    charte["personnages"] = []
    with pytest.raises(ErreurValidation) as e:
        CharteVisuelle().apres(charte, {"visuel": _visuel()}, _contexte())
    assert "personnage" in str(e.value).lower()


def test_deux_personnages_ne_peuvent_pas_partager_un_identifiant():
    """Sinon ils partagent silencieusement voix et fiche image."""
    charte = _charte(2)
    charte["personnages"][1]["id"] = charte["personnages"][0]["id"]
    with pytest.raises(ErreurValidation) as e:
        CharteVisuelle().apres(charte, {"visuel": _visuel()}, _contexte())
    assert "deux fois" in str(e.value)


def test_une_apparence_trop_vague_est_refusee():
    """« a red stapler » ne permet pas de redessiner le personnage."""
    charte = _charte(1)
    charte["personnages"][0]["apparence"] = "a red stapler"
    with pytest.raises(ErreurValidation) as e:
        CharteVisuelle().apres(charte, {"visuel": _visuel()}, _contexte())
    assert "vague" in str(e.value)


def test_le_mode_transposition_exige_de_dire_ce_qui_change():
    charte = _charte(1)
    charte["transposition"] = []
    with pytest.raises(ErreurValidation):
        CharteVisuelle().apres(charte, {"visuel": _visuel(), "transposer": True},
                               _contexte())


# ── Prompts d'images ─────────────────────────────────────────────────────

def test_le_personnage_passe_avant_le_style_dans_le_prompt():
    """Les modèles d'image pondèrent le début du prompt. Inversé, on obtient
    de très belles images du mauvais personnage."""
    u = Univers.charger(FRUITS)
    perso = u.personnages[0]
    prompt = images.prompt_plan(perso, u, action="elle claque la porte",
                                emotion="colere")
    assert prompt.index(perso.apparence.split()[0]) < prompt.index(u.style.rendu[:12])


def test_lemotion_devient_une_description_de_visage():
    """« angry » donne un visage contrarié ; les sourcils donnent la colère."""
    u = Univers.charger(FRUITS)
    prompt = images.prompt_plan(u.personnages[0], u, action="x", emotion="colere")
    assert "eyebrow" in prompt
    assert "colere" not in prompt          # rien de français ne part au modèle


def test_le_decor_demande_est_celui_utilise():
    u = Univers.charger(FRUITS)
    prompt = images.prompt_plan(u.personnages[0], u, action="x", decor="ceremonie")
    assert "torches" in prompt


def test_la_fiche_de_personnage_est_neutre():
    """Une fiche prise en scène transmettrait ce décor à tous les plans."""
    u = Univers.charger(FRUITS)
    fiche = images.prompt_fiche(u.personnages[0], u)
    assert "plain flat" in fiche and "neutral" in fiche
    assert "villa" not in fiche


def test_regenerer_une_fiche_invalide_les_plans_du_personnage(tmp_path):
    """Sinon deux versions du même personnage cohabitent dans un épisode."""
    fiche = tmp_path / "fiche.jpg"
    fiche.write_bytes(b"version-1")
    avant = images._empreinte("un prompt", 42, fiche)
    fiche.write_bytes(b"version-2")
    apres = images._empreinte("un prompt", 42, fiche)
    assert avant != apres


def test_deux_prompts_identiques_partagent_la_meme_empreinte(tmp_path):
    assert images._empreinte("p", 1, None) == images._empreinte("p", 1, None)
    assert images._empreinte("p", 1, None) != images._empreinte("p", 2, None)


# ── Budget d'animation ───────────────────────────────────────────────────

def test_le_budget_prime_sur_le_chiffre_annonce_par_le_profil():
    """Un profil qui promet 6 animations sans regarder la caisse produit une
    facture surprise. Ici le nombre réel est calculé."""
    combien, raison = animation.combien_animer(20, budget_restant=0.10,
                                               profil="equilibre")
    assert combien < 6
    assert "budget" in raison


def test_un_budget_confortable_laisse_le_profil_decider():
    combien, raison = animation.combien_animer(20, budget_restant=100.0,
                                               profil="equilibre")
    assert combien == 6
    assert "profil" in raison


def test_le_profil_economique_nanime_rien():
    combien, raison = animation.combien_animer(20, budget_restant=100.0,
                                               profil="economique")
    assert combien == 0
    assert "désactivée" in raison


def test_on_nanime_jamais_plus_de_plans_quil_nen_existe():
    combien, _ = animation.combien_animer(2, budget_restant=100.0, profil="premium")
    assert combien == 2


# ── Narration : personne à l'écran ───────────────────────────────────────

HOLO = Path(__file__).resolve().parent.parent / "univers" / "techno-holo.yaml"


def test_en_narration_le_prompt_part_de_la_scene_pas_du_narrateur():
    """Une voix off ne se voit pas. Mettre son apparence en tête du prompt
    donnerait vingt portraits du même sujet là où il faut vingt scènes."""
    u = Univers.charger(HOLO)
    assert not u.anime
    prompt = images.prompt_plan(u.personnages[0], u,
                                action="a glowing wireframe city at night",
                                emotion="colere", decor="ville")
    assert prompt.startswith("a glowing wireframe city at night")
    assert u.personnages[0].apparence.split(",")[0] not in prompt
    # Aucune émotion : un visage qu'on ne voit pas n'a rien à jouer.
    assert "expression" not in prompt


def test_en_serie_animee_le_personnage_reste_en_tete():
    """Non-régression : c'est ce qui garde le personnage reconnaissable."""
    u = Univers.charger(FRUITS)
    perso = u.personnages[0]
    prompt = images.prompt_plan(perso, u, action="se retourne", emotion="colere")
    assert prompt.startswith(perso.apparence.split(",")[0])
    assert "expression" in prompt


def _prompts_de_scenes(u):
    return [images.prompt_plan(u.personnages[0], u, action=a, decor=d)
            for a, d in [("a wireframe city", "ville"),
                         ("a network of nodes", "reseau"),
                         ("a rotating object", "objet")]]


def test_en_narration_la_graine_varie_dun_plan_a_lautre():
    """Mesuré à l'écran : une graine fixe appliquée à vingt scènes
    différentes rendait la même ville filaire pendant tout l'épisode."""
    u = Univers.charger(HOLO)
    graines = {images.graine_du_plan(u, p) for p in _prompts_de_scenes(u)}
    assert len(graines) == 3, "chaque scène doit avoir sa propre graine"


def test_en_serie_animee_la_graine_reste_fixe():
    """Non-régression : c'est l'un des mécanismes qui gardent la patte
    graphique constante d'un plan à l'autre."""
    u = Univers.charger(FRUITS)
    graines = {
        images.graine_du_plan(u, images.prompt_plan(u.personnages[0], u, action=a))
        for a in ("se retourne", "crie", "sourit")
    }
    assert graines == {u.style.seed}


def test_la_graine_dun_plan_est_reproductible():
    """Sinon le cache ne servirait plus à rien : chaque reprise repaierait
    toutes les images."""
    u = Univers.charger(HOLO)
    prompt = _prompts_de_scenes(u)[0]
    assert images.graine_du_plan(u, prompt) == images.graine_du_plan(u, prompt)


def test_sans_graine_declaree_rien_nest_invente():
    u = Univers.charger(HOLO)
    u.style.seed = None
    assert images.graine_du_plan(u, "peu importe") is None


def test_la_narration_ne_produit_aucune_fiche(tmp_path):
    """La fiche servirait d'image de départ à chaque plan et rendrait toutes
    les scènes identiques — l'inverse du but recherché."""
    u = Univers.charger(HOLO)
    assert images.fiches(u, tmp_path) == {}


def test_un_echec_total_danimation_est_crie_pas_chuchote(monkeypatch, caplog,
                                                         tmp_path):
    """Une animation ratée est rattrapée en image fixe pour ne pas perdre
    l'épisode — au prix d'un silence qui a laissé passer un identifiant de
    modèle périmé pendant plusieurs productions. Un échec TOTAL doit sortir
    en ERROR, visible sans lire les journaux ligne à ligne."""
    from pdz.moteur.erreurs import ErreurValidation

    def _toujours_en_echec(*a, **k):
        raise ErreurValidation("endpoint introuvable")

    monkeypatch.setattr(animation.fal, "animer_image", _toujours_en_echec)

    u = Univers.charger(FRUITS)
    images = []
    for i in range(3):
        p = tmp_path / f"p{i}.jpg"
        Image.new("RGB", (64, 64), (10 * i, 60, 90)).save(p)
        images.append(p)
    plans = [{"numero": i, "personnage": u.personnages[0].id, "action": "parle",
              "emotion": "calme", "duree_s": 2.0} for i in range(3)]

    with caplog.at_level(logging.ERROR):
        resultats = animation.animer(
            plans, images, u, tmp_path / "anim", budget_restant=100.0,
            profil="equilibre", vie_pour_le_reste=False,
        )

    assert not any(r.anime for r in resultats), "aucune animation ne devait réussir"
    assert any(e.levelno >= logging.ERROR for e in caplog.records), \
        "un échec total d'animation doit remonter en ERROR"
    assert "AUCUN plan animé" in caplog.text


def test_lepisode_annonce_combien_de_plans_sont_animes():
    """« aucune animation » dans le résumé est une information : son absence
    a longtemps caché que rien n'était animé."""
    from pdz.production.episode import Episode

    muet = Episode(job_id="j", titre="T", video=Path("v.mp4"), duree_s=20.0,
                   cout=0.1, plans_animes=0)
    assert "aucune animation" in muet.resume()

    anime = Episode(job_id="j", titre="T", video=Path("v.mp4"), duree_s=20.0,
                    cout=0.5, plans_animes=2)
    assert "2 plan(s) animé(s)" in anime.resume()


def test_le_prompt_de_mouvement_reste_court_et_protege_le_personnage():
    """Un prompt long fait refabriquer la scène au lieu de l'animer."""
    u = Univers.charger(FRUITS)
    prompt = animation._prompt_mouvement(
        {"emotion": "colere", "action": "elle jette un verre"}, u
    )
    assert len(prompt.split()) < 45
    assert "identical" in prompt


# ── Appariement de voix ──────────────────────────────────────────────────

def _profil(hauteur, debit=5.0, etendue=6.0, timbre=1500.0):
    return ProfilVoix(
        hauteur_hz=hauteur, hauteur_p10=hauteur * 0.9, hauteur_p90=hauteur * 1.1,
        etendue_demi_tons=etendue, stabilite_hz=1.0, timbre_hz=timbre,
        debit_syllabes_s=debit, ratio_parole=0.8, dynamique_db=6.0,
        voisement=0.4, duree_s=10.0, confiance=1.0,
    )


class _VoixFactice:
    def __init__(self, id_, nom):
        self.id, self.nom, self.langue, self.genre, self.usage = id_, nom, "fr", "", ""


def test_la_vitesse_corrige_lecart_pas_la_cible():
    """Reprendre la vitesse de la cible corrigerait une erreur inexistante.

    Ce qu'il faut, c'est de combien la voix retenue parle trop vite ou trop
    lentement — donc un rapport entre les deux mesures.
    """
    candidat = Candidat(
        voix=_VoixFactice("v1", "Voix"),
        profil=_profil(140, debit=4.0),     # la candidate parle lentement
        cible=_profil(140, debit=6.0),      # la cible parle vite
        distance=0.1, fichier=Path("x.mp3"),
    )
    assert candidat.reglages()["vitesse"] > 1.0


def test_le_jeu_vient_de_la_cible_pas_de_la_candidate():
    expressive = Candidat(
        voix=_VoixFactice("v", "V"), profil=_profil(140, etendue=3.0),
        cible=_profil(140, etendue=14.0), distance=0.1, fichier=Path("x.mp3"),
    )
    assert expressive.reglages()["style"] > 0.6


def test_la_vitesse_reste_dans_ce_que_le_moteur_encaisse():
    extreme = Candidat(
        voix=_VoixFactice("v", "V"), profil=_profil(140, debit=1.0),
        cible=_profil(140, debit=9.0), distance=0.1, fichier=Path("x.mp3"),
    )
    assert extreme.reglages()["vitesse"] <= 1.25


def test_sans_audio_de_reference_seule_la_hauteur_compte():
    """Un profil supposé a une confiance nulle : ses autres axes sont du
    remplissage, les pondérer reviendrait à choisir sur une invention."""
    suppose = profil_suppose(120.0)
    assert suppose.confiance == 0.0

    proche = _profil(122.0, timbre=3000.0, etendue=15.0)
    loin = _profil(230.0, timbre=1500.0, etendue=6.0)

    def d(autre):
        ecart = np.abs(suppose.vecteur() - autre.vecteur())
        return float(np.sqrt(((ecart * POIDS_HAUTEUR_SEULE) ** 2).sum()))

    assert d(proche) < d(loin)


# ── Choisir une voix sans audio de référence ─────────────────────────────

def test_le_registre_inscrit_dans_lunivers_est_suivi():
    from pdz.production.appariement_voix import hauteur_attendue
    from pdz.univers import Personnage, Voix

    grave = Personnage(id="a", nom="A", espece="x", apparence="y",
                       voix=Voix(registre_percu="grave"))
    aigu = Personnage(id="b", nom="B", espece="x", apparence="y",
                      voix=Voix(registre_percu="aigu"))
    assert hauteur_attendue(grave, 0, 2) < hauteur_attendue(aigu, 1, 2)


def test_sans_registre_les_personnages_sont_etales():
    """Sinon tous visent la même hauteur, reçoivent des voix voisines, et le
    dialogue devient impossible à suivre."""
    from pdz.production.appariement_voix import hauteur_attendue
    from pdz.univers import Personnage

    persos = [Personnage(id=f"p{i}", nom=f"P{i}", espece="x", apparence="y")
              for i in range(4)]
    hauteurs = [hauteur_attendue(p, i, len(persos)) for i, p in enumerate(persos)]
    assert len(set(hauteurs)) == len(hauteurs)
    assert min(hauteurs) >= 110 and max(hauteurs) <= 255
