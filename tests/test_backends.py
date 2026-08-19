"""Les backends tiennent l'interface, et n'inventent aucune certitude.

Trois propriétés à protéger :

  · **substituabilité** — un mock doit pouvoir remplacer un vrai backend.
    Si ce n'est pas le cas, c'est que le métier connaît encore le
    fournisseur, et l'indépendance annoncée n'existe pas ;
  · **refus avant dépense** — tout ce qui est refusable sans payer doit
    l'être. Une interface réduite à `executer()` obligerait à découvrir chez
    le fournisseur ce qu'on pouvait savoir chez soi ;
  · **honnêteté des capacités** — un backend n'a pas le droit de déclarer
    MESURÉ ce qu'il n'a pas mesuré.
"""

from __future__ import annotations

import pytest

from pdz.backends import (
    ArtefactRendu,
    BackendMusiqueMock,
    BackendVideoMock,
    BackendVoixMock,
    ReconnaissanceAudioBackend,
    TTSBackend,
    VideoBackend,
    backend_musique,
    backend_video,
    backend_voix,
)
from pdz.backends import musique as backends_musique
from pdz.backends import video as backends_video
from pdz.backends import voix as backends_voix
from pdz.backends.base import VoixDisponible
from pdz.backends.video import BackendVideoFal
from pdz.contracts import RenderSpecExecutable, StatutCapacite, Strategie


def _spec(destination, **extra) -> RenderSpecExecutable:
    base = dict(shot_id="shot_001", strategie=Strategie.DIRECT_I2V, duree_s=5.0,
                prompt="animate this still image", image_depart=str(destination),
                parametres={"destination": str(destination)})
    return RenderSpecExecutable(**{**base, **extra})


# ── Substituabilité ──────────────────────────────────────────────────────

@pytest.mark.parametrize("mock,protocole", [
    (BackendVideoMock(), VideoBackend),
    (BackendVoixMock(), TTSBackend),
    (BackendMusiqueMock(), ReconnaissanceAudioBackend),
])
def test_chaque_mock_respecte_son_protocole(mock, protocole):
    assert isinstance(mock, protocole)


def test_le_backend_reel_respecte_aussi_le_protocole():
    """La preuve que le protocole décrit bien ce qui existe, et pas un idéal."""
    assert isinstance(BackendVideoFal(), VideoBackend)


def test_un_mock_remplace_un_vrai_backend_par_le_registre(tmp_path, monkeypatch):
    """Le point d'extension : aucune ligne de métier à modifier."""
    faux = BackendVideoMock()
    resolu = backend_video()
    monkeypatch.setitem(backends_video.BACKENDS, resolu.nom, faux)
    assert backend_video() is faux


def test_les_trois_familles_ont_un_registre_public():
    for module in (backends_video, backends_voix, backends_musique):
        assert isinstance(module.BACKENDS, dict) and module.BACKENDS


# ── Refus avant dépense ──────────────────────────────────────────────────

def test_une_video_sans_image_de_depart_est_refusee(tmp_path):
    """Ce backend ne fait que de l'image→vidéo : partir sans image
    reviendrait à payer pour apprendre une chose connue d'avance."""
    validation = BackendVideoMock().valider(
        _spec(tmp_path / "x.mp4", image_depart=""))
    assert not validation.ok
    assert "image de départ" in validation.bloquants[0]


def test_une_duree_nulle_est_refusee(tmp_path):
    assert not BackendVideoMock().valider(_spec(tmp_path / "x.mp4", duree_s=0)).ok


def test_une_duree_au_dela_du_palier_maximal_est_refusee(tmp_path):
    """« ltx-video rend ~4,84 s qu'on lui demande 5 ou 10 » : la limite est
    une propriété MESURÉE du modèle, pas une préférence."""
    court = BackendVideoMock(durees_s=(5,))
    assert not court.valider(_spec(tmp_path / "x.mp4", duree_s=10)).ok
    assert court.valider(_spec(tmp_path / "x.mp4", duree_s=5)).ok


