"""Assemblage de la bande voix — testé sans appeler ElevenLabs.

La synthèse est remplacée par de vrais fichiers audio fabriqués avec ffmpeg :
les durées, le recalage des timings et l'assemblage sont donc réellement
vérifiés, seul l'appel réseau est simulé.
"""

import subprocess
from pathlib import Path

import pytest

from pdz.moteur.erreurs import ErreurConfig
from pdz.production import voix as mod
from pdz.production.voix import (
    PAUSE_CHANGEMENT_MS,
    PAUSE_MS,
    _reglages_avec_emotion,
    dire,
)
from pdz.univers import Univers, Voix
from pdz.video.soustitres import Mot


@pytest.fixture
def univers(tmp_path):
    u = Univers.charger(Path("univers/fruit-island.yaml"))
    for i, p in enumerate(u.personnages):
        p.voix.voice_id = f"voix_{i}"
    return u


@pytest.fixture
def fausse_synthese(monkeypatch):
    """Remplace ElevenLabs par un bip de durée proportionnelle au texte."""
    appels = []

    def _faux(texte, sortie, *, voice_id, stabilite, style, vitesse):
        appels.append((texte, voice_id))
        duree = max(0.4, len(texte) * 0.05)
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", f"sine=frequency=300:duration={duree}",
             str(sortie)], check=True)
        # Alignement plausible : chaque mot reçoit sa part.
        mots, t = [], 0.0
        for m in texte.split():
            part = duree / len(texte.split())
            mots.append(Mot(m, round(t * 1000), round((t + part) * 1000)))
            t += part
        return sortie, mots

    monkeypatch.setattr(mod.elevenlabs, "synthetiser", _faux)
    return appels


def _repliques(u, n=3):
    ids = [p.id for p in u.personnages]
    return [{"numero": i + 1, "personnage": ids[i % len(ids)],
             "replique": f"Replique numero {i + 1} de cet episode"}
            for i in range(n)]


def test_la_bande_est_assemblee(tmp_path, univers, fausse_synthese):
    b = dire(_repliques(univers), univers, tmp_path / "voix.m4a", cache=False)
    assert b.fichier.exists() and b.fichier.stat().st_size > 0
    assert len(b.repliques) == 3
    assert b.duree_ms > 0


def test_chaque_personnage_garde_sa_voix(tmp_path, univers, fausse_synthese):
    """C'est ce qui rend un personnage reconnaissable d'un épisode à l'autre."""
    dire(_repliques(univers, 3), univers, tmp_path / "v.m4a", cache=False)
    voix_utilisees = [v for _, v in fausse_synthese]
    assert len(set(voix_utilisees)) == 3, "trois personnages, trois voix"


def test_les_timings_sont_recales_sur_la_piste(tmp_path, univers, fausse_synthese):
    """Le bug le plus vicieux : sans recalage, tous les sous-titres
    sauf ceux de la première réplique sont faux."""
    b = dire(_repliques(univers, 3), univers, tmp_path / "v.m4a", cache=False)

    # Les mots de la 2e réplique commencent après la fin de la 1re.
    assert b.repliques[1].mots[0].debut_ms >= b.repliques[0].fin_ms
    # Et l'ensemble est strictement croissant.
    debuts = [m.debut_ms for m in b.mots]
    assert debuts == sorted(debuts)


def test_une_pause_separe_les_repliques(tmp_path, univers, fausse_synthese):
    b = dire(_repliques(univers, 3), univers, tmp_path / "v.m4a", cache=False)
    ecart = b.repliques[1].debut_ms - b.repliques[0].fin_ms
    # Personnages différents → la pause longue s'applique.
    assert ecart == PAUSE_CHANGEMENT_MS


def test_le_meme_personnage_enchaine_plus_vite(tmp_path, univers, fausse_synthese):
    ids = [univers.personnages[0].id] * 2
    reps = [{"numero": i + 1, "personnage": ids[i], "replique": f"phrase {i}"}
            for i in range(2)]
    b = dire(reps, univers, tmp_path / "v.m4a", cache=False)
    assert b.repliques[1].debut_ms - b.repliques[0].fin_ms == PAUSE_MS
    assert PAUSE_MS < PAUSE_CHANGEMENT_MS


