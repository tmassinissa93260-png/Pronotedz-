"""Prototype semi-automatique.

    python main.py                              le storyboard complet
    python -m app.main elements                 tout exporter pour produire
    python -m app.main aligner                  l'image doit EXPLIQUER la phrase
    python -m app.main affiner-tout             les images deposees -> animations
    python -m app.main affiner --shot 1 --image X   une seule image -> animation
    python -m app.main analyser-videos          les videos rendues -> analyses
    python -m app.main controle                 ce qui a ete produit vs le plan
    python -m app.main juger                    le juge aveugle : a-t-on compris ?
    python -m app.main duel --shot N            la deuxieme piste, pour comparer
    python -m app.main timeline                 timeline + sous-titres
    python -m app.main montage                  MP4 final
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "app"

from . import aligner, analyzer, config, juge, memoire, montage, prompts, validator  # noqa: E402
from .models import EXPLICATION_FIELDS, Shot, Storyboard, StoryboardError  # noqa: E402
from .openai_client import OpenAIError, generate_storyboard  # noqa: E402

EXTENSIONS_VIDEO = (".mp4", ".mov", ".webm", ".m4v")
EXTENSIONS_IMAGE = (".png", ".jpg", ".jpeg", ".webp")


def log(tag: str, message: str = "") -> None:
    print(f"[{tag}] {message}".rstrip(), flush=True)


def montrer_problemes(problems: list) -> None:
    for p in problems:
        print(f"  ! {p}", flush=True)


# ---------------------------------------------------------------------------
# ETAPE 1 : script, storyboard, visual bible, prompts
# ---------------------------------------------------------------------------


def construire(subject: str, duration: float, shot_count: int) -> Storyboard:
    log("INPUT")
    print(f"  {subject}\n  {duration:g} secondes\n  {shot_count} plans\n", flush=True)

    log("OPENAI", "Écriture du script...")
    log("OPENAI", "Storyboard, visual bible et prompts...")

    def a_chaque_tentative(numero: int, problems: list) -> None:
        log("VALIDATION", f"Vérification... (tentative {numero})")
        if problems:
            log("CORRECTION", f"{len(problems)} point(s) à corriger, renvoi à OpenAI")
            montrer_problemes(problems)

    sb, problems = generate_storyboard(subject, duration, shot_count,
                                       on_attempt=a_chaque_tentative)
    config.ensure_dirs(len(sb.shots))
    sb.save(config.PROJECT_FILE)

    if problems:
        log("ATTENTION", f"{len(problems)} point(s) non corrigé(s) après "
                         f"{config.MAX_REPAIR_ATTEMPTS} tentative(s) :")
        montrer_problemes(problems)
    else:
        log("OK", f"{len(sb.shots)} plans validés")
    log("OUTPUT", str(config.PROJECT_FILE))
    return sb


def charger() -> Storyboard:
    return Storyboard.load(config.PROJECT_FILE)


# ---------------------------------------------------------------------------
# ETAPE 2 : tout remettre a l'utilisateur
# ---------------------------------------------------------------------------


def chemin_lisible(chemin: Path) -> str:
    """Le chemin tel qu'on le tape, pas celui de la machine qui a tourne.

    Le fichier est lu sur GitHub depuis un telephone : « app/output/images »
    veut dire quelque chose, « /home/runner/work/... » non.
    """
    try:
        return str(chemin.relative_to(config.ROOT_DIR))
    except ValueError:
        return str(chemin)


def ecrire_elements(sb: Storyboard) -> Path:
    """Une feuille unique : script, bible, et pour chaque plan les deux prompts."""
    lignes = [
        f"# {sb.subject}",
        "",
        f"{sb.duration_seconds:g} secondes · {sb.shot_count} plans",
        "",
        "## Script",
        "",
        sb.script,
        "",
        "## Visual bible",
        "",
        "À réutiliser dans **chaque** image. Les couleurs ont un sens fixe.",
        "",
    ]
    lignes += [f"- **{c.replace('_', ' ')}** : {getattr(sb.visual_bible, c)}"
               for c in sb.visual_bible.__dataclass_fields__]
    lignes += ["", "## Code couleur", "",
               "Une notion, une couleur, la même du début à la fin.", ""]
    lignes += [f"- **{e.color}** = {e.notion} — {e.meaning}"
               + ("  *(se déplace)*" if e.moving else "")
               for e in sb.code_couleur()]
    lignes += ["", "## Contrôle qualité", ""]
    lignes += [f"- {axe.replace('_', ' ')} : {note}" for axe, note in sb.quality_check.items()]

    for s in sb.shots:
        lignes += [
            "", "---", "",
            f"## Plan {s.id:02d} — {s.duration_seconds:g}s",
            "",
            f"**Voix** : {s.voice}",
            "",
            f"**Fonction** : {s.educational_function}",
            "",
            f"**Élément pédagogique** : {s.visual_concept}",
            "",
            f"**Intention de mouvement** : `{s.motion_intent}`",
            "",
            "### Le raisonnement, avant le prompt",
            "",
        ]
        alignement = lire_alignement(s.id)
        if alignement:
            lignes = lignes[:-2] + [
                "### Ce que le spectateur doit comprendre",
                "",
                alignement["understanding"],
                "",
                f"**L'action qui l'explique** : {alignement['chosen']}",
                "",
                f"*Comprise sans le son : {alignement['mute_test']}* — "
                f"{alignement['why_chosen']}",
                "",
                "### Le raisonnement, avant le prompt",
                "",
            ]
        lignes += [f"{n}. **{champ.replace('_', ' ')}** : "
                   f"{s.visual_explanation.get(champ, '')}"
                   for n, champ in enumerate(EXPLICATION_FIELDS, start=1)]
        lignes += [
            "",
            "### Prompt image", "", "```", s.image_prompt, "```",
            "",
            "### Prompt animation", "", "```", s.animation_prompt, "```",
        ]

    lignes += [
        "", "---", "",
        "## Ce que tu fais maintenant",
        "",
        "1. Génère chaque **image** avec l'outil de ton choix, à partir du prompt image.",
        f"2. Dépose les images dans `{chemin_lisible(config.IMAGES_DIR)}` nommées "
        "`shot_01.png`, `shot_02.png`…",
        "3. Lance `affiner-tout` : chaque prompt d'animation est réécrit sur ton image "
        "réelle, et non plus sur une image imaginée. **Les prompts ci-dessus sont alors "
        "remplacés** — reviens les lire ici.",
        "4. Génère chaque **animation** à partir de ton image, avec le prompt animation.",
        f"5. Dépose les vidéos dans `{chemin_lisible(config.VIDEOS_DIR)}` nommées "
        "`shot_01.mp4`, `shot_02.mp4`…",
        "6. Reviens : `analyser-videos`, puis `juger`, puis `timeline`, puis "
        "`montage`.",
        "",
        "**`juger`** est le contrôle qui ne se ment pas : un modèle qui ne sait rien "
        "regarde tes vidéos **sans la narration** et dit ce qu'il a compris. On compare "
        "à ce que chaque plan devait faire comprendre. Les plans compris entrent dans "
        "la mémoire et serviront aux vidéos suivantes.",
        "",
        "Pour que l'objet reste le même d'un plan à l'autre, produis d'abord l'image "
        "maîtresse et dérive les autres : voir `app/output/identite.md`.",
        "",
    ]
    config.ELEMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.ELEMENTS_FILE.write_text("\n".join(lignes), encoding="utf-8")
    ecrire_identite(sb)

    for s in sb.shots:
        d = config.shot_dir(s.id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "image_prompt.txt").write_text(s.image_prompt + "\n", encoding="utf-8")
        (d / "animation_prompt.txt").write_text(s.animation_prompt + "\n", encoding="utf-8")
        (d / "voice.txt").write_text(s.voice + "\n", encoding="utf-8")
    return config.ELEMENTS_FILE


# ---------------------------------------------------------------------------
# Videos deposees par l'utilisateur
# ---------------------------------------------------------------------------


def realigner(sb: Storyboard) -> list[tuple[int, list[str]]]:
    """Plan par plan : l'image explique-t-elle la phrase, sans le son ?

    Le storyboard ecrit six plans d'un coup ; l'agent en reprend UN a la fois,
    ce qui est la seule facon de lui donner toute son attention.
    """
    restants = []
    for s in sb.shots:
        log("AGENT", f"Plan {s.id:02d} — l'image explique-t-elle la phrase ?")

        def a_chaque_tentative(numero: int, problemes: list, plan=s) -> None:
            if problemes:
                log("CORRECTION", f"plan {plan.id:02d}, tentative {numero} : "
                                  f"{len(problemes)} point(s)")
                for probleme in problemes:
                    print(f"  ! {probleme}", flush=True)

        avant = aligner.problemes_valides(sb, s)
        plan, manques = aligner.aligner_plan(sb, s, on_attempt=a_chaque_tentative)
        apres = aligner.problemes_valides(sb, s, plan)

        # L'agent n'a pas le droit de degrader. Au run 37 il gagnait sur son
        # axe — le plan se comprenait sans le son — en cassant la continuite
        # et la precision ailleurs. Un gain qui coute plus qu'il ne rapporte
        # n'est pas un gain : le plan d'origine est garde.
        if len(apres) > len(avant):
            log("REFUS", f"plan {s.id:02d} : {len(apres)} manquement(s) contre "
                         f"{len(avant)} avant — le plan d'origine est gardé")
            restants.append((s.id, ["realignement refuse : il degradait le plan"]))
            continue

        dossier = config.shot_dir(s.id)
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "alignment.json").write_text(
            json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        aligner.appliquer(s, plan)
        log("OK", f"plan {s.id:02d} · test sans le son : {plan['mute_test']} · "
                  f"{len(avant)} → {len(apres)} manquement(s)")
        print(f"  comprendre : {plan['understanding']}")
        print(f"  action     : {plan['chosen']}")
        if manques:
            restants.append((s.id, manques))
    return restants


def lire_alignement(shot_id: int) -> dict | None:
    fichier = config.shot_dir(shot_id) / "alignment.json"
    if not fichier.is_file():
        return None
    try:
        return json.loads(fichier.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def cmd_aligner(args) -> int:
    sb = charger()
    restants = realigner(sb)
    sb.save(config.PROJECT_FILE)
    ecrire_elements(sb)
    if restants:
        log("ATTENTION", f"{len(restants)} plan(s) imparfaits :")
        for shot_id, manques in restants:
            for manque in manques:
                print(f"  ! plan {shot_id:02d} : {manque}")
    log("OUTPUT", str(config.PROJECT_FILE))
    log("OUTPUT", str(config.ELEMENTS_FILE))
    return 0


def plan_maitre(sb: Storyboard) -> Shot:
    """Celui qui montre l'objet le plus entier : le plus large gagne.

    Faute de mesure du cadre, on prend le plan dont le prompt parle le moins
    de gros plan et le plus de vue d'ensemble ; a egalite, le premier.
    """
    large = ("wide", "full view", "entire", "whole", "establishing", "overall")
    serre = ("close-up", "closeup", "macro", "detail", "tight")

    def note(s: Shot) -> tuple[int, int]:
        bas = s.image_prompt.lower()
        return (sum(m in bas for m in large) - sum(m in bas for m in serre), -s.id)

    return max(sb.shots, key=note)


def ecrire_identite(sb: Storyboard) -> Path:
    """La fiche qui dit quel plan verrouille l'objet, et comment derive le reste."""
    chemin = config.OUTPUT_DIR / "identite.md"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(prompts.fiche_identite(sb, plan_maitre(sb)) + "\n",
                      encoding="utf-8")
    return chemin


