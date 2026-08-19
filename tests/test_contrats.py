"""Les contrats tiennent-ils leurs promesses ?

Un contrat qui se sérialise mal, se relit de travers ou change de sens sans
changer de version ne vaut rien — il vaut même moins qu'un `dict`, parce
qu'il inspire une confiance qu'il ne mérite pas. Ce fichier vérifie les
quatre garanties sur lesquelles tout le reste s'appuie :

  1. aller-retour JSON sans perte ;
  2. refus explicite de ce qui ne peut pas être relu honnêtement ;
  3. les migrations existent et s'enchaînent ;
  4. les règles d'honnêteté (INCONNU, INCERTAIN, ANNONCE) ne se contournent pas.
"""

from __future__ import annotations

import json
import warnings

import pytest

from pdz import contracts
from pdz.contracts import (
    AudioTimeline,
    Axe,
    Capacite,
    Certitude,
    Claim,
    Contrat,
    Entite,
    ErreurContrat,
    Etat,
    ExecutionPlan,
    ExperienceRecord,
    FailureDiagnosis,
    Mesure,
    ModeEchec,
    ModeleCapacites,
    Mot,
    NoeudExecution,
    ObservationReport,
    Replique,
    Severite,
    ShotSpec,
    Source,
    StatutCapacite,
    TopicRequest,
    Verdict,
    WorldState,
    enregistrer_migration,
    versions,
)
from pdz.contracts.base import migrer

# Tous les contrats concrets exportés — le test doit couvrir ce qui existe,
# pas une liste écrite à la main qui oubliera le prochain.
TOUS = sorted(
    (v for v in vars(contracts).values()
     if isinstance(v, type) and issubclass(v, Contrat) and v is not Contrat),
    key=lambda c: c.nom(),
)


def test_le_paquet_expose_bien_des_contrats():
    assert len(TOUS) >= 15, f"seulement {len(TOUS)} contrats trouvés"


# ── 1. Aller-retour ──────────────────────────────────────────────────────

@pytest.mark.parametrize("contrat", TOUS, ids=lambda c: c.nom())
def test_un_contrat_vide_fait_l_aller_retour(contrat):
    """Le cas le plus bête est celui qui casse en premier."""
    if contrat is TopicRequest:          # `sujet` est obligatoire, à raison
        origine = TopicRequest(sujet="essai")
    else:
        origine = contrat()
    relu = contrat.depuis_json(origine.en_json())
    assert relu == origine


def test_un_contrat_rempli_fait_l_aller_retour():
    """Le cas qui compte : imbrication, tuples, enums, sous-modèles."""
    origine = AudioTimeline(
        id="voix_01", fichier_voix="voix.mp3", duree_ms=4200,
        repliques=(
            Replique(numero=1, personnage="strawberina", texte="tu m'as trahi",
                     debut_ms=0, duree_ms=1500, emotion="colere", relance=True,
                     mots=(Mot(texte="tu", debut_ms=0, fin_ms=300),
                           Mot(texte="m'as", debut_ms=300, fin_ms=800))),
        ),
    )
    relu = AudioTimeline.depuis_json(origine.en_json())
    assert relu == origine
    assert relu.repliques[0].mots[1].texte == "m'as"
    assert relu.mots[0].duree_ms == 300


@pytest.mark.parametrize("contrat", TOUS, ids=lambda c: c.nom())
def test_le_json_est_deterministe(contrat):
    """Deux sérialisations du même contenu donnent le MÊME texte.

    C'est ce qui rend `empreinte()` reproductible — sans quoi le cache
    produirait une clé différente à chaque exécution et ne servirait à rien.
    """
    origine = TopicRequest(sujet="x") if contrat is TopicRequest else contrat()
    assert origine.en_json() == contrat.depuis_json(origine.en_json()).en_json()


@pytest.mark.parametrize("contrat", TOUS, ids=lambda c: c.nom())
def test_la_version_voyage_avec_la_donnee(contrat):
    origine = TopicRequest(sujet="x") if contrat is TopicRequest else contrat()
    brut = json.loads(origine.en_json())
    assert brut["schema_version"] == contrat.VERSION
    assert brut["contrat"] == contrat.nom()


