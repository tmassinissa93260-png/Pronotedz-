"""De la mesure à la production : ADN, découpage en plans, notation.

Ces trois modules sont ceux qui font des divisions plutôt que des appels
payants. Une division fausse coûte moins cher qu'un appel raté, mais elle se
voit à l'écran — un débit mal calculé donne un épisode 30 % trop long.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pdz.analyse.adn import Adn, _pics, extraire
from pdz.analyse.coupes import Decoupage
from pdz.analyse.son import AnalyseSon
from pdz.production import animation, storyboard
from pdz.univers import Univers
from pdz.video.soustitres import Mot

FRUITS = Path(__file__).resolve().parent.parent / "univers" / "fruit-island.yaml"


def _decoupage(durees, duree_totale=None):
    total = duree_totale or sum(durees)
    coupes, curseur = [], 0.0
    for d in durees[:-1]:
        curseur += d
        coupes.append(curseur)
    return Decoupage(seuil=0.16, coupes=coupes, durees=list(durees),
                     duree_totale=total, confiance=0.9)


def _son(courbe=None, silence=0.2):
    courbe = courbe or [0.5] * 40
    return AnalyseSon(duree_s=45.0, courbe_energie=courbe, fenetre_ms=25,
                      silences=[(0.0, 45.0 * silence)], lufs_estime=-14.0,
                      tempo_bpm=120.0, confiance_tempo=0.8)


def _adn(**surcharges) -> Adn:
    base = dict(
        duree_s=45.0, duree_plan_s=1.75, coupes_par_minute=34.0,
        duree_premier_plan_s=2.0, plans_par_replique=2.0,
        debit_wpm=170, ratio_parole=0.8, relances_pct=[0.35, 0.7],
        courbe_energie=[0.5] * 12, palette=["#112233"], consignes_image=[],
        confiance={"decoupage": 0.9},
    )
    return Adn(**{**base, **surcharges})


# ── Arithmétique de l'ADN ────────────────────────────────────────────────

def test_le_nombre_de_repliques_suit_le_rythme_de_la_reference():
    """Plans courts → plus de répliques dans la même durée."""
    rapide = _adn(duree_plan_s=1.2).nb_repliques(45)
    lent = _adn(duree_plan_s=3.0).nb_repliques(45)
    assert rapide > lent


def test_les_mots_par_replique_decoulent_du_debit_mesure():
    lent = _adn(debit_wpm=120).mots_par_replique(45)
    rapide = _adn(debit_wpm=220).mots_par_replique(45)
    assert sum(rapide) > sum(lent)
    # Le total doit rester cohérent avec la durée visée, à 15 % près.
    for adn_wpm, mots in ((120, lent), (220, rapide)):
        duree_parlee = sum(mots) / adn_wpm * 60
        assert abs(duree_parlee - 45) < 45 * 0.15, (adn_wpm, duree_parlee)


def test_les_contraintes_sont_recalculees_pour_la_duree_visee():
    """L'ADN d'une vidéo de 20 s doit savoir décrire un épisode de 60 s."""
    adn = _adn(duree_s=20.0)
    court, long = adn.contraintes(20), adn.contraintes(60)
    assert long["nb_repliques"] > court["nb_repliques"]
    assert long["duree_plan_s"] == court["duree_plan_s"]   # le rythme, lui, ne change pas


def test_les_relances_tombent_aux_positions_mesurees():
    adn = _adn(relances_pct=[0.25, 0.75])
    numeros = adn.repliques_de_relance(45)
    n = adn.nb_repliques(45)
    assert all(1 < x <= n for x in numeros)
    assert len(set(numeros)) == len(numeros)      # pas de doublon


def test_une_reference_au_montage_extreme_est_bornee():
    """0,3 s par plan donnerait 150 images pour 45 secondes : intenable.

    Les bornes ne sont pas de la prudence gratuite : sans elles, une seule
    vidéo de référence mal découpée fait exploser le coût d'un épisode.
    """
    adn = extraire(_decoupage([0.3] * 100, 30.0), _son())
    assert adn.duree_plan_s >= 0.8


def test_lardn_se_recharge_a_lidentique():
    adn = _adn()
    copie = Adn.depuis_dict(adn.en_dict())
    assert copie.contraintes(45) == adn.contraintes(45)


# ── Honnêteté ────────────────────────────────────────────────────────────

def test_les_limites_sont_toujours_presentes():
    """Un rapport chiffré sans ses limites laisse croire qu'il explique."""
    limites = _adn().limites()
    assert len(limites) >= 3
    assert any("percé" in x or "réussite" in x for x in limites)