def trouver_images(sb: Storyboard) -> dict[int, Path]:
    """Les images que l'utilisateur a produites, ou qu'il les ait posees.

    Deux endroits acceptes : output/images/shot_01.png, ou directement
    shots/shot_01/image.png — c'est le meme fichier pour le systeme.
    """
    trouvees: dict[int, Path] = {}
    for s in sb.shots:
        candidats = []
        if config.IMAGES_DIR.is_dir():
            candidats += [config.IMAGES_DIR / f"{motif}{ext}"
                          for motif in (f"shot_{s.id:02d}", f"{s.id:02d}", str(s.id))
                          for ext in EXTENSIONS_IMAGE]
        candidats += [config.shot_dir(s.id) / f"image{ext}" for ext in EXTENSIONS_IMAGE]
        for candidat in candidats:
            if candidat.is_file():
                trouvees[s.id] = candidat
                break
    return trouvees


def trouver_videos(sb: Storyboard) -> dict[int, Path]:
    trouvees: dict[int, Path] = {}
    if not config.VIDEOS_DIR.is_dir():
        return trouvees
    for s in sb.shots:
        for ext in EXTENSIONS_VIDEO:
            for motif in (f"shot_{s.id:02d}{ext}", f"{s.id:02d}{ext}", f"{s.id}{ext}"):
                candidat = config.VIDEOS_DIR / motif
                if candidat.is_file():
                    trouvees[s.id] = candidat
                    break
            if s.id in trouvees:
                break
    return trouvees


