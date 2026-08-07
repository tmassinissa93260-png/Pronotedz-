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
from pdz.production.voix import PAUSE_CHANGEMENT_MS, PAUSE_MS, dire
from pdz.univers import Univers
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
