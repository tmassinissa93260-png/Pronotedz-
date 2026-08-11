"""La commande `pdz` — la seule chose à taper.

    pdz cles                         vérifier que tout est branché
    pdz univers                      lister mes mondes
    pdz analyser <video>             mesurer une vidéo de référence
    pdz charte <video>               en faire un univers jouable
    pdz voix apparier <univers>      donner à chacun la bonne voix
    pdz episode <univers> "<sujet>"  produire un épisode
    pdz jobs / pdz reprendre <id>    voir et relancer
    pdz cout                         où part l'argent

Un principe dans tout ce fichier : la commande fait le travail, elle ne le
décrit pas. Rien ici ne demande de recopier une valeur d'une commande à
l'autre à la main — quand une étape produit un identifiant, la suivante sait
le retrouver.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from pdz import db
from pdz.config import RACINE, config
from pdz.moteur.erreurs import ErreurPdz
from pdz.univers import EmpreinteCreative, Format, Univers

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="Agent perso de production de vidéos courtes.")
voix_app = typer.Typer(no_args_is_help=True, help="Choisir et régler les voix.")
app.add_typer(voix_app, name="voix")

console = Console()
DOSSIER_UNIVERS = RACINE / "univers"


# ── Aides communes ───────────────────────────────────────────────────────

def _journal(verbeux: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbeux else config().log_niveau,
        format="%(message)s",
        stream=sys.stderr,
    )


def _charger_univers(nom: str) -> tuple[Univers, Path]:
    """Accepte un identifiant (« fruit-island ») ou un chemin de fichier."""
    candidats = [Path(nom), DOSSIER_UNIVERS / f"{nom}.yaml", DOSSIER_UNIVERS / nom]
    for chemin in candidats:
        if chemin.is_file():
            return Univers.charger(chemin), chemin

    disponibles = sorted(p.stem for p in DOSSIER_UNIVERS.glob("*.yaml"))
    console.print(f"[red]Univers « {nom} » introuvable.[/red]")
    console.print(f"Disponibles : {', '.join(disponibles) or 'aucun'}")
    console.print("Pour en créer un depuis une vidéo : [bold]pdz charte <video>[/bold]")
    raise typer.Exit(1)


def _echouer(e: ErreurPdz) -> None:
    console.print(f"\n[red]✗ {e.categorie}[/red] — {e}")
    raise typer.Exit(1)


def _resume_empreinte(e: EmpreinteCreative) -> str:
    """Ce qu'on lit tout de suite après `charte`, sans ouvrir le YAML.

    La confiance s'affiche à côté de chaque valeur — c'est ce qui rappelle
    que ce sont des observations du modèle, pas des faits établis.
    """
    def c(champ) -> str:
        return f"{champ.valeur} [dim](confiance {champ.confiance:.0%})[/dim]"

    lignes = [
        "\n[bold]Empreinte créative[/bold]",
        f"  Hook       : {c(e.hook.type)}",
        f"  Narration  : {c(e.narrative.structure)} → {c(e.narrative.fin)}",
        f"  Émotion    : {c(e.psychologie.arc_emotionnel)}",
        f"  Rétention  : {c(e.psychologie.retention)}",
        f"  Cadrage    : {c(e.visuel.cadrage)}",
    ]
    if e.pacing:
        lignes.append(
            f"  Rythme (mesuré) : {e.pacing.get('duree_plan_s', '?')} s/plan, "
            f"{e.pacing.get('debit_wpm', '?')} mots/min"
        )
    if e.principes_reutilisables:
        lignes.append("  Principes réutilisables :")
        lignes += [f"    · {p}" for p in e.principes_reutilisables]
    return "\n".join(lignes)


# ── Vérifications ────────────────────────────────────────────────────────

@app.command()
def cles() -> None:
    """Vérifier que chaque clé d'API fonctionne. Aucun coût."""
    from pdz.cles import main
    raise typer.Exit(main())


@app.command()
def init() -> None:
    """Créer la base et les dossiers de travail."""
    chemin = db.init()
    config().preparer_dossiers()
    console.print(f"[green]✓[/green] Base prête : {chemin}")
    console.print(f"  Dossiers sous : {config().donnees}")