def charger_analyses(sb: Storyboard) -> dict:
    from .models import VideoAnalysis

    analyses = {}
    for s in sb.shots:
        fichier = config.shot_dir(s.id) / "video_analysis.json"
        if fichier.is_file():
            brut = json.loads(fichier.read_text(encoding="utf-8"))
            analyses[s.id] = VideoAnalysis(**brut)
    return analyses


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------


def cmd_storyboard(args) -> int:
    sb = construire(args.subject, args.duration, args.shots)
    if not args.sans_alignement:
        print()
        log("AGENT", "L'image doit EXPLIQUER la phrase, pas l'illustrer.")
        realigner(sb)
        sb.save(config.PROJECT_FILE)
    chemin = ecrire_elements(sb)
    print()
    print("VISUAL BIBLE")
    for ligne in sb.visual_bible.as_block().splitlines():
        print(f"  {ligne}")
    print()
    print("SCRIPT")
    print(f"  {sb.script}")
    for s in sb.shots:
        print()
        print(f"  ── PLAN {s.id:02d} ── {s.duration_seconds:g}s · {s.word_count} mots "
              f"· {s.words_per_second:.1f} mot/s · {s.motion_intent}")
        print(f"  Voix     : {s.voice}")
        print(f"  Concept  : {s.visual_concept}")
        print(f"  Fonction : {s.educational_function}")
    print()
    log("OUTPUT", str(chemin))
    log("TEST_MODE", "aucune image, aucune vidéo générée — c'est toi qui produis")
    return 0