def test_une_mesure_peu_fiable_est_signalee_dans_les_limites():
    limites = _adn(confiance={"decoupage": 0.3}).limites()
    assert any("decoupage" in x for x in limites)


def test_sans_voix_le_debit_est_une_norme_et_la_confiance_le_dit():
    adn = extraire(_decoupage([1.5] * 20), _son())
    assert adn.confiance["debit"] < 0.5
    assert 110 <= adn.debit_wpm <= 230


# ── Détection des relances ───────────────────────────────────────────────

def test_les_pics_denergie_sont_reperes():
    courbe = [0.2, 0.2, 0.9, 0.2, 0.2, 0.2, 0.9, 0.2, 0.2, 0.2, 0.9, 0.2]
    pics = _pics(courbe)
    assert len(pics) >= 2
    assert all(0.15 < p <= 1.0 for p in pics)


def test_le_tout_debut_nest_pas_compte_comme_une_relance():
    """Le début, c'est le hook — il est déjà traité ailleurs."""
    courbe = [0.9, 0.9, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2]
    assert all(p > 0.15 for p in _pics(courbe))


# ── Découpage en plans ───────────────────────────────────────────────────

def _repliques(n=4, avec_reaction=True):
    u = Univers.charger(FRUITS)
    a, b = u.personnages[0].id, u.personnages[1].id
    return u, [
        {"numero": i + 1, "personnage": a if i % 2 == 0 else b,
         "replique": "une phrase", "action": "il parle", "emotion": "colere",
         "reaction_de": (b if i % 2 == 0 else a) if avec_reaction else ""}
        for i in range(n)
    ]


def test_les_durees_des_plans_couvrent_exactement_la_voix():
    """Le total des plans doit égaler le total de la parole.

    Un écart de 200 ms par réplique donne trois secondes de décalage sur un
    épisode — l'image ne change plus au bon moment, et ça se voit.
    """
    u, repliques = _repliques(6)
    durees = [3.0, 4.0, 2.5, 3.5, 3.0, 2.0]
    plans = storyboard.decouper(repliques, durees, u)
    assert sum(p.duree_s for p in plans) == pytest.approx(sum(durees), abs=0.01)


def test_une_replique_avec_reaction_donne_deux_plans():
    u, repliques = _repliques(2)
    plans = storyboard.decouper(repliques, [4.0, 4.0], u)
    assert len(plans) == 4
    assert sum(1 for p in plans if p.reaction) == 2


def test_une_replique_trop_courte_nest_pas_coupee():
    """Couper une réplique d'une seconde donne un clignotement, pas un plan."""
    u, repliques = _repliques(2)
    plans = storyboard.decouper(repliques, [1.0, 1.0], u)
    assert len(plans) == 2
    assert not any(p.reaction for p in plans)


# ── `relance` : le temps fort de rétention, déjà écrit par ScriptWriter,
# jusqu'ici jamais relu après sa propre validation (voir script.py) ─────

def test_la_relance_est_portee_sur_le_plan():
    u, repliques = _repliques(2, avec_reaction=False)
    repliques[0]["relance"] = True
    plans = storyboard.decouper(repliques, [4.0, 4.0], u)
    assert plans[0].relance is True
    assert plans[1].relance is False


def test_sans_relance_le_plan_ne_lest_pas_par_defaut():
    """Non-régression : un script en cache d'avant ce champ, ou un plan
    normal (la plupart), ne doit ni planter ni être marqué relance."""
    u, repliques = _repliques(1, avec_reaction=False)
    plans = storyboard.decouper(repliques, [4.0], u)
    assert plans[0].relance is False