def test_le_cache_evite_de_repayer(tmp_path, univers, fausse_synthese, monkeypatch):
    """ElevenLabs facture au caractère : redire une réplique est du gaspillage."""
    monkeypatch.setenv("DONNEES", str(tmp_path / "d"))
    from pdz.config import config
    config.cache_clear()

    reps = _repliques(univers, 2)
    a = dire(reps, univers, tmp_path / "a.m4a", cache=True)
    appels_apres_premier = len(fausse_synthese)
    b = dire(reps, univers, tmp_path / "b.m4a", cache=True)

    assert len(fausse_synthese) == appels_apres_premier, "aucun nouvel appel"
    assert a.caracteres_factures > 0
    assert b.caracteres_factures == 0
    assert b.caracteres_evites == a.caracteres_factures


def test_un_personnage_sans_voix_est_signale_avant_de_payer(tmp_path, univers,
                                                            fausse_synthese):
    univers.personnages[0].voix.voice_id = ""
    with pytest.raises(ErreurConfig, match="n'a pas de voix"):
        dire(_repliques(univers, 1), univers, tmp_path / "v.m4a", cache=False)


def test_un_personnage_inconnu_est_signale(tmp_path, univers, fausse_synthese):
    reps = [{"numero": 1, "personnage": "pasteque", "replique": "salut"}]
    with pytest.raises(ErreurConfig, match="absent de l'univers"):
        dire(reps, univers, tmp_path / "v.m4a", cache=False)


def test_les_durees_reelles_pilotent_les_plans(tmp_path, univers, fausse_synthese):
    """Le montage cale la durée de chaque plan sur la voix, pas l'inverse."""
    b = dire(_repliques(univers, 3), univers, tmp_path / "v.m4a", cache=False)
    durees = b.durees_repliques_s
    assert len(durees) == 3
    assert all(d > 0 for d in durees)


# ── Prosodie selon l'émotion : un champ écrit par ScriptWriter, jusqu'ici
# jamais lu par la synthèse vocale ────────────────────────────────────────

def test_une_emotion_forte_rend_la_voix_plus_dynamique():
    """Colère : stabilité plus basse (plus variable), style plus haut (plus
    expressif) que la base neutre du personnage."""
    base = Voix(stabilite=0.5, style=0.5, vitesse=1.0)
    stabilite, style, vitesse = _reglages_avec_emotion(base, "colere")
    assert stabilite < base.stabilite
    assert style > base.style
    assert vitesse == base.vitesse


def test_une_emotion_calme_reste_proche_de_la_base_posee():
    base = Voix(stabilite=0.75, style=0.25, vitesse=1.0)
    stabilite, style, vitesse = _reglages_avec_emotion(base, "calme")
    assert 0.6 <= stabilite <= 0.8


def test_une_emotion_inconnue_garde_la_base_du_personnage():
    """Non-régression : un job en cache d'avant ce champ, ou un script qui
    omet `emotion`, ne doit ni planter ni changer la voix."""
    base = Voix(stabilite=0.5, style=0.5, vitesse=1.2)
    assert _reglages_avec_emotion(base, "inconnue") == (0.5, 0.5, 1.2)


def test_deux_emotions_differentes_donnent_des_reglages_differents():
    base = Voix(stabilite=0.5, style=0.5, vitesse=1.0)
    colere = _reglages_avec_emotion(base, "colere")
    tristesse = _reglages_avec_emotion(base, "tristesse")
    assert colere != tristesse


def test_dire_transmet_les_reglages_ajustes_a_la_synthese(tmp_path, univers, monkeypatch):
    """Bug réel : `emotion` était déjà écrit par ScriptWriter sur chaque
    réplique, mais la synthèse vocale ne le lisait jamais — chaque
    personnage gardait le même débit du hook au payoff."""
    import subprocess as sp

    vus = []

    def _espion(texte, sortie, *, voice_id, stabilite, style, vitesse):
        vus.append((stabilite, style))
        duree = max(0.4, len(texte) * 0.05)
        sp.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-f", "lavfi", "-i", f"sine=frequency=300:duration={duree}",
               str(sortie)], check=True)
        return sortie, []

    monkeypatch.setattr(mod.elevenlabs, "synthetiser", _espion)

    perso_id = univers.personnages[0].id
    reps = [
        {"numero": 1, "personnage": perso_id, "replique": "phrase calme",
         "emotion": "calme"},
        {"numero": 2, "personnage": perso_id, "replique": "phrase en colere",
         "emotion": "colere"},
    ]
    dire(reps, univers, tmp_path / "v.m4a", cache=False)

    assert len(vus) == 2
    assert vus[0] != vus[1], "deux émotions différentes doivent produire des réglages différents"