@pytest.mark.parametrize("contrat", TOUS, ids=lambda c: c.nom())
def test_aucun_champ_ne_masque_l_api_du_contrat(contrat):
    """Un champ nommé `nom`, `reference` ou `id` masquerait une méthode de
    `Contrat` — pydantic le signale, et ce test transforme l'avertissement
    en échec. Trouvé pour de vrai sur `ShotSpec.reference` et
    `ExigenceCapacite.nom` pendant l'écriture de ce paquet."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        contrat.model_rebuild(force=True)


# ── 2. Refus explicites ──────────────────────────────────────────────────

def test_une_donnee_sans_version_est_refusee():
    """Un `dict` nu n'est pas un contrat. Le relire comme tel supposerait
    que ses champs ont le sens qu'on leur prête aujourd'hui."""
    with pytest.raises(ErreurContrat, match="schema_version"):
        ShotSpec.depuis_dict({"numero": 3, "but": "montrer le rotor"})


def test_une_version_future_est_refusee():
    """Relire en arrière perdrait ce que la version récente savait en plus."""
    with pytest.raises(ErreurContrat, match="PLUS RÉCENTE"):
        ShotSpec.depuis_dict({"schema_version": "99.0.0", "numero": 3})


def test_une_version_qui_n_est_pas_du_semver_est_refusee():
    with pytest.raises(ErreurContrat, match="semver"):
        ShotSpec.depuis_dict({"schema_version": "v2", "numero": 3})


def test_un_json_invalide_est_refuse_clairement():
    with pytest.raises(ErreurContrat, match="JSON invalide"):
        ShotSpec.depuis_json("{ceci n'est pas du json")


def test_un_champ_inconnu_est_refuse():
    """`extra="forbid"` : un champ inattendu est presque toujours un champ
    RENOMMÉ dont l'ancienne valeur allait être perdue en silence."""
    with pytest.raises(ErreurContrat):
        ShotSpec.depuis_dict({"schema_version": ShotSpec.VERSION, "champ_fantome": 1})


def test_une_version_ancienne_sans_migration_est_refusee():
    """Mieux vaut une erreur nette qu'un contrat à moitié compris."""
    with pytest.raises(ErreurContrat, match="aucune migration"):
        ShotSpec.depuis_dict({"schema_version": "0.9.0", "numero": 1})


# ── 3. Migrations ────────────────────────────────────────────────────────

class _Exemple(Contrat):
    """Contrat jetable : migrer un vrai contrat dans un test le figerait."""

    NOM = "ExempleMigration"
    VERSION = "1.2.0"
    ancien: str = ""
    nouveau: str = ""
    ajoute: int = 0


@enregistrer_migration("ExempleMigration", "1.0.0", "1.1.0")
def _renomme(donnees):
    donnees["nouveau"] = donnees.pop("ancien", "")
    return donnees


@enregistrer_migration("ExempleMigration", "1.1.0", "1.2.0")
def _ajoute(donnees):
    # Champ neuf → valeur NEUTRE. Jamais devinée : inventer une valeur
    # plausible pour d'anciennes données est exactement la rupture
    # silencieuse que le versionnement existe pour empêcher.
    donnees["ajoute"] = 0
    return donnees


def test_les_migrations_s_enchainent():
    relu = _Exemple.depuis_dict({"schema_version": "1.0.0", "ancien": "valeur"})
    assert relu.nouveau == "valeur"
    assert relu.ancien == ""
    assert relu.ajoute == 0


def test_une_migration_intermediaire_marche_aussi():
    relu = _Exemple.depuis_dict({"schema_version": "1.1.0", "nouveau": "v"})
    assert relu.nouveau == "v" and relu.ajoute == 0


def test_une_migration_deja_declaree_est_refusee():
    with pytest.raises(ErreurContrat, match="déjà déclarée"):
        enregistrer_migration("ExempleMigration", "1.0.0", "1.1.0")(lambda d: d)


def test_migrer_vers_la_version_courante_ne_fait_rien():
    assert migrer(_Exemple, _Exemple.VERSION, {"nouveau": "x"}) == {"nouveau": "x"}


# ── 4. Empreinte et cache ────────────────────────────────────────────────

def test_deux_contrats_identiques_ont_la_meme_empreinte():
    assert ShotSpec(numero=1, but="x").empreinte() == ShotSpec(numero=1, but="x").empreinte()


def test_un_champ_different_change_l_empreinte():
    assert ShotSpec(numero=1, but="x").empreinte() != ShotSpec(numero=1, but="y").empreinte()


def test_la_version_entre_dans_l_empreinte():
    """LA propriété qui empêche un artefact produit sous l'ancien sens d'un
    champ d'être réutilisé sous le nouveau."""
    class V1(Contrat):
        NOM = "MemeContrat"
        VERSION = "1.0.0"
        valeur: str = "x"

    class V2(Contrat):
        NOM = "MemeContrat"
        VERSION = "2.0.0"
        valeur: str = "x"

    assert V1().empreinte() != V2().empreinte()