def test_la_relance_ne_se_propage_pas_au_plan_de_reaction():
    """Le temps fort appartient à la réplique qui parle, pas à celle qui
    l'encaisse — voir pdz/production/animation.py::noter()."""
    u, repliques = _repliques(1, avec_reaction=True)
    repliques[0]["relance"] = True
    plans = storyboard.decouper(repliques, [4.0], u)
    parlant = next(p for p in plans if not p.reaction)
    reaction = next(p for p in plans if p.reaction)
    assert parlant.relance is True
    assert reaction.relance is False


# ── Point de coupe naturel (pause de la voix plutôt que % fixe) ─────────

def _mots(*paires):
    """`_mots((texte, debut_ms, fin_ms), ...)` — un raccourci de lisibilité."""
    return [Mot(t, d, f) for t, d, f in paires]


def test_sans_mots_le_point_de_coupe_retombe_sur_le_repli():
    assert storyboard.point_de_coupe([], 4000) == storyboard.PART_REACTION
    assert storyboard.point_de_coupe([Mot("seul", 0, 500)], 4000) == storyboard.PART_REACTION


def test_une_pause_proche_de_la_cible_est_choisie():
    """Cible à 65 % de 4000 ms = 2600 ms, fenêtre de recherche [2000, 3200].
    Une vraie pause de la voix dans cette fenêtre doit l'emporter sur le
    pourcentage fixe."""
    mots = _mots(
        ("Mais", 0, 400), ("tu", 400, 600), ("ne", 600, 800),
        ("comprends", 800, 1400), ("pas", 1400, 2200),
        # pause de 500 ms ici, à 2200 ms — dans la fenêtre de recherche.
        ("ce", 2700, 2900), ("qu'il", 2900, 3200), ("y", 3200, 3300),
        ("avait", 3300, 3700), ("derriere", 3700, 4000),
    )
    part = storyboard.point_de_coupe(mots, 4000)
    # La coupe doit tomber sur la pause (à 2200 ms, donc 45 % de réaction),
    # pas sur les 35 % par défaut.
    assert part != storyboard.PART_REACTION
    assert part == pytest.approx(1 - 2200 / 4000, abs=0.01)


def test_une_pause_hors_fenetre_est_ignoree():
    """Une pause en tout début de réplique n'est pas la frontière
    parlant/réaction — juste une respiration avant de parler."""
    mots = _mots(("Alors", 0, 300), ("voila", 900, 1200), ("la", 1200, 1300),
                 ("suite", 1300, 3800))
    assert storyboard.point_de_coupe(mots, 4000) == storyboard.PART_REACTION


def test_la_plus_grande_pause_dans_la_fenetre_gagne():
    mots = _mots(
        ("un", 0, 2200), ("deux", 2210, 2550),   # petite pause : 10 ms
        ("trois", 2900, 3300),                    # grande pause : 350 ms
        ("quatre", 3310, 4000),
    )
    part = storyboard.point_de_coupe(mots, 4000)
    assert part == pytest.approx(1 - 2550 / 4000, abs=0.01)
    assert part != storyboard.PART_REACTION


def test_grouper_mots_par_replique_retrouve_les_frontieres():
    mots = [
        Mot("un", 0, 200), Mot("deux", 200, 500),
        Mot("trois", 1000, 1200), Mot("quatre", 1200, 1600), Mot("cinq", 1600, 2000),
        Mot("six", 3000, 3400),
    ]
    groupes = storyboard.grouper_mots_par_replique(mots, frozenset({0, 1000, 3000}))
    assert [len(g) for g in groupes] == [2, 3, 1]
    assert groupes[1][0].texte == "trois"


def test_grouper_mots_par_replique_sans_frontiere_est_vide():
    assert storyboard.grouper_mots_par_replique([Mot("x", 0, 100)], frozenset()) == []