def test_executer_valide_avant_de_depenser(tmp_path):
    """Un appelant qui oublie de valider ne doit pas pouvoir engager un euro."""
    from pdz.moteur.erreurs import ErreurConfig

    reel = BackendVideoFal()
    with pytest.raises(ErreurConfig, match="refusé avant dépense"):
        reel.executer(_spec(tmp_path / "x.mp4", image_depart=""))


def test_une_image_de_depart_absente_du_disque_est_refusee(tmp_path):
    validation = BackendVideoFal().valider(
        _spec(tmp_path / "sortie.mp4", image_depart=str(tmp_path / "jamais.png")))
    assert not validation.ok
    assert "introuvable" in validation.bloquants[0]


def test_un_prompt_vide_avertit_sans_bloquer(tmp_path):
    """Animer à l'aveugle est une mauvaise idée, pas une impossibilité —
    les deux appellent des actions différentes."""
    image = tmp_path / "img.png"
    image.write_bytes(b"x")
    validation = BackendVideoFal().valider(
        _spec(tmp_path / "s.mp4", image_depart=str(image), prompt="  "))
    assert validation.ok
    assert validation.avertissements


# ── Estimation ───────────────────────────────────────────────────────────

def test_le_cout_est_estime_avant_l_appel(tmp_path):
    estimation = BackendVideoMock(cout_par_seconde=0.05).estimer(
        _spec(tmp_path / "x.mp4", duree_s=10))
    assert estimation.eur == pytest.approx(0.5)


def test_le_backend_reel_ne_presente_jamais_son_estimation_comme_sure(tmp_path):
    """Les prix de `modeles.yaml` bougent tous les 2-3 mois — le fichier le
    documente lui-même. Une estimation présentée comme certaine finirait par
    servir de facture."""
    assert not BackendVideoFal().estimer(_spec(tmp_path / "x.mp4")).sur


# ── Exécution ────────────────────────────────────────────────────────────

def test_un_rendu_produit_un_artefact_date_et_chiffre(tmp_path):
    artefact = BackendVideoMock().executer(_spec(tmp_path / "clip.mp4"))
    assert isinstance(artefact, ArtefactRendu)
    assert artefact.fichier.exists()
    assert artefact.cout_eur > 0
    assert artefact.fournisseur == "mock"


def test_un_echec_de_fournisseur_est_reproductible_sans_reseau(tmp_path):
    """Ce qui rendra testables le diagnostic et la réparation, en PHASES 15-16."""
    from pdz.moteur.erreurs import ErreurFournisseur

    faux = BackendVideoMock(echoue_sur="shot_001")
    with pytest.raises(ErreurFournisseur):
        faux.executer(_spec(tmp_path / "x.mp4"))
    assert faux.executer(_spec(tmp_path / "y.mp4", shot_id="shot_002")).fichier.exists()


# ── Voix : la chronologie officielle ────────────────────────────────────

def test_la_synthese_rend_des_timings_mot_a_mot(tmp_path):
    """Sans eux, le karaoké retombe sur une estimation au prorata et dérive
    de quelques dixièmes sur chaque phrase longue."""
    fichier, mots = BackendVoixMock().synthetiser(
        "tu m'as trahi mon coeur", tmp_path / "v.mp3", voice_id="v1")
    assert fichier.exists()
    assert [m.texte for m in mots] == ["tu", "m'as", "trahi", "mon", "coeur"]


def test_les_mots_sont_contigus_et_sans_chevauchement(tmp_path):
    _, mots = BackendVoixMock().synthetiser("un deux trois", tmp_path / "v.mp3",
                                            voice_id="v1")
    for avant, apres in zip(mots, mots[1:], strict=False):
        assert apres.debut_ms == avant.fin_ms
        assert avant.fin_ms > avant.debut_ms