def test_versions_est_trie_et_utilisable_en_signature():
    v = versions(ShotSpec, AudioTimeline, WorldState)
    assert list(v) == sorted(v), "l'ordre doit être stable pour l'empreinte"
    assert v["ShotSpec"] == ShotSpec.VERSION


# ── 5. Les règles d'honnêteté ────────────────────────────────────────────

def test_un_claim_sans_source_n_est_jamais_affirmable():
    """Un FAIT sans source est une contradiction dans les termes."""
    sans = Claim(id="c", enonce="e", certitude=Certitude.FAIT)
    avec = Claim(id="c", enonce="e", certitude=Certitude.FAIT, sources=(Source(url="u"),))
    assert not sans.utilisable_comme_fait
    assert avec.utilisable_comme_fait


def test_une_confiance_elevee_ne_promeut_pas_un_heuristique():
    """Le nombre ne change jamais le statut. C'est l'erreur exacte que le
    couple (certitude, confiance) existe pour empêcher."""
    c = Claim(id="c", enonce="e", certitude=Certitude.HEURISTIQUE,
              confiance=0.99, sources=(Source(url="u"),))
    assert not c.utilisable_comme_fait


def test_un_claim_en_conflit_n_est_pas_affirmable():
    c = Claim(id="c", enonce="e", certitude=Certitude.FAIT,
              sources=(Source(url="u"),), conflits=("autre",))
    assert not c.utilisable_comme_fait


def test_un_axe_non_mesure_vaut_incertain_jamais_reussi():
    """La règle centrale de l'observation. Un système qui lit « pas
    regardé » comme « bon » finit par livrer un clip statique conforme."""
    rapport = ObservationReport(mesures=(
        Mesure(axe=Axe.MOUVEMENT, nom="diff", verdict=Verdict.REUSSI, sonde="s"),
    ))
    assert rapport.verdict_axe(Axe.MOUVEMENT) is Verdict.REUSSI
    assert rapport.verdict_axe(Axe.SEMANTIQUE) is Verdict.INCERTAIN
    assert rapport.verdict is Verdict.INCERTAIN


def test_un_seul_echec_fait_echouer_l_axe_et_le_rapport():
    rapport = ObservationReport(mesures=(
        Mesure(axe=Axe.MOUVEMENT, nom="a", verdict=Verdict.REUSSI, sonde="s"),
        Mesure(axe=Axe.MOUVEMENT, nom="b", verdict=Verdict.ECHOUE, sonde="s"),
    ))
    assert rapport.verdict_axe(Axe.MOUVEMENT) is Verdict.ECHOUE
    assert rapport.verdict is Verdict.ECHOUE
    assert len(rapport.echecs) == 1


def test_le_rapport_dit_ses_propres_angles_morts():
    rapport = ObservationReport(mesures=(
        Mesure(axe=Axe.TECHNIQUE, nom="duree", verdict=Verdict.REUSSI, sonde="ffprobe"),
    ))
    assert Axe.TECHNIQUE not in rapport.axes_non_mesures
    assert Axe.AUDIO in rapport.axes_non_mesures


def test_une_capacite_annoncee_n_engage_pas():
    """Une documentation n'est pas une mesure. Deux modèles ont été retirés
    en 2026 avec des capacités annoncées exactes jusqu'au dernier jour."""
    annoncee = Capacite(nom="camera_control", statut=StatutCapacite.ANNONCE, valeur=True)
    mesuree = Capacite(nom="image_to_video", statut=StatutCapacite.MESURE, valeur=True)
    assert not annoncee.utilisable
    assert mesuree.utilisable


def test_une_capacite_inconnue_n_est_pas_un_refus():
    """`valeur=None` et `valeur=False` disent deux choses différentes :
    « on ne sait pas » et « on a vérifié que non »."""
    inconnue = ModeleCapacites(modele="m").capacite("quoi_que_ce_soit")
    assert inconnue.statut is StatutCapacite.INCONNU
    assert inconnue.valeur is None
    assert not inconnue.utilisable


def test_les_candidats_mettent_le_mesure_avant_l_annonce():
    from pdz.contracts import CapabilityGraph

    annonce = ModeleCapacites(modele="promesse", capacites=(
        Capacite(nom="i2v", statut=StatutCapacite.ANNONCE, valeur=True),))
    mesure = ModeleCapacites(modele="preuve", capacites=(
        Capacite(nom="i2v", statut=StatutCapacite.MESURE, valeur=True),))
    graphe = CapabilityGraph(modeles=(annonce, mesure))
    assert [m.modele for m in graphe.candidats("i2v")] == ["preuve", "promesse"]