# ── Univers ──────────────────────────────────────────────────────────────

@app.command("univers")
def lister_univers(
    montrer: str = typer.Argument(None, help="identifiant d'un univers à détailler"),
) -> None:
    """Lister mes mondes, ou en détailler un."""
    if montrer:
        univers, chemin = _charger_univers(montrer)
        console.print(f"[bold]{univers.nom}[/bold]  [dim]{chemin}[/dim]\n")
        console.print(univers.contexte_script())
        console.print(f"\n[dim]Style : {univers.style.rendu}[/dim]")
        console.print(f"[dim]Palette : {' '.join(univers.style.palette)}[/dim]")
        sans_voix = [p.nom for p in univers.personnages if not p.voix.voice_id]
        if sans_voix:
            console.print(
                f"\n[yellow]Sans voix : {', '.join(sans_voix)}[/yellow]\n"
                f"→ [bold]pdz voix apparier {univers.id}[/bold]"
            )
        return

    table = Table("identifiant", "nom", "format", "personnages", "voix")
    for chemin in sorted(DOSSIER_UNIVERS.glob("*.yaml")):
        try:
            u = Univers.charger(chemin)
        except Exception as e:  # noqa: BLE001 — un fichier cassé ne cache pas les autres
            table.add_row(chemin.stem, f"[red]illisible : {e}[/red]", "", "", "")
            continue
        avec_voix = sum(1 for p in u.personnages if p.voix.voice_id)
        table.add_row(u.id, u.nom, u.format.value, str(len(u.personnages)),
                      f"{avec_voix}/{len(u.personnages)}")
    console.print(table)


@app.command()
def empreintes() -> None:
    """Diagnostiquer les empreintes créatives de tous les univers analysés.

    Ne dit jamais qu'une répétition est une erreur — seulement qu'elle existe
    et vaut la peine d'être regardée. Sous 3 univers avec empreinte, rien à
    comparer statistiquement : la commande le dit et s'arrête là.
    """
    from pdz.analyse.diversite import diagnostic_diversite

    empreintes: list[tuple[str, Any]] = []
    for chemin in sorted(DOSSIER_UNIVERS.glob("*.yaml")):
        try:
            u = Univers.charger(chemin)
        except Exception:  # noqa: BLE001 — un fichier cassé ne cache pas les autres
            continue
        if u.empreinte_creative is not None:
            empreintes.append((u.id, u.empreinte_creative))

    if len(empreintes) < 3:
        console.print(
            f"[dim]{len(empreintes)} univers avec empreinte créative — "
            "il en faut au moins 3 pour qu'une répétition ait un sens "
            "statistique.[/dim]"
        )
        return

    console.print(f"{len(empreintes)} univers comparés : "
                  f"{', '.join(nom for nom, _ in empreintes)}\n")
    alertes = diagnostic_diversite(empreintes)
    if not alertes:
        console.print("[green]Aucune répétition marquée détectée.[/green]")
        return
    for a in alertes:
        console.print(f"[yellow]{a}[/yellow]")


# ── Musique ──────────────────────────────────────────────────────────────

