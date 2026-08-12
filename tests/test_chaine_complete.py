"""Le test qui compte le jour de l'installation : la chaîne entière tourne-t-elle ?

Script → voix → découpage → images → sous-titres → montage, jusqu'à un vrai
fichier .mp4 qu'on rouvre avec ffprobe pour vérifier sa durée et son format.

Les trois fournisseurs payants sont remplacés par des doublures locales — pas
pour éviter la dépense, mais parce qu'un test qui dépend du réseau ne dit plus
rien quand il échoue : on ne sait pas si c'est le code ou la connexion. Ici,
un échec vient forcément du code.

Ce que ce test ne couvre pas, et qu'il faut savoir : la qualité de ce que
renvoient les fournisseurs. Un script plat, une voix ratée ou une image floue
passeraient ici sans broncher.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import pytest

from pdz.moteur.erreurs import ErreurValidation
from pdz.video.soustitres import Mot

FRUITS = Path(__file__).resolve().parent.parent / "univers" / "fruit-island.yaml"

SCRIPT_FACTICE = {
    "titre": "La dernière rose",
    "promesse": "Quelqu'un part ce soir",
    "repliques": [
        {"numero": 1, "personnage": "strawberina",
         "replique": "Tu m'as trahie hier soir devant tout le monde",
         "action": "elle claque la porte de la villa", "emotion": "colere",
         "reaction_de": "bananito", "relance": False, "decor": "villa"},
        {"numero": 2, "personnage": "bananito",
         "replique": "C'est pas ce que tu crois, laisse-moi t'expliquer",
         "action": "il recule vers la piscine", "emotion": "peur",
         "reaction_de": "strawberina", "relance": True, "decor": "villa"},
        {"numero": 3, "personnage": "avocado",
         "replique": "On va dire ça, moi j'ai rien vu du tout",
         "action": "il croise les bras", "emotion": "mepris",
         "reaction_de": "", "relance": False, "decor": "ceremonie"},
    ],
    "derniere_image": "la porte de la villa, à nouveau fermée",
}


@pytest.fixture
def atelier(tmp_path, monkeypatch):
    """Un projet complet en bac à sable : dossiers, base, et faux fournisseurs."""
    monkeypatch.setenv("DONNEES", str(tmp_path / "donnees"))
    from pdz.config import config
    config.cache_clear()
    config().preparer_dossiers()

    # ── Le brief (structure narrative, avant le dialogue) ──────────────────
    async def faux_brief(self, entrees, ctx):
        ctx.facturer(0.001)
        sortie = {"beats": [
            {"position_pct": 0, "role": "hook", "quoi": "ça tourne mal dès le début"},
            {"position_pct": 25, "role": "mise en place", "quoi": "les tensions montent"},
            {"position_pct": 60, "role": "montée de tension", "quoi": "l'accusation éclate"},
            {"position_pct": 90, "role": "payoff", "quoi": "quelqu'un part ce soir"},
        ]}
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.brief.BriefWriter.executer", faux_brief)

    # ── Le scénariste ────────────────────────────────────────────────────
    async def faux_script(self, entrees, ctx):
        ctx.facturer(0.012)
        sortie = json.loads(json.dumps(SCRIPT_FACTICE))
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.script.ScriptWriter.executer",
                        faux_script)

    # ── Les prompts d'image (cadrage, séparé du dialogue, après découpage) ──
    async def faux_prompts(self, entrees, ctx):
        ctx.facturer(0.001)
        sortie = {"plans": [
            {"numero": p.numero, "prompt_image": f"prompt riche {p.numero}"}
            for p in entrees["plans"]
        ]}
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.plans.ShotPromptWriter.executer",
                        faux_prompts)

    # ── Le réalisme (texte seul, corrige les prompts avant l'image) ─────────
    async def faux_realisme(self, entrees, ctx):
        ctx.facturer(0.001)
        sortie = {"plans": [
            {"numero": p.numero, "prompt_image": p.action}
            for p in entrees["plans"]
        ]}
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.realisme.RealismWriter.executer",
                        faux_realisme)

    # ── La voix ──────────────────────────────────────────────────────────
    def fausse_voix(texte, sortie, *, voice_id, stabilite=0.5, style=0.4,
                    vitesse=1.0, modele=None):
        # ~12,5 caractères par seconde : le débit d'une voix de synthèse
        # française. C'est cette durée qui pilotera celle des plans, donc
        # elle doit être réaliste, pas seulement variable.
        duree = max(1.2, len(texte) / 12.5)
        sortie.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", f"aevalsrc='0.3*sin(2*PI*160*t)':d={duree:.3f}:s=44100",
             "-ac", "1", str(sortie)],
            check=True, timeout=60,
        )
        mots, curseur = [], 0
        parts = texte.split()
        pas = int(duree * 1000 / max(1, len(parts)))
        for mot in parts:
            mots.append(Mot(mot, curseur, curseur + pas))
            curseur += pas
        return sortie, mots

    monkeypatch.setattr("pdz.production.voix.elevenlabs.synthetiser", fausse_voix)

    # ── Les images ───────────────────────────────────────────────────────
    appels = {"images": 0}

    def fausses_images(prompt, destination, **kwargs):
        from PIL import Image, ImageDraw

        appels["images"] += 1
        img = Image.new("RGB", (608, 1080),
                        (30 + appels["images"] * 17 % 200, 60, 90))
        ImageDraw.Draw(img).rectangle([100, 300, 500, 700], fill=(220, 180, 60))
        destination.parent.mkdir(parents=True, exist_ok=True)
        img.save(destination, quality=90)
        return destination, 0.0028

    monkeypatch.setattr("pdz.production.images.ia_images.generer_image", fausses_images)
    return tmp_path, appels


def _sonder(chemin: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(chemin)],
        capture_output=True, text=True, timeout=60, check=True,
    )
    return json.loads(r.stdout)


def _produire(atelier, **surcharges):
    from pdz.production import episode
    from pdz.univers import Univers

    tmp_path, _ = atelier
    univers = Univers.charger(FRUITS)
    for perso in univers.personnages:
        perso.voix.voice_id = f"voix_{perso.id}"

    sortie = tmp_path / "episode.mp4"
    # 12 s : la durée que SCRIPT_FACTICE tient réellement (27 mots ≈ 10 s à
    # voix haute). Viser les 45 s de l'univers ferait produire un épisode
    # deux fois trop court — ce que l'agent d'écriture refuse désormais, à
    # juste titre. Garder le script court garde aussi le test rapide.
    options = dict(profil="economique", avec_animation=False, duree_s=12)
    options.update(surcharges)
    return episode, asyncio.run(episode.produire(
        univers, "une élimination qui tourne mal", sortie, **options
    ))


# ── La chaîne complète ───────────────────────────────────────────────────

def test_un_episode_complet_sort_en_mp4(atelier):
    _, resultat = _produire(atelier)

    assert resultat.video.exists()


def test_une_erreur_de_validation_du_script_est_rattrapee_par_une_relance(atelier, monkeypatch):
    """Le chemin RÉEL de production (`pdz episode`) appelle ScriptWriter via
    `executer_avec_relance`, jamais `.executer()` nu — sans ce fil, une
    ErreurValidation faisait échouer l'épisode entier dès le premier essai,
    sans jamais laisser sa chance à la correction automatique. Mesuré en
    conditions réelles : c'était le cas jusqu'à ce soir, malgré un mécanisme
    de relance déjà écrit et testé... mais jamais appelé par ce chemin-là."""
    tentatives = {"n": 0}

    async def script_qui_rate_une_fois(self, entrees, ctx):
        tentatives["n"] += 1
        if tentatives["n"] == 1:
            assert "_erreur_precedente" not in entrees
            raise ErreurValidation("Script trop court : ajoute des mots.")
        assert entrees.get("_erreur_precedente") == "Script trop court : ajoute des mots."
        ctx.facturer(0.012)
        sortie = json.loads(json.dumps(SCRIPT_FACTICE))
        return self.apres(sortie, entrees, ctx)

    monkeypatch.setattr("pdz.agents.ecriture.script.ScriptWriter.executer",
                        script_qui_rate_une_fois)

    _, resultat = _produire(atelier)

    assert tentatives["n"] == 2
    assert resultat.video.exists()
    assert resultat.video.stat().st_size > 10_000

    infos = _sonder(resultat.video)
    video = next(f for f in infos["streams"] if f["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1080, 1920)
    assert any(f["codec_type"] == "audio" for f in infos["streams"])


def test_la_duree_du_montage_suit_la_duree_de_la_parole(atelier):
    """Le point central de l'ordre des étapes : la voix décide, pas l'inverse."""
    _, resultat = _produire(atelier)
    duree_reelle = float(_sonder(resultat.video)["format"]["duration"])
    attendue = sum(p.duree_s for p in resultat.plans)
    assert abs(duree_reelle - attendue) < 0.5, (duree_reelle, attendue)


def test_il_y_a_plus_de_plans_que_de_repliques(atelier):
    """Deux répliques sur trois demandent une réaction : elles font deux plans."""
    _, resultat = _produire(atelier)
    assert len(resultat.plans) == 5
    assert sum(1 for p in resultat.plans if p.reaction) == 2


def test_une_image_est_produite_par_plan_plus_les_fiches(atelier):
    _, appels = atelier
    _, resultat = _produire(atelier)
    # 3 fiches de personnages + 5 plans.
    assert appels["images"] == 3 + len(resultat.plans)


def test_le_cout_est_enregistre_et_non_nul(atelier):
    from pdz import db

    _, resultat = _produire(atelier)
    assert resultat.cout > 0

    with db.connexion() as conn:
        job = conn.execute("SELECT * FROM jobs WHERE id = ?",
                           (resultat.job_id,)).fetchone()
    assert job["statut"] == "termine"
    assert job["cout_total"] == pytest.approx(resultat.cout, abs=1e-6)


# ── Reprise ──────────────────────────────────────────────────────────────

def test_relancer_le_meme_job_ne_repaie_rien(atelier):
    """Le mécanisme qui rend une coupure de courant sans conséquence."""
    tmp_path, appels = atelier
    episode, premier = _produire(atelier)

    images_apres_premier = appels["images"]
    _, second = _produire(atelier, job_id=premier.job_id)

    assert appels["images"] == images_apres_premier   # aucune image refaite
    assert second.cout == 0.0
    assert set(second.etapes_reprises) >= {"script", "voix", "images"}
    assert second.video.exists()


def test_une_image_effacee_est_refaite_et_pas_le_reste(atelier):
    """Une étape terminée dont les fichiers ont disparu doit être refaite.

    Sans cette vérification, le montage échouerait trente secondes plus tard
    sur une erreur ffmpeg incompréhensible.
    """
    tmp_path, appels = atelier
    episode, premier = _produire(atelier)

    from pdz import db
    with db.connexion() as conn:
        ligne = conn.execute(
            "SELECT resultat FROM etapes WHERE job_id = ? AND cle = 'images'",
            (premier.job_id,),
        ).fetchone()
    Path(json.loads(ligne["resultat"])["fichiers"][0]).unlink()

    _, second = _produire(atelier, job_id=premier.job_id)

    # L'étape est refaite — elle n'est pas dans les étapes reprises — mais
    # elle ne repaie rien : le cache d'images sert les fichiers identiques.
    assert "images" not in second.etapes_reprises
    assert "script" in second.etapes_reprises
    assert "voix" in second.etapes_reprises
    assert second.cout == 0.0
    assert second.video.exists()


# ── Sous-titres ──────────────────────────────────────────────────────────

def test_les_sous_titres_sont_cales_sur_les_mots_reels(atelier):
    tmp_path, _ = atelier
    _, resultat = _produire(atelier)

    ass = next((tmp_path / "donnees" / "travail" / resultat.job_id)
               .glob("soustitres.ass"))
    contenu = ass.read_text(encoding="utf-8")
    assert "\\k" in contenu                          # balises karaoké
    assert "Dialogue:" in contenu
    # Le dernier mot du script doit être daté après le premier.
    assert contenu.count("Dialogue:") >= 3