def test_une_voix_plus_rapide_produit_des_mots_plus_courts(tmp_path):
    lent = BackendVoixMock().synthetiser("bonjour", tmp_path / "a.mp3",
                                         voice_id="v", vitesse=0.5)[1]
    vite = BackendVoixMock().synthetiser("bonjour", tmp_path / "b.mp3",
                                         voice_id="v", vitesse=2.0)[1]
    assert vite[0].fin_ms < lent[0].fin_ms


def test_la_forme_d_une_voix_appartient_a_l_interface():
    """`VoixDisponible` vit dans `backends/base.py` : le métier annote ses
    variables sans importer un fournisseur pour un nom de type."""
    from pdz.ia.elevenlabs import Voix

    voix = Voix({"voice_id": "abc", "name": "Rachel",
                 "labels": {"gender": "female", "use_case": "narration"}})
    assert isinstance(voix, VoixDisponible)
    assert (voix.id, voix.nom, voix.genre) == ("abc", "Rachel", "female")


# ── Musique : ne rien reconnaître est le cas normal ─────────────────────

def test_ne_rien_reconnaitre_n_est_pas_une_erreur(tmp_path):
    """Le résultat le plus fréquent en production, avec les musiques libres
    de droits. L'appel reste facturé — d'où l'importance d'un retour
    explicite plutôt que d'une exception qu'on serait tenté d'avaler."""
    extrait = tmp_path / "e.mp3"
    extrait.write_bytes(b"x")
    assert BackendMusiqueMock().identifier(extrait) is None


def test_un_morceau_reconnu_remonte_tel_quel(tmp_path):
    extrait = tmp_path / "e.mp3"
    extrait.write_bytes(b"x")
    assert BackendMusiqueMock(morceau="Nightcall").identifier(extrait) == "Nightcall"


# ── Capacités : ANNONCE / MESURE / INCONNU ──────────────────────────────

def test_une_capacite_non_mesuree_reste_inconnue():
    """`camera_control` est ANNONCÉ par plusieurs fournisseurs et n'a jamais
    été mesuré ici. Le déclarer MESURÉ parce que la documentation l'affirme
    est exactement l'erreur que `StatutCapacite` existe pour empêcher."""
    capacites = BackendVideoFal().capabilities()
    camera = capacites.capacite("camera_control")
    assert camera.statut is StatutCapacite.INCONNU
    assert not camera.utilisable
    assert camera.valeur is None, "INCONNU n'est pas FAUX"


def test_une_capacite_mesuree_porte_sa_methode():
    """Sans la méthode, une mesure n'est pas reproductible — donc pas une
    mesure, seulement une affirmation de plus."""
    i2v = BackendVideoFal().capabilities().capacite("image_to_video")
    assert i2v.statut is StatutCapacite.MESURE
    assert i2v.utilisable
    assert i2v.methode


def test_le_mock_ne_promet_pas_plus_que_le_vrai():
    """Un mock plus généreux ferait passer des tests que la production ne
    tiendrait pas."""
    vrai = BackendVideoFal().capabilities()
    faux = BackendVideoMock().capabilities()
    assert faux.capacite("camera_control").statut is vrai.capacite("camera_control").statut


def test_les_capacites_de_voix_couvrent_les_timings():
    assert backend_voix().capabilities().sait_faire("word_timestamps")


def test_les_capacites_de_musique_portent_la_limite_mesuree():
    """AudD s'arrête à 10 Mo — une limite mesurée, vérifiée avant envoi."""
    assert backend_musique().capabilities().sait_faire("extrait_10Mo_max")


def test_un_fournisseur_sans_backend_donne_un_message_utile(monkeypatch):
    from pdz.moteur.erreurs import ErreurConfig

    monkeypatch.setattr(backends_video, "BACKENDS", {})
    with pytest.raises(ErreurConfig, match="aucun backend vidéo"):
        backend_video()