@app.command()
def musique(
    video: Path = typer.Argument(..., help="la vidéo dont on veut la musique"),
    sans_identification: bool = typer.Option(
        False, "--sans-identification",
        help="ne mesurer que le tempo, la tonalité et l'énergie — gratuit",
    ),
    verbeux: bool = typer.Option(False, "--verbeux", "-v"),
) -> None:
    """Reconnaître la musique de fond : quel morceau, quel tempo, quelle tonalité.

    Le programme isole d'abord les passages où personne ne parle, puis n'envoie
    que ceux-là à la reconnaissance : une voix par-dessus fait chuter le taux
    de réussite. Les mesures, elles, sortent toujours — même sans clé AudD.
    """
    _journal(verbeux)
    from pdz.analyse import musique as module_musique

    try:
        r = module_musique.reconnaitre(
            video, dossier=config().dossier_travail,
            identifier=not sans_identification,
        )
    except ErreurPdz as e:
        _echouer(e)

    console.print("\n[bold]Mesures[/bold]  [dim]locales, 0 €[/dim]")
    console.print(f"  {r.analyse.resume()}")

    if r.analyse.passages:
        zones = ", ".join(f"{p.debut_s:.1f}–{p.fin_s:.1f} s"
                          for p in r.analyse.passages[:5])
        console.print(f"  [dim]Sans parole : {zones}[/dim]")

    if r.identifie:
        m = r.morceau
        console.print(f"\n[bold green]♪ {m.resume()}[/bold green]")
        for nom, lien in (("Écouter", m.lien), ("Spotify", m.spotify),
                          ("Apple Music", m.apple_music)):
            if lien:
                console.print(f"  {nom} : {lien}")
        console.print(
            "\n[yellow]Attention :[/yellow] identifier un morceau ne donne pas "
            "le droit de l'utiliser. Pour une vidéo monétisée, prends un titre "
            "libre de droits qui sonne pareil."
        )
    elif r.echec_identification:
        console.print(f"\n[yellow]Pas d'identification[/yellow] — "
                      f"{r.echec_identification}")

    if r.raison_extrait:
        console.print(f"[dim]Extrait envoyé : {r.raison_extrait}[/dim]")

    console.print("\n[bold]Pour retrouver une musique libre qui sonne pareil[/bold]")
    console.print(f"  {r.analyse.pour_chercher_une_musique_libre()}")


# ── Résultats des publications ───────────────────────────────────────────

resultats_app = typer.Typer(no_args_is_help=True,
                            help="Ce que mes vidéos donnent une fois publiées.")
app.add_typer(resultats_app, name="resultats")


@resultats_app.command("publie")
def resultats_publie(
    job_id: str = typer.Argument(..., help="l'épisode publié"),
    plateforme: str = typer.Option("tiktok", "--plateforme"),
    url: str = typer.Option("", "--url"),
) -> None:
    """Noter qu'un épisode a été publié, pour suivre ce qu'il donne."""
    from pdz.analyse import retention

    try:
        publication_id = retention.enregistrer(job_id, plateforme, url=url)
    except ErreurPdz as e:
        _echouer(e)
    console.print(f"[green]✓[/green] Publication enregistrée : {publication_id}")


@resultats_app.command("importer")
def resultats_importer(
    export: Path = typer.Argument(..., help="le CSV exporté de TikTok Studio"),
    plateforme: str = typer.Option("tiktok", "--plateforme"),
) -> None:
    """Importer l'export d'analytics de la plateforme.

    TikTok Studio → Analytiques → exporter en CSV. YouTube Studio propose la
    même chose. Les colonnes sont reconnues automatiquement, quel que soit
    leur ordre ou leur langue.
    """
    from pdz.analyse import retention

    try:
        lus, associes = retention.importer(export, plateforme)
    except ErreurPdz as e:
        _echouer(e)

    console.print(f"[green]✓[/green] {lus} ligne(s) lue(s), "
                  f"{associes} associée(s) à un épisode produit ici.")
    if associes < lus:
        console.print(
            "[dim]Les lignes non associées sont conservées, mais elles "
            "n'entrent pas dans la comparaison : on ne connaît pas les "
            "réglages qui les ont produites.[/dim]"
        )