def test_une_entite_non_observee_n_est_pas_conforme():
    """Vide ≠ conforme. « Pas encore regardé » et « conforme » ne doivent
    jamais se confondre."""
    jamais_vue = Entite(id="rotor", attendu=Etat(description="tourne"))
    deviante = Entite(id="rotor", attendu=Etat(description="tourne"),
                      observe=Etat(description="immobile"))
    assert not jamais_vue.ecart_connu
    assert deviante.ecart_connu
    assert WorldState(entites=(jamais_vue, deviante)).entites_derivees == (deviante,)


def test_un_diagnostic_peu_sur_n_est_pas_actionnable():
    """Réparer sur une hypothèse à pile ou face coûte plus que d'accepter."""
    sur = FailureDiagnosis(mode=ModeEchec.CAMERA_DOMINANTE, severite=Severite.MAJEURE,
                           confiance=0.8, reparations_possibles=("CAMERA_FIX",))
    doute = sur.model_copy(update={"confiance": 0.3})
    sans_piste = sur.model_copy(update={"reparations_possibles": ()})
    assert sur.actionnable
    assert not doute.actionnable
    assert not sans_piste.actionnable


def test_une_experience_sans_conclusion_n_est_pas_exploitable():
    """Une ligne sans résultat est du bruit : l'agréger ferait bouger des
    moyennes sans rien signifier."""
    from pdz.contracts import Strategie

    complete = ExperienceRecord(shot_id="s1", strategie=Strategie.DIRECT_I2V,
                                modele="kling", resultat="PASS")
    partielle = ExperienceRecord(shot_id="s1", strategie=Strategie.DIRECT_I2V)
    assert complete.exploitable
    assert not partielle.exploitable


# ── 6. Ordonnancement du DAG ─────────────────────────────────────────────

def test_le_dag_ordonnance_par_vagues_parallelisables():
    plan = ExecutionPlan(noeuds=(
        NoeudExecution(noeud_id="image", operation="image"),
        NoeudExecution(noeud_id="profondeur", operation="depth", depend_de=("image",)),
        NoeudExecution(noeud_id="masque", operation="mask", depend_de=("image",)),
        NoeudExecution(noeud_id="composite", operation="comp",
                       depend_de=("profondeur", "masque")),
    ))
    assert plan.ordonnancer() == (("image",), ("masque", "profondeur"), ("composite",))


def test_un_noeud_seul_reste_un_noeud_seul():
    """Un plan simple ne doit pas être forcé à ressembler à un graphe."""
    plan = ExecutionPlan(noeuds=(NoeudExecution(noeud_id="video"),))
    assert plan.ordonnancer() == (("video",),)


def test_une_dependance_circulaire_leve():
    plan = ExecutionPlan(noeuds=(
        NoeudExecution(noeud_id="a", depend_de=("b",)),
        NoeudExecution(noeud_id="b", depend_de=("a",)),
    ))
    with pytest.raises(ValueError, match="circulaire"):
        plan.ordonnancer()


def test_une_dependance_absente_leve():
    """Un nœud qui attend un nœud inexistant attendrait pour toujours."""
    plan = ExecutionPlan(noeuds=(NoeudExecution(noeud_id="a", depend_de=("fantome",)),))
    with pytest.raises(ValueError, match="absents"):
        plan.ordonnancer()


def test_le_cout_du_plan_est_la_somme_de_ses_noeuds():
    plan = ExecutionPlan(noeuds=(
        NoeudExecution(noeud_id="a", cout_estime_eur=0.05, cout_reel_eur=0.07),
        NoeudExecution(noeud_id="b", cout_estime_eur=0.10, cout_reel_eur=0.09),
    ))
    assert plan.cout_estime_eur == pytest.approx(0.15)
    assert plan.cout_reel_eur == pytest.approx(0.16)


# ── 7. Validation du sujet ───────────────────────────────────────────────

def test_un_sujet_vide_ne_compile_pas():
    with pytest.raises(ValueError, match="rien à raconter"):
        TopicRequest(sujet="   ")


@pytest.mark.parametrize("duree", [0.5, 4.9, 601, 10_000])
def test_une_duree_hors_domaine_est_refusee(duree):
    with pytest.raises(ValueError, match="hors du domaine"):
        TopicRequest(sujet="x", duree_cible_s=duree)