def test_le_decoupage_utilise_le_point_de_coupe_naturel_quand_fourni():
    u, repliques = _repliques(1, avec_reaction=True)
    # Réplique de 4 s avec une vraie pause de 500 ms à 2200 ms (45 % de
    # réaction), différente des 35 % par défaut.
    mots_replique = _mots(
        ("Mais", 0, 400), ("tu", 400, 600), ("ne", 600, 800),
        ("comprends", 800, 1400), ("pas", 1400, 2200),
        ("ce", 2700, 2900), ("qu'il", 2900, 3200), ("y", 3200, 3300),
        ("avait", 3300, 3700), ("derriere", 3700, 4000),
    )
    sans_mots = storyboard.decouper(repliques, [4.0], u)
    avec_mots = storyboard.decouper(repliques, [4.0], u, mots_par_replique=[mots_replique])

    parlant_sans = next(p for p in sans_mots if not p.reaction)
    parlant_avec = next(p for p in avec_mots if not p.reaction)
    assert parlant_sans.duree_s != parlant_avec.duree_s
    assert parlant_avec.duree_s == pytest.approx(2.2, abs=0.02)


def test_une_coupe_naturelle_trop_courte_retombe_sur_le_repli():
    """Une pause trouvée dans la fenêtre, mais qui produirait un plan de
    réaction sous le minimum lisible (0,9 s), ne doit pas être utilisée."""
    u, repliques = _repliques(1, avec_reaction=True)
    mots_replique = _mots(
        ("long", 0, 3150),
        # pause à 3150 ms : dans la fenêtre de recherche, mais ne laisserait
        # que 850 ms à la réaction — sous le minimum lisible.
        ("fin", 3200, 4000),
    )
    plans = storyboard.decouper(repliques, [4.0], u, mots_par_replique=[mots_replique])
    parlant = next(p for p in plans if not p.reaction)
    reaction = next(p for p in plans if p.reaction)
    assert parlant.duree_s >= storyboard.DUREE_PLAN_MINIMALE_S
    assert reaction.duree_s >= storyboard.DUREE_PLAN_MINIMALE_S
    assert reaction.duree_s == pytest.approx(4.0 * storyboard.PART_REACTION, abs=0.01)


# ── Fonction narrative du plan ───────────────────────────────────────────
# Mesuré à l'écran : sans cette information, le storyboard illustre chaque
# phrase littéralement et produit des plans consécutifs redondants.

def test_la_fonction_du_plan_parlant_vient_de_la_replique():
    u, repliques = _repliques(2, avec_reaction=False)
    repliques[0]["fonction_plan"] = "révèle l'enjeu caché"
    plans = storyboard.decouper(repliques, [4.0, 4.0], u)
    assert plans[0].fonction == "révèle l'enjeu caché"


def test_le_plan_de_reaction_reference_la_fonction_de_la_replique():
    u, repliques = _repliques(1, avec_reaction=True)
    repliques[0]["fonction_plan"] = "fait monter la tension"
    plans = storyboard.decouper(repliques, [4.0], u)
    reaction = next(p for p in plans if p.reaction)
    assert "fait monter la tension" in reaction.fonction


def test_sans_fonction_fournie_le_champ_reste_vide():
    """Non-régression : un script écrit sans empreinte créative (prompt
    antérieur à 1.3.0, ou modèle qui n'en a pas eu besoin) continue de
    produire des plans exploitables, juste sans cette information."""
    u, repliques = _repliques(2, avec_reaction=False)
    plans = storyboard.decouper(repliques, [4.0, 4.0], u)
    assert all(p.fonction == "" for p in plans)


def test_le_resume_affiche_les_fonctions_quand_elles_existent():
    u, repliques = _repliques(1, avec_reaction=False)
    repliques[0]["fonction_plan"] = "établit l'échelle du monde"
    plans = storyboard.decouper(repliques, [4.0], u)
    assert "établit l'échelle du monde" in storyboard.resume(plans)


def test_le_resume_reste_compact_sans_fonctions():
    u, repliques = _repliques(2, avec_reaction=False)
    plans = storyboard.decouper(repliques, [4.0, 4.0], u)
    assert "\n" not in storyboard.resume(plans)