@resultats_app.command("bilan")
def resultats_bilan(
    mesure: str = typer.Option(
        "taux_completion", "--mesure",
        help="taux_completion | duree_moyenne_s | vues",
    ),
) -> None:
    """Quels réglages vont avec mes meilleurs résultats.

    Sur MON catalogue — donc sans le biais qui rend l'analyse des vidéos des
    autres illusoire : ici, on voit aussi les épisodes qui n'ont pas marché.
    """
    from pdz.analyse import retention

    try:
        b = retention.bilan(mesure)
    except ErreurPdz as e:
        _echouer(e)

    console.print(f"\n{b.resume()}\n")

    if b.facteurs:
        table = Table("réglage", "groupe", "résultat médian", "épisodes")
        for f in b.facteurs:
            couleur = "" if f.exploitable else "dim "
            table.add_row(
                f"[{couleur}white]{f.nom}[/{couleur}white]",
                f"{f.groupe_bas} → {f.groupe_haut}",
                f"{f.valeur_bas:.2f} → {f.valeur_haut:.2f}"
                + (f"  ({f.ecart_pct:+.0f} %)" if f.exploitable else ""),
                f"{f.n_bas} / {f.n_haut}",
            )
        console.print(table)

        exploitables = [f for f in b.facteurs if f.exploitable]
        if exploitables and b.assez_de_donnees:
            console.print("\n[bold]Ce qui ressort[/bold]")
            for f in exploitables[:4]:
                console.print(f"  · {f.resume()}")
    elif b.publications:
        console.print("[dim]Pas encore assez d'épisodes pour comparer "
                      "quoi que ce soit.[/dim]")

    console.print("\n[bold]À ne pas conclure de ce tableau[/bold]")
    for message in b.avertissements():
        console.print(f"  · {message}")


# ── Analyse ──────────────────────────────────────────────────────────────