def cmd_elements(args) -> int:
    sb = charger()
    log("OUTPUT", str(ecrire_elements(sb)))
    for s in sb.shots:
        print(f"  plan {s.id:02d} : {config.shot_dir(s.id)}")
    return 0


def affiner_plan(shot: Shot, image) -> dict:
    """Une image REELLE -> ce qu'elle contient -> prompt d'animation ajuste.

    Le prompt d'animation cesse ici de decrire une image IMAGINEE : il ne
    parle plus que de ce qui bouge dans l'image que l'utilisateur a vraiment
    produite. Le plan modifie est ecrit sur le disque et rendu a l'appelant,
    qui met project.json a jour.
    """
    dossier = config.shot_dir(shot.id)
    dossier.mkdir(parents=True, exist_ok=True)

    log("OPENAI", f"Analyse de l'image du plan {shot.id:02d}...")
    analyse = analyzer.analyze_image(image, shot.visual_concept)
    (dossier / "image_analysis.json").write_text(
        json.dumps(analyse, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    visible = analyse.get("pedagogical_element_visible")
    log("OK", f"Élément pédagogique visible : {visible}")
    if visible is False:
        log("ATTENTION", analyse.get("pedagogical_element_note", ""))

    log("OPENAI", f"Prompt d'animation du plan {shot.id:02d} ajusté à cette image...")
    plan = analyzer.refine_animation(shot, analyse)
    (dossier / "animation.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (dossier / "animation_prompt.txt").write_text(
        plan["animation_prompt"] + "\n", encoding="utf-8")

    # project.json porte desormais le prompt ecrit sur l'image reelle.
    shot.animation_prompt = plan["animation_prompt"].strip()
    shot.motion_intent = plan["motion_intent"]
    log("OK", f"Intention : {plan['motion_intent']}")
    return plan


def cmd_affiner(args) -> int:
    sb = charger()
    shot = sb.shot(args.shot)
    image = args.image if str(args.image).startswith(("http://", "https://")) \
        else Path(args.image)
    plan = affiner_plan(shot, image)
    sb.save(config.PROJECT_FILE)
    print()
    print(plan["animation_prompt"])
    return 0


def cmd_affiner_tout(args) -> int:
    """Toutes les images deposees -> tous les prompts d'animation reecrits."""
    sb = charger()
    images = trouver_images(sb)
    if not images:
        log("STOP", f"aucune image trouvée dans {config.IMAGES_DIR}")
        print("  Nomme-les shot_01.png, shot_02.png, … puis relance.")
        return 1

    faits, echecs = [], []
    for s in sb.shots:
        image = images.get(s.id)
        if image is None:
            log("MANQUE", f"plan {s.id:02d} : aucune image, prompt d'animation inchangé")
            continue
        try:
            affiner_plan(s, image)
        except (OpenAIError, StoryboardError) as exc:
            log("ERREUR", str(exc).splitlines()[0])
            echecs.append(s.id)
            continue
        faits.append(s.id)

    if faits:
        sb.save(config.PROJECT_FILE)
        ecrire_elements(sb)
        log("OUTPUT", str(config.PROJECT_FILE))
        log("OUTPUT", str(config.ELEMENTS_FILE))
    log("OK", f"{len(faits)} prompt(s) d'animation réécrits sur l'image réelle")
    for i in faits:
        print(f"  plan {i:02d} : {config.shot_dir(i) / 'animation_prompt.txt'}")
    return 6 if echecs else 0


def cmd_analyser_videos(args) -> int:
    sb = charger()
    videos = trouver_videos(sb)
    if not videos:
        log("STOP", f"aucune vidéo trouvée dans {config.VIDEOS_DIR}")
        print("  Nomme-les shot_01.mp4, shot_02.mp4, … puis relance.")
        return 1

    echecs = []
    for s in sb.shots:
        video = videos.get(s.id)
        if video is None:
            log("MANQUE", f"plan {s.id:02d} : aucune vidéo")
            continue
        dossier = config.shot_dir(s.id)
        dossier.mkdir(parents=True, exist_ok=True)
        log("OPENAI", f"Analyse de la vidéo {s.id:02d} ({video.name})...")
        try:
            analyse = analyzer.analyze_video(s, video, dossier)
        except OpenAIError as exc:
            log("ERREUR", str(exc).splitlines()[0])
            echecs.append((s.id, str(exc)))
            continue
        (dossier / "video_analysis.json").write_text(
            json.dumps(analyse.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        etat = "conforme" if analyse.matches_plan else "NON CONFORME"
        log("OK", f"Vidéo {s.id:02d} — {analyse.measured_duration or '?'}s — {etat}")
        for defaut in analyse.defects:
            print(f"      défaut : {defaut}")
    if echecs:
        return 6

    # La boucle se ferme ici : on ne se contente plus d'analyser, on compare.
    # Le controle rend 1 quand des plans sont a refaire ; l'analyse, elle,
    # a bien fonctionne — on ne transforme pas un verdict en echec d'outil.
    print()
    cmd_controle(args)
    return 0


def ecrire_controle(sb: Storyboard, problems: list) -> Path:
    """Le verdict sur les vidéos rendues, en une feuille."""
    refaire = validator.a_refaire(problems)
    lignes = [f"# Contrôle des vidéos — {sb.subject}", ""]
    if not problems:
        lignes += [f"Les {len(sb.shots)} plans sont conformes au storyboard.", ""]
    else:
        lignes += [f"**{len(refaire)} plan(s) à refaire** sur {len(sb.shots)}.", ""]
    for s in sb.shots:
        siens = [p for p in problems if p.where == s.slug]
        etat = "à refaire" if s.slug in refaire else ("conforme" if not siens else "à surveiller")
        lignes += [f"## Plan {s.id:02d} — {etat}", ""]
        if not siens:
            lignes += ["Rien à signaler.", ""]
        for p in siens:
            lignes += [f"- **{p.code}** — {p.message}", f"  {p.fix}", ""]
    chemin = config.OUTPUT_DIR / "controle_videos.md"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(lignes), encoding="utf-8")
    return chemin


def cmd_controle(args) -> int:
    """Ce que les vidéos montrent VRAIMENT, comparé à ce qui était demandé."""
    sb = charger()
    analyses = charger_analyses(sb)
    if not analyses:
        log("STOP", "aucune analyse de vidéo trouvée")
        print("  Lance d'abord `analyser-videos`.")
        return 1

    problems = validator.controler_videos(sb, analyses)
    chemin = ecrire_controle(sb, problems)
    refaire = validator.a_refaire(problems)
    if problems:
        montrer_problemes(problems)
    if refaire:
        log("À REFAIRE", ", ".join(refaire))
    else:
        log("OK", f"{len(sb.shots)} plans conformes au storyboard")
    log("OUTPUT", str(chemin))
    return 1 if refaire else 0


def cmd_juger(args) -> int:
    """Un modele qui ne sait rien regarde les videos et dit ce qu'il comprend."""
    sb = charger()
    videos = trouver_videos(sb)
    if not videos:
        log("STOP", f"aucune vidéo trouvée dans {config.VIDEOS_DIR}")
        return 1

    verdicts, echecs = {}, []
    for s in sb.shots:
        video = videos.get(s.id)
        if video is None:
            log("MANQUE", f"plan {s.id:02d} : aucune vidéo")
            continue
        intention = juge.intention_du_plan(s, lire_alignement(s.id))
        log("JUGE", f"Plan {s.id:02d} — regard sans le son...")
        try:
            verdict = juge.juger(s, video, intention, config.shot_dir(s.id))
        except OpenAIError as exc:
            log("ERREUR", str(exc).splitlines()[0])
            echecs.append(s.id)
            continue
        (config.shot_dir(s.id) / "verdict.json").write_text(
            json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        verdicts[s.id] = verdict
        log("OK", f"plan {s.id:02d} · compris à {verdict['understood']} · "
                  f"{verdict['etat']}")
        print(f"  il a vu     : {verdict['vu']['what_i_understand']}")
        print(f"  il fallait  : {intention}")
        print(f"  verdict     : {verdict['verdict']}")
        if verdict["etat"] != "compris":
            print(f"  à changer   : {verdict['fix']}")

    if verdicts:
        souvenirs = memoire.moisson(sb.subject, sb.shots,
                                    {i: lire_alignement(i) or {} for i in verdicts},
                                    verdicts)
        chemin = memoire.retenir(souvenirs)
        gardes = [s for s in souvenirs if s.understood >= memoire.NOTE_RETENUE]
        log("MÉMOIRE", f"{len(gardes)} plan(s) compris retenus → {chemin}")
    return 6 if echecs else 0


def cmd_duel(args) -> int:
    """La deuxième piste de l'agent, écrite noir sur blanc, pour comparer."""
    sb = charger()
    shot = sb.shot(args.shot)
    alignement = lire_alignement(shot.id)
    if not alignement:
        log("STOP", f"plan {shot.id:02d} : aucun alignement, lance `aligner`")
        return 1

    pistes = alignement.get("candidates") or []
    retenue = alignement.get("chosen", "")
    autres = [c for c in pistes if c.get("action") != retenue]
    if not autres:
        log("STOP", "aucune piste écartée à opposer")
        return 1

    print(f"\n  RETENUE  : {retenue}")
    print(f"  POURQUOI : {alignement.get('why_chosen', '')}\n")
    for i, piste in enumerate(autres, start=1):
        print(f"  PISTE {i}  : {piste['action']}")
        print(f"    explique : {piste['explains']}")
        print(f"    rate     : {piste['misses']}\n")
    log("À TOI", "produis l'image des deux, et laisse `juger` trancher")
    return 0


def cmd_timeline(args) -> int:
    sb = charger()
    videos = trouver_videos(sb)
    manquants = [s.id for s in sb.shots if s.id not in videos]
    if manquants:
        log("STOP", f"vidéo manquante pour le(s) plan(s) : "
                    f"{', '.join(f'{i:02d}' for i in manquants)}")
        print(f"  Dépose-les dans {config.VIDEOS_DIR}")
        return 1

    entrees = montage.construire_timeline(sb, videos, charger_analyses(sb))
    montage.sauver_timeline(entrees, config.TIMELINE_FILE)
    config.SRT_FILE.write_text(montage.sous_titres(entrees), encoding="utf-8")

    print()
    print("  Plan   Début     Fin      Durée   Ajustement")
    for e in entrees:
        print(f"  {e.shot_id:02d}     {e.start:6.2f}s  {e.end:6.2f}s  "
              f"{e.duration:5.2f}s  {e.ajustement}")
        for r in e.remarques:
            print(f"           ! {r}")
    print()
    log("OUTPUT", str(config.TIMELINE_FILE))
    log("OUTPUT", str(config.SRT_FILE))
    return 0


def cmd_montage(args) -> int:
    sb = charger()
    videos = trouver_videos(sb)
    manquants = [s.id for s in sb.shots if s.id not in videos]
    if manquants:
        log("STOP", f"vidéo manquante pour le(s) plan(s) : "
                    f"{', '.join(f'{i:02d}' for i in manquants)}")
        return 1

    entrees = montage.construire_timeline(sb, videos, charger_analyses(sb))
    montage.sauver_timeline(entrees, config.TIMELINE_FILE)
    config.SRT_FILE.write_text(montage.sous_titres(entrees), encoding="utf-8")

    voix = config.VOICE_FILE if config.VOICE_FILE.is_file() else None
    musique = config.MUSIC_FILE if config.MUSIC_FILE.is_file() else None
    log("MONTAGE", f"{len(entrees)} plans · voix : {'oui' if voix else 'non'} · "
                   f"musique : {'oui' if musique else 'non'} · sous-titres : oui")
    sortie = montage.assembler(entrees, config.FINAL_FILE, voix, musique,
                               config.SRT_FILE if not args.sans_sous_titres else None)
    log("OK", f"MP4 final -> {sortie}")
    return 0


def cmd_valider(args) -> int:
    sb = charger()
    log("VALIDATION", f"Vérification de {config.PROJECT_FILE}...")
    problems = validator.validate(sb, args.duration, args.shots)
    if problems:
        log("ÉCHEC", f"{len(problems)} point(s) :")
        montrer_problemes(problems)
        return 1
    log("OK", f"{len(sb.shots)} plans validés")
    return 0


def cmd_selfcheck(args) -> int:
    ok = True
    print("Configuration")
    print(f"  SUBJECT     : {config.SUBJECT}")
    print(f"  DURATION    : {config.DURATION}s")
    print(f"  SHOT_COUNT  : {config.SHOT_COUNT}")
    print(f"  cerveau     : {config.cerveau()}")
    print(f"  vision      : {config.OPENAI_VISION_MODEL}")
    print(f"  corrections : {config.MAX_REPAIR_ATTEMPTS} au plus")
    print(f"  vidéos      : {config.VIDEOS_DIR}")

    print("\nCerveau")
    if config.OPENAI_API_KEY:
        source = "GROQ_API_KEY" if config.USING_GROQ else "OPENAI_API_KEY"
        print(f"  {source} présente ({len(config.OPENAI_API_KEY)} caractères)")
    else:
        print("  OPENAI_API_KEY manquante dans .env")
        ok = False

    print("\nffmpeg (montage et analyse vidéo)")
    try:
        montage.exiger_ffmpeg()
        print("  ffmpeg et ffprobe présents")
    except montage.MontageError as exc:
        print(f"  {str(exc).splitlines()[0]}")
        print("  storyboard et prompts fonctionnent sans ; montage et analyse vidéo non.")

    print("\n=> selfcheck", "OK" if ok else "INCOMPLET")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Sujet -> script, storyboard, prompts -> tu produis -> montage")
    sub = parser.add_subparsers(dest="command")

    def commun(p):
        p.add_argument("--subject", default=config.SUBJECT)
        p.add_argument("--duration", type=float, default=config.DURATION)
        p.add_argument("--shots", type=int, default=config.SHOT_COUNT)
        return p

    p_sb = commun(sub.add_parser("storyboard", help="script, bible, plans, prompts"))
    p_sb.add_argument("--sans-alignement", dest="sans_alignement", action="store_true",
                      help="ne pas repasser chaque plan à l'agent d'alignement")
    p_sb.set_defaults(func=cmd_storyboard)
    sub.add_parser("elements", help="tout réexporter pour produire"
                   ).set_defaults(func=cmd_elements)
    sub.add_parser("aligner", help="l'image doit EXPLIQUER la phrase, sans le son"
                   ).set_defaults(func=cmd_aligner)

    sub.add_parser("affiner-tout",
                   help="toutes les images déposées -> prompts d'animation réécrits"
                   ).set_defaults(func=cmd_affiner_tout)

    p_aff = sub.add_parser("affiner", help="une image réelle -> prompt d'animation ajusté")
    p_aff.add_argument("--shot", type=int, required=True)
    p_aff.add_argument("--image", required=True, help="fichier local ou URL http(s)")
    p_aff.set_defaults(func=cmd_affiner)

    sub.add_parser("analyser-videos", help="analyser les vidéos déposées"
                   ).set_defaults(func=cmd_analyser_videos)
    sub.add_parser("controle", help="les vidéos rendues face au plan : quoi refaire"
                   ).set_defaults(func=cmd_controle)
    sub.add_parser("juger", help="le juge aveugle : a-t-on compris sans le son ?"
                   ).set_defaults(func=cmd_juger)

    p_duel = sub.add_parser("duel", help="la deuxième piste de l'agent, pour comparer")
    p_duel.add_argument("--shot", type=int, required=True)
    p_duel.set_defaults(func=cmd_duel)
    sub.add_parser("timeline", help="timeline + sous-titres").set_defaults(func=cmd_timeline)

    p_mon = sub.add_parser("montage", help="assembler le MP4 final")
    p_mon.add_argument("--sans-sous-titres", dest="sans_sous_titres", action="store_true")
    p_mon.set_defaults(func=cmd_montage)

    commun(sub.add_parser("valider", help="rejouer les vérifications")
           ).set_defaults(func=cmd_valider)
    sub.add_parser("selfcheck", help="état de la configuration").set_defaults(func=cmd_selfcheck)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        argv = ["storyboard", *argv]
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except OpenAIError as exc:
        print(f"\n[ERREUR OPENAI] {exc}", file=sys.stderr)
        return 2
    except montage.MontageError as exc:
        print(f"\n[ERREUR MONTAGE] {exc}", file=sys.stderr)
        return 3
    except StoryboardError as exc:
        print(f"\n[ERREUR STORYBOARD] {exc}", file=sys.stderr)
        return 5
    except KeyError as exc:
        print(f"\n[ERREUR] {exc.args[0] if exc.args else exc}", file=sys.stderr)
        return 5
    except KeyboardInterrupt:
        print("\n[STOP] interrompu.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
