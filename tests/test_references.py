"""Tests du harnais de vidéos de référence privées (pdz.analyse.references).

Aucune vidéo réelle ici : ce module ne fait que découvrir et annoter des
fichiers locaux, jamais les analyser. Les tests utilisent des fichiers
vides sous `tmp_path` pour vérifier la logique de découverte, pas le
contenu vidéo.
"""

from __future__ import annotations

from pdz.analyse.references import dossier_references, lister_references


def test_un_dossier_absent_ne_leve_pas_derreur(tmp_path):
    assert lister_references(tmp_path / "nexiste-pas") == []


def test_un_dossier_vide_ne_leve_pas_derreur(tmp_path):
    assert lister_references(tmp_path) == []


def test_seules_les_extensions_video_sont_retenues(tmp_path):
    (tmp_path / "clip.mp4").write_bytes(b"")
    (tmp_path / "clip.yaml").write_text("mecanique_attendue: test", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("pas une vidéo", encoding="utf-8")

    refs = lister_references(tmp_path)
    assert [r.id for r in refs] == ["clip"]


def test_lannotation_a_cote_de_la_video_est_chargee(tmp_path):
    (tmp_path / "hologramme.mp4").write_bytes(b"")
    (tmp_path / "hologramme.yaml").write_text(
        "mecanique_attendue: pose une question jamais résolue\n"
        "sujet_original: une IA qui explique la physique quantique\n"
        "notes: trouvée sur TikTok\n",
        encoding="utf-8",
    )

    refs = lister_references(tmp_path)
    assert len(refs) == 1
    assert refs[0].mecanique_attendue == "pose une question jamais résolue"
    assert refs[0].sujet_original == "une IA qui explique la physique quantique"
    assert refs[0].notes == "trouvée sur TikTok"


def test_une_video_sans_annotation_donne_des_champs_vides(tmp_path):
    (tmp_path / "sans_note.mov").write_bytes(b"")
    refs = lister_references(tmp_path)
    assert refs[0].mecanique_attendue == ""
    assert refs[0].sujet_original == ""
    assert refs[0].notes == ""


def test_plusieurs_videos_sont_triees_par_id(tmp_path):
    for nom in ["zebre.mp4", "abeille.mp4", "moutarde.webm"]:
        (tmp_path / nom).write_bytes(b"")
    refs = lister_references(tmp_path)
    assert [r.id for r in refs] == ["abeille", "moutarde", "zebre"]


def test_dossier_references_lit_la_variable_denvironnement(monkeypatch):
    monkeypatch.setenv("PDZ_DOSSIER_REFERENCES", "/tmp/mes-references-privees")
    assert str(dossier_references()) == "/tmp/mes-references-privees"


def test_dossier_references_par_defaut(monkeypatch):
    monkeypatch.delenv("PDZ_DOSSIER_REFERENCES", raising=False)
    assert str(dossier_references()) == "donnees/references"