@app.command()
def analyser(
    video: Path = typer.Argument(..., help="la vidéo de référence"),
    nom: str = typer.Option(None, "--nom", help="nom à donner à cette forme"),
    json_sortie: Path = typer.Option(None, "--json", help="écrire le rapport complet"),
    verbeux: bool = typer.Option(False, "--verbeux", "-v"),
) -> None:
    """Mesurer une vidéo : rythme, son, image, voix. Aucun coût."""
    _journal(verbeux)
    from pdz.analyse import rapport as module_rapport

    try:
        r = module_rapport.analyser(video, dossier_travail=config().dossier_travail)
    except ErreurPdz as e:
        _echouer(e)

    console.print()
    console.print(r.resume())

    console.print("\n[bold]Ce que ces mesures ne disent pas[/bold]")
    for limite in r.adn.limites():
        console.print(f"  · {limite}")

    structure_id = module_rapport.enregistrer(r, nom)
    console.print(f"\n[green]✓[/green] Forme enregistrée : [bold]{structure_id}[/bold]")
    console.print(f"  Analyse faite en {r.duree_analyse_s:.1f} s, coût 0,00 €")
    console.print(f"  Pour produire avec cette forme :\n"
                  f"  [bold]pdz episode <univers> \"<sujet>\" --forme {structure_id}[/bold]")

    if json_sortie:
        import json
        json_sortie.write_text(
            json.dumps(r.en_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        console.print(f"  Rapport complet : {json_sortie}")


@app.command()
def charte(
    video: Path = typer.Argument(..., help="la vidéo à transposer"),
    identifiant: str = typer.Option(..., "--id", help="identifiant du nouvel univers"),
    nom: str = typer.Option(None, "--nom", help="nom lisible de l'univers"),
    fidele: bool = typer.Option(
        False, "--fidele",
        help="décrire au lieu de transposer — à réserver à MES propres vidéos",
    ),
    duree: int = typer.Option(45, "--duree", help="durée cible des épisodes"),
    verbeux: bool = typer.Option(False, "--verbeux", "-v"),
) -> None:
    """Faire d'une vidéo un univers jouable : style, personnages, décors.

    Par défaut les personnages sont TRANSPOSÉS : on garde l'archétype et le
    style graphique, on change ce qui identifie. Recopier un personnage
    protégé n'est pas une option du programme.
    """
    _journal(verbeux)
    from pdz.agents.analyse.charte import CharteVisuelle, vers_univers
    from pdz.analyse import rapport as module_rapport
    from pdz.moteur.pipeline import Contexte

    try:
        r = module_rapport.analyser(video, dossier_travail=config().dossier_travail)
        console.print(r.resume())

        agent = CharteVisuelle()
        ctx = Contexte(job_id=db.nouvel_id("job"), etape_cle="charte",
                       profil=config().profil, budget_restant=1.0)
        console.print("\n[dim]Lecture des images-clés…[/dim]")
        resultat = asyncio.run(agent.executer({
            "visuel": r.visuel,
            "mesures_rythme": r.adn.bloc_pour_prompt(),
            "transposer": not fidele,
            "langue": "français",
        }, ctx))

        univers = vers_univers(
            resultat, r.visuel, identifiant=identifiant,
            nom=nom or identifiant.replace("-", " ").title(),
            format=Format.SERIE_ANIMEE, duree_cible_s=duree,
            adn=r.adn,
        )
        if univers.empreinte_creative:
            console.print(_resume_empreinte(univers.empreinte_creative))
    except ErreurPdz as e:
        _echouer(e)

    DOSSIER_UNIVERS.mkdir(parents=True, exist_ok=True)
    chemin = DOSSIER_UNIVERS / f"{identifiant}.yaml"
    univers.sauver(chemin)

    console.print(f"\n[green]✓[/green] Univers écrit : [bold]{chemin}[/bold]"
                  f"  ({ctx.cout_engage:.3f} €)")
    for p in univers.personnages:
        console.print(f"  · [bold]{p.nom}[/bold] ({p.espece}) — {p.caractere}")

    if resultat.get("transposition"):
        console.print("\n[bold]Transposition[/bold]")
        for t in resultat["transposition"]:
            console.print(f"  · {t['personnage']} — gardé : {t['garde']}")
            console.print(f"    [dim]changé : {t['change']}[/dim]")

    if resultat.get("incertitudes"):
        console.print("\n[yellow]Ce que les images ne permettent pas de trancher[/yellow]")
        for i in resultat["incertitudes"]:
            console.print(f"  · {i}")

    console.print(f"\nProchaine étape : [bold]pdz voix apparier {identifiant} "
                  f"--source {video}[/bold]")


# ── Voix ─────────────────────────────────────────────────────────────────

@voix_app.command("lister")
def voix_lister() -> None:
    """Lister les voix disponibles sur mon compte ElevenLabs."""
    from pdz.ia import elevenlabs
    try:
        voix = elevenlabs.lister_voix()
        quota = elevenlabs.quota()
    except ErreurPdz as e:
        _echouer(e)

    table = Table("voice_id", "nom", "genre", "langue", "usage")
    for v in voix:
        table.add_row(v.id, v.nom, v.genre, v.langue, v.usage)
    console.print(table)
    console.print(f"[dim]Formule {quota['formule']} · "
                  f"{quota['restants']:,} caractères restants[/dim]")


@voix_app.command("apparier")
def voix_apparier(
    univers_nom: str = typer.Argument(..., help="univers à équiper"),
    source: Path = typer.Option(
        None, "--source",
        help="vidéo ou audio de référence : les voix seront choisies pour lui ressembler",
    ),
    debut: float = typer.Option(0.0, "--debut", help="où commencer à écouter, en secondes"),
    duree: float = typer.Option(30.0, "--duree", help="combien de secondes écouter"),
    maximum: int = typer.Option(12, "--maximum", help="nombre de voix à essayer"),
    ecrire: bool = typer.Option(True, "--ecrire/--simuler"),
    verbeux: bool = typer.Option(False, "--verbeux", "-v"),
) -> None:
    """Donner à chaque personnage la voix qui lui ressemble le plus.

    Avec `--source`, la voix de la référence est mesurée et les candidates
    sont comparées à elle sur des mesures, pas sur des adjectifs.

    Sans source, on part du registre inscrit dans l'univers (« grave »,
    « aigu »…) — c'est une intention, pas une mesure, et seule la hauteur
    pèse alors dans le choix.
    """
    _journal(verbeux)
    from pdz.production import appariement_voix as appar

    univers, chemin = _charger_univers(univers_nom)

    try:
        if source is not None:
            cible = appar.profil_cible(source, debut_s=debut, duree_s=duree)
            console.print(f"Voix de référence : {cible.resume()}\n")
            cibles = {p.id: cible for p in univers.personnages}
        else:
            console.print(
                "[yellow]Pas de --source : les voix sont choisies sur le "
                "registre inscrit dans l'univers, pas sur une mesure.[/yellow]\n"
                "[dim]Pour un vrai appariement : --source <video ou audio>[/dim]\n"
            )
            cibles = {
                p.id: appar.profil_suppose(appar.hauteur_attendue(p, i, len(univers.personnages)))
                for i, p in enumerate(univers.personnages)
            }

        attribue = appar.attribuer(univers, cibles, maximum=maximum)
    except ErreurPdz as e:
        _echouer(e)

    table = Table("personnage", "voix retenue", "écart", "hauteur", "réglages")
    for pid, candidat in attribue.items():
        perso = univers.personnage(pid)
        r = candidat.reglages()
        table.add_row(
            perso.nom, candidat.voix.nom, f"{candidat.distance:.2f}",
            f"{candidat.profil.hauteur_hz:.0f} Hz",
            f"stab {r['stabilite']} · style {r['style']} · vit {r['vitesse']}",
        )
    console.print(table)

    if ecrire:
        appar.appliquer(univers, attribue, chemin)
        console.print(f"\n[green]✓[/green] Voix écrites dans {chemin}")
    else:
        console.print("\n[dim]--simuler : rien n'a été écrit.[/dim]")


# ── Production ───────────────────────────────────────────────────────────

@app.command()
def episode(
    univers_nom: str = typer.Argument(..., help="univers à faire jouer"),
    situation: str = typer.Argument(..., help="ce qui se passe dans l'épisode"),
    duree: float = typer.Option(None, "--duree", help="durée visée, en secondes"),
    profil: str = typer.Option(None, "--profil", help="economique | equilibre | premium"),
    forme: str = typer.Option(
        None, "--forme",
        help="identifiant d'une forme mesurée (`pdz analyser`) à épouser",
    ),
    sortie: Path = typer.Option(None, "--sortie", help="fichier .mp4 de sortie"),
    musique: Path = typer.Option(None, "--musique"),
    sans_animation: bool = typer.Option(False, "--sans-animation"),
    reprendre: str = typer.Option(None, "--reprendre", help="identifiant d'un job à finir"),
    verbeux: bool = typer.Option(False, "--verbeux", "-v"),
) -> None:
    """Produire un épisode complet : script, voix, images, montage."""
    _journal(verbeux)
    from pdz.analyse import rapport as module_rapport
    from pdz.analyse.adn import Adn
    from pdz.production import episode as production

    univers, chemin = _charger_univers(univers_nom)
    cfg = config()

    sans_voix = [p.nom for p in univers.personnages if not p.voix.voice_id]
    if sans_voix:
        console.print(
            f"[red]Ces personnages n'ont pas de voix : {', '.join(sans_voix)}[/red]\n"
            f"→ [bold]pdz voix apparier {univers.id}[/bold]"
        )
        raise typer.Exit(1)

    adn = None
    if forme:
        try:
            adn = Adn.depuis_dict(module_rapport.charger(forme)["adn"])
        except (ErreurPdz, KeyError) as e:
            console.print(f"[red]Forme « {forme} » inutilisable : {e}[/red]")
            raise typer.Exit(1) from e
        console.print(f"Forme épousée : {adn.resume()}")

    destination = sortie or (cfg.dossier_sorties /
                             f"{univers.id}_{int(db.maintenant())}.mp4")

    try:
        resultat = asyncio.run(production.produire(
            univers, situation, destination,
            duree_s=duree, profil=profil or cfg.profil, adn=adn,
            musique=musique, avec_animation=not sans_animation,
            job_id=reprendre, chemin_univers=chemin,
        ))
    except ErreurPdz as e:
        _echouer(e)

    console.print(f"\n[green]✓[/green] {resultat.resume()}")
    console.print(f"[dim]job {resultat.job_id} — pour relancer : "
                  f"pdz reprendre {resultat.job_id}[/dim]")


# ── Suivi ────────────────────────────────────────────────────────────────

@app.command()
def jobs(limite: int = typer.Option(15, "--limite")) -> None:
    """Voir les productions récentes et leur état."""
    with db.connexion() as conn:
        lignes = conn.execute(
            "SELECT id, type, statut, profil, cout_total, budget_max, cree_le, erreur"
            " FROM jobs ORDER BY cree_le DESC LIMIT ?", (limite,),
        ).fetchall()

    if not lignes:
        console.print("Aucune production pour l'instant.")
        return

    import datetime as dt
    table = Table("job", "type", "statut", "coût", "quand")
    for ligne in lignes:
        quand = dt.datetime.fromtimestamp(ligne["cree_le"]).strftime("%d/%m %H:%M")
        statut = ligne["statut"]
        couleur = {"termine": "green", "echoue": "red",
                   "attente_validation": "yellow"}.get(statut, "white")
        table.add_row(ligne["id"], ligne["type"], f"[{couleur}]{statut}[/{couleur}]",
                      f"{ligne['cout_total']:.3f} €", quand)
    console.print(table)

    echoues = [ligne for ligne in lignes if ligne["statut"] == "echoue"]
    for ligne in echoues[:3]:
        console.print(f"[dim]{ligne['id']} : {ligne['erreur']}[/dim]")


@app.command()
def reprendre(job_id: str = typer.Argument(...),
              verbeux: bool = typer.Option(False, "--verbeux", "-v")) -> None:
    """Finir une production interrompue, sans repayer ce qui est déjà fait."""
    _journal(verbeux)
    import json

    from pdz.production import episode as production

    with db.connexion() as conn:
        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job is None:
        console.print(f"[red]Job introuvable : {job_id}[/red]")
        raise typer.Exit(1)

    entree = json.loads(job["entree"])
    univers, chemin = _charger_univers(entree["univers"])
    destination = (config().dossier_sorties / f"{univers.id}_{job_id}.mp4")

    try:
        resultat = asyncio.run(production.produire(
            univers, entree["situation"], destination,
            profil=job["profil"], job_id=job_id, chemin_univers=chemin,
        ))
    except ErreurPdz as e:
        _echouer(e)

    console.print(f"\n[green]✓[/green] {resultat.resume()}")


@app.command()
def cout(jours: int = typer.Option(30, "--jours")) -> None:
    """Où part l'argent : par modèle, par agent, par jour."""
    depuis = db.maintenant() - jours * 86400

    with db.connexion() as conn:
        par_modele = conn.execute(
            "SELECT modele, COUNT(*) n, SUM(cout) total FROM appels_ia"
            " WHERE cree_le > ? GROUP BY modele ORDER BY total DESC", (depuis,),
        ).fetchall()
        par_agent = conn.execute(
            "SELECT COALESCE(agent,'?') agent, COUNT(*) n, SUM(cout) total"
            " FROM appels_ia WHERE cree_le > ? GROUP BY agent ORDER BY total DESC",
            (depuis,),
        ).fetchall()
        evite = conn.execute(
            "SELECT COALESCE(SUM(cout_evite), 0) total FROM cache"
        ).fetchone()

    total = sum(ligne["total"] or 0 for ligne in par_modele)
    plafond = config().budget_mensuel_eur

    table = Table("modèle", "appels", "coût")
    for ligne in par_modele:
        table.add_row(ligne["modele"], str(ligne["n"]), f"{ligne['total'] or 0:.3f} €")
    console.print(table)

    table = Table("agent", "appels", "coût")
    for ligne in par_agent:
        table.add_row(ligne["agent"], str(ligne["n"]), f"{ligne['total'] or 0:.3f} €")
    console.print(table)

    part = total / plafond * 100 if plafond else 0
    couleur = "green" if part < 60 else ("yellow" if part < 90 else "red")
    console.print(f"\nSur {jours} jours : [{couleur}]{total:.2f} €[/{couleur}] "
                  f"sur {plafond:.0f} € ({part:.0f} %)")
    console.print(f"[dim]Économisé par le cache : {evite['total']:.2f} €[/dim]")


@app.command()
def web(port: int = typer.Option(None, "--port")) -> None:
    """Ouvrir la page locale de validation des scripts."""
    import uvicorn

    from pdz.web import application

    p = port or config().web_port
    console.print(f"Page de validation : [bold]http://127.0.0.1:{p}[/bold]")
    uvicorn.run(application, host="127.0.0.1", port=p, log_level="warning")


if __name__ == "__main__":
    app()