def test_le_resume_compte_les_scenes():
    u, repliques = _repliques(3, avec_reaction=False)
    repliques[0]["decor"] = "villa"
    repliques[1]["decor"] = "villa"
    repliques[2]["decor"] = "ceremonie"
    plans = storyboard.decouper(repliques, [4.0, 4.0, 4.0], u)
    assert "2 scène" in storyboard.resume(plans)


def test_sans_reaction_demandee_un_seul_plan():
    u, repliques = _repliques(3, avec_reaction=False)
    plans = storyboard.decouper(repliques, [4.0, 4.0, 4.0], u)
    assert len(plans) == 3


def test_un_desaccord_script_voix_est_attrape_tout_de_suite():
    u, repliques = _repliques(3)
    with pytest.raises(Exception) as e:
        storyboard.decouper(repliques, [4.0, 4.0], u)
    assert "durées" in str(e.value)


def test_les_numeros_de_plans_sont_continus():
    u, repliques = _repliques(5)
    plans = storyboard.decouper(repliques, [4.0] * 5, u)
    assert [p.numero for p in plans] == list(range(len(plans)))


# ── Notation pour l'animation ────────────────────────────────────────────

def test_laccroche_passe_toujours_en_premier():
    plans = [{"emotion": "calme", "duree_s": 2.0} for _ in range(6)]
    assert animation.noter(plans)[0].index == 0


def test_une_emotion_forte_passe_avant_un_plan_calme():
    plans = [
        {"emotion": "calme", "duree_s": 2.0},      # 0 : accroche
        {"emotion": "calme", "duree_s": 2.0},
        {"emotion": "colere", "duree_s": 2.0},
        {"emotion": "calme", "duree_s": 2.0},
    ]
    classement = animation.noter(plans)
    rangs = {c.index: i for i, c in enumerate(classement)}
    assert rangs[2] < rangs[1]


def test_un_plan_trop_court_est_penalise():
    plans = [
        {"emotion": "calme", "duree_s": 2.0},
        {"emotion": "colere", "duree_s": 0.8},
        {"emotion": "colere", "duree_s": 3.5},
    ]
    classement = animation.noter(plans)
    rangs = {c.index: i for i, c in enumerate(classement)}
    assert rangs[2] < rangs[1]


def test_chaque_note_est_justifiee():
    """Une décision de dépense sans raison écrite est indéfendable."""
    plans = [{"emotion": "colere", "duree_s": 3.0}, {"emotion": "calme", "duree_s": 1.0}]
    assert all(c.raison for c in animation.noter(plans))


def test_une_relance_passe_avant_un_plan_calme_ordinaire():
    """Le temps fort de rétention que ScriptWriter place exprès (audit
    data-flow : `relance` n'était relu par personne après sa propre
    validation) mérite de bouger autant qu'une émotion forte."""
    plans = [
        {"emotion": "calme", "duree_s": 2.0},              # 0 : accroche
        {"emotion": "calme", "duree_s": 2.0, "relance": True},
        {"emotion": "calme", "duree_s": 2.0},
    ]
    classement = animation.noter(plans)
    rangs = {c.index: i for i, c in enumerate(classement)}
    assert rangs[1] < rangs[2]


def test_un_plan_deja_signale_needs_review_est_penalise():
    """Un défaut visuel déjà constaté (`pdz/production/qa_images.py`) ne
    doit pas gagner le budget d'animation — le poste le plus cher du
    pipeline, réservé aux plans qu'on sait déjà défectueux, est de
    l'argent jeté (audit data-flow : ce verdict n'était lu par personne)."""
    plans = [
        {"emotion": "calme", "duree_s": 2.0},                              # 0 : accroche
        {"emotion": "colere", "duree_s": 2.0, "besoin_revue": True},
        {"emotion": "colere", "duree_s": 2.0},
    ]
    classement = animation.noter(plans)
    rangs = {c.index: i for i, c in enumerate(classement)}
    assert rangs[2] < rangs[1]
