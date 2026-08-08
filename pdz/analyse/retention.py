"""Pourquoi **mes** vidéos marchent — la seule version honnête de la question.

Il existe des dizaines d'outils qui promettent d'expliquer pourquoi une vidéo
a percé. Vérifié : aucun n'a accès à la courbe de rétention d'une vidéo qui ne
lui appartient pas. Ces données sont privées, réservées au compte qui a publié.
Ce que ces outils appellent « courbe de rétention » est une courbe **prédite
par un modèle** à partir du contenu — une opinion, pas une mesure.

La vraie courbe existe pourtant, seconde par seconde, à un seul endroit :
**TikTok Studio et YouTube Studio, pour tes propres vidéos**.

D'où ce module. Au lieu de deviner pourquoi la vidéo de quelqu'un d'autre a
marché — question sur laquelle le biais du survivant interdit toute réponse —
il relie ce que le système a **décidé** à la production (longueur du hook,
durée des plans, émotion d'ouverture, nombre de répliques, univers) à ce que
l'audience a **fait** ensuite. Sur ton propre catalogue, il n'y a plus de biais
du survivant : on voit aussi les épisodes qui n'ont pas marché.

Deux règles tenues strictement :

  1. **On ne conclut pas sous 10 épisodes publiés.** En dessous, l'écart entre
     deux groupes est du bruit, et le présenter comme un enseignement serait
     pire que de ne rien dire.
  2. **On dit « associé à », jamais « fait que ».** Un hook court et une bonne
     rétention peuvent tous deux venir d'un sujet meilleur. Le module range,
     il n'explique pas.
"""

from __future__ import annotations

import csv
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

from pdz import db
from pdz.moteur.erreurs import ErreurPdz

log = logging.getLogger(__name__)

# En dessous, tout écart observé est du bruit d'échantillonnage.
MINIMUM_POUR_CONCLURE = 10
MINIMUM_PAR_GROUPE = 4

SCHEMA_PUBLICATIONS = """
CREATE TABLE IF NOT EXISTS publications (
    id              TEXT PRIMARY KEY,
    job_id          TEXT,
    plateforme      TEXT NOT NULL,          -- tiktok | youtube | instagram
    titre           TEXT,
    url             TEXT,
    publie_le       REAL,
    vues            INTEGER DEFAULT 0,
    likes           INTEGER DEFAULT 0,
    commentaires    INTEGER DEFAULT 0,
    partages        INTEGER DEFAULT 0,
    duree_moyenne_s REAL,                   -- temps de visionnage moyen
    taux_completion REAL,                   -- part qui va jusqu'au bout, 0-1
    courbe          TEXT,                   -- JSON, si je la saisis à la main
    maj_le          REAL NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_publications_job ON publications(job_id);
"""

# Les en-têtes changent selon la plateforme, la langue et l'année. On les
# reconnaît par mots-clés plutôt que par correspondance exacte : un export
# renommé ne doit pas obliger à retoucher le programme.
COLONNES = {
    "titre": ("titre", "title", "video title", "nom", "description", "caption"),
    "url": ("url", "lien", "link", "video link", "permalink"),
    "vues": ("vues", "views", "video views", "lectures", "plays", "nombre de vues"),
    "likes": ("likes", "j'aime", "jaime", "mentions"),
    "commentaires": ("commentaires", "comments"),
    "partages": ("partages", "shares"),
    "duree_moyenne_s": ("temps de visionnage moyen", "average watch time",
                        "avg watch time", "duree moyenne", "average view duration"),
    "taux_completion": ("taux de completion", "completion rate", "completed",
                        "watched full video", "taux d'achevement"),
    "publie_le": ("date", "date de publication", "publish time", "post time",
                  "created"),
}


@dataclass
class Publication:
    id: str
    plateforme: str
    titre: str
    job_id: str | None = None
    vues: int = 0
    duree_moyenne_s: float | None = None
    taux_completion: float | None = None
    likes: int = 0
    partages: int = 0

    @property
    def engagement(self) -> float:
        """Part des spectateurs qui réagissent. Robuste au volume de vues."""
        return (self.likes + self.partages) / max(1, self.vues)


@dataclass
class Facteur:
    """Une décision de production, et ce qu'elle donne."""

    nom: str
    explication: str
    groupe_bas: str
    groupe_haut: str
    valeur_bas: float
    valeur_haut: float
    n_bas: int
    n_haut: int

    @property
    def ecart_pct(self) -> float:
        if not self.valeur_bas:
            return 0.0
        return (self.valeur_haut - self.valeur_bas) / abs(self.valeur_bas) * 100

    @property
    def exploitable(self) -> bool:
        return min(self.n_bas, self.n_haut) >= MINIMUM_PAR_GROUPE

    def resume(self) -> str:
        if not self.exploitable:
            return (f"{self.nom} : pas assez d'épisodes pour comparer "
                    f"({self.n_bas} contre {self.n_haut})")
        sens = "mieux" if self.ecart_pct > 0 else "moins bien"
        return (f"{self.nom} : {self.groupe_haut} fait {abs(self.ecart_pct):.0f} % "
                f"{sens} que {self.groupe_bas} "
                f"({self.valeur_haut:.2f} contre {self.valeur_bas:.2f}, "
                f"{self.n_haut} vs {self.n_bas} épisodes)")


@dataclass
class Bilan:
    publications: list[Publication] = field(default_factory=list)
    facteurs: list[Facteur] = field(default_factory=list)
    mesure: str = "taux de complétion"

    @property
    def assez_de_donnees(self) -> bool:
        return len(self.publications) >= MINIMUM_POUR_CONCLURE

    def resume(self) -> str:
        n = len(self.publications)
        if not self.publications:
            return ("Aucune publication enregistrée. Publie des épisodes, "
                    "puis importe l'export de TikTok Studio.")
        if not self.assez_de_donnees:
            return (f"{n} épisode(s) publié(s) sur les {MINIMUM_POUR_CONCLURE} "
                    "qu'il faut pour que les écarts veuillent dire quelque "
                    "chose. Les chiffres ci-dessous sont affichés, mais rien "
                    "n'en est encore concluable.")
        return (f"{n} épisodes publiés · {self.mesure} médian "
                f"{self._median():.2f}")

    def _median(self) -> float:
        valeurs = [p.taux_completion for p in self.publications
                   if p.taux_completion is not None]
        return median(valeurs) if valeurs else 0.0

    def avertissements(self) -> list[str]:
        """Ce qu'il ne faut pas conclure de ce tableau. Toujours affiché."""
        messages = [
            "Ces écarts sont des associations, pas des causes : un hook court "
            "et une bonne rétention peuvent tous deux venir d'un meilleur sujet.",
            "Le sujet et l'écriture pèsent plus que tous les réglages listés "
            "ici. Ils ne sont pas mesurés parce qu'ils ne se mesurent pas.",
        ]
        if not self.assez_de_donnees:
            messages.insert(0, (
                f"Moins de {MINIMUM_POUR_CONCLURE} épisodes publiés : à ce "
                "stade, l'écart entre deux groupes est indiscernable du hasard."
            ))
        return messages


# ── Enregistrer une publication ──────────────────────────────────────────

def _table() -> None:
    with db.connexion() as conn:
        conn.executescript(SCHEMA_PUBLICATIONS)


def enregistrer(job_id: str, plateforme: str, *, url: str = "",
                titre: str = "") -> str:
    """Note qu'un épisode produit a été publié quelque part."""
    _table()
    with db.connexion() as conn:
        job = conn.execute("SELECT id FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            raise ErreurPdz(f"Job introuvable : {job_id}")

        if not titre:
            titre = _titre_du_job(conn, job_id)

        publication_id = db.nouvel_id("pub")
        conn.execute(
            "INSERT INTO publications (id, job_id, plateforme, titre, url,"
            " publie_le, maj_le) VALUES (?,?,?,?,?,?,?)",
            (publication_id, job_id, plateforme, titre, url,
             db.maintenant(), db.maintenant()),
        )
    return publication_id


def _titre_du_job(conn, job_id: str) -> str:
    ligne = conn.execute(
        "SELECT resultat FROM etapes WHERE job_id = ? AND cle = 'script'",
        (job_id,),
    ).fetchone()
    script = db.charger(ligne["resultat"], {}) if ligne else {}
    return script.get("titre", "")


# ── Importer un export de plateforme ─────────────────────────────────────

def _normaliser(texte: str) -> str:
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFD", texte or "")
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", sans_accent.lower()).strip()


def reperer_colonnes(entetes: list[str]) -> dict[str, str]:
    """Associe chaque champ connu à la colonne du fichier qui le porte.

    On accepte n'importe quel ordre et n'importe quelle langue : les exports
    de TikTok, YouTube et des outils tiers ne s'accordent sur rien, et
    demander un format précis ferait échouer l'import une fois sur deux.
    """
    trouvees: dict[str, str] = {}
    normalises = {_normaliser(e): e for e in entetes}

    for champ, mots in COLONNES.items():
        for mot in mots:
            cible = _normaliser(mot)
            # Correspondance exacte d'abord : « vues » ne doit pas attraper
            # « vues des abonnés » s'il existe une colonne « vues » tout court.
            if cible in normalises:
                trouvees[champ] = normalises[cible]
                break
        else:
            for mot in mots:
                cible = _normaliser(mot)
                for normalise, original in normalises.items():
                    if cible in normalise and original not in trouvees.values():
                        trouvees[champ] = original
                        break
                if champ in trouvees:
                    break
    return trouvees


def _nombre(valeur: str | None) -> float:
    """Lit « 12 345 », « 12,3 % », « 1.2K » ou « 00:00:07 »."""
    if valeur is None:
        return 0.0
    texte = str(valeur).strip().replace(" ", "").replace("\xa0", "")
    if not texte:
        return 0.0

    if ":" in texte:                       # une durée hh:mm:ss ou mm:ss
        parts = [p for p in texte.split(":") if p.strip()]
        try:
            secondes = 0.0
            for part in parts:
                secondes = secondes * 60 + float(part.replace(",", "."))
            return secondes
        except ValueError:
            return 0.0

    pourcent = texte.endswith("%")
    texte = texte.rstrip("%").strip()

    facteur = 1.0
    if texte and texte[-1] in "KkMm":
        facteur = 1_000 if texte[-1] in "Kk" else 1_000_000
        texte = texte[:-1]

    texte = texte.replace(" ", "").replace(",", ".")
    try:
        nombre = float(texte) * facteur
    except ValueError:
        return 0.0
    return nombre / 100 if pourcent else nombre


def importer(chemin: Path, plateforme: str = "tiktok") -> tuple[int, int]:
    """Lit un export CSV et met à jour les publications. Renvoie (lus, associés).

    L'association se fait sur le titre, normalisé : c'est la seule colonne
    présente dans tous les exports. Une ligne qui ne correspond à aucun
    épisode produit est quand même enregistrée — connaître les résultats
    d'une vidéo faite à la main reste utile pour comparer.
    """
    chemin = Path(chemin)
    if not chemin.exists():
        raise ErreurPdz(f"Export introuvable : {chemin}")

    _table()
    texte = chemin.read_text(encoding="utf-8-sig", errors="replace")
    try:
        dialecte = csv.Sniffer().sniff(texte[:4000], delimiters=",;\t")
    except csv.Error:
        dialecte = csv.excel
    lignes = list(csv.DictReader(texte.splitlines(), dialect=dialecte))

    if not lignes:
        raise ErreurPdz(f"{chemin.name} est vide ou illisible.")

    colonnes = reperer_colonnes(list(lignes[0].keys()))
    if "titre" not in colonnes:
        raise ErreurPdz(
            f"Aucune colonne de titre dans {chemin.name}. "
            f"Colonnes trouvées : {', '.join(lignes[0].keys())}"
        )

    lus = associes = 0
    with db.connexion() as conn:
        conn.executescript(SCHEMA_PUBLICATIONS)
        titres_connus = {
            _normaliser(_titre_du_job(conn, ligne["id"])): ligne["id"]
            for ligne in conn.execute(
                "SELECT id FROM jobs WHERE statut = 'termine'"
            ).fetchall()
        }
        titres_connus.pop("", None)

        for ligne in lignes:
            titre = (ligne.get(colonnes["titre"]) or "").strip()
            if not titre:
                continue
            lus += 1

            job_id = titres_connus.get(_normaliser(titre))
            associes += int(job_id is not None)

            valeurs = {
                champ: _nombre(ligne.get(colonne))
                for champ, colonne in colonnes.items()
                if champ not in ("titre", "url", "publie_le")
            }
            completion = valeurs.get("taux_completion") or None
            # Un taux donné en « 43 » plutôt qu'en « 43 % » : au-dessus de 1,
            # c'est forcément une échelle de 0 à 100.
            if completion and completion > 1:
                completion = completion / 100

            existant = conn.execute(
                "SELECT id FROM publications WHERE plateforme = ? AND titre = ?",
                (plateforme, titre),
            ).fetchone()

            champs = (
                job_id,
                int(valeurs.get("vues", 0)),
                int(valeurs.get("likes", 0)),
                int(valeurs.get("commentaires", 0)),
                int(valeurs.get("partages", 0)),
                valeurs.get("duree_moyenne_s") or None,
                completion,
                db.maintenant(),
            )
            if existant:
                conn.execute(
                    "UPDATE publications SET job_id = COALESCE(?, job_id),"
                    " vues = ?, likes = ?, commentaires = ?, partages = ?,"
                    " duree_moyenne_s = ?, taux_completion = ?, maj_le = ?"
                    " WHERE id = ?",
                    (*champs, existant["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO publications (id, plateforme, titre, url,"
                    " job_id, vues, likes, commentaires, partages,"
                    " duree_moyenne_s, taux_completion, maj_le)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (db.nouvel_id("pub"), plateforme, titre,
                     (ligne.get(colonnes.get("url", "")) or "") if "url" in colonnes
                     else "", *champs),
                )

    log.info("Import %s : %d ligne(s), %d associée(s) à un épisode produit",
             chemin.name, lus, associes)
    return lus, associes


# ── Ce que mes décisions donnent ─────────────────────────────────────────

def caracteristiques(job_id: str) -> dict[str, float]:
    """Les décisions prises à la production de cet épisode.

    Uniquement ce que le système a réellement choisi, et qu'il pourrait
    choisir autrement la prochaine fois. Un facteur qu'on ne peut pas régler
    n'aurait rien à faire dans ce tableau.
    """
    with db.connexion() as conn:
        script = db.charger(
            (conn.execute(
                "SELECT resultat FROM etapes WHERE job_id = ? AND cle = 'script'",
                (job_id,)).fetchone() or {"resultat": None})["resultat"], {}
        )
        voix = db.charger(
            (conn.execute(
                "SELECT resultat FROM etapes WHERE job_id = ? AND cle = 'voix'",
                (job_id,)).fetchone() or {"resultat": None})["resultat"], {}
        )
        anim = db.charger(
            (conn.execute(
                "SELECT resultat FROM etapes WHERE job_id = ? AND cle = 'animation'",
                (job_id,)).fetchone() or {"resultat": None})["resultat"], {}
        )

    repliques = script.get("repliques") or []
    if not repliques:
        return {}

    durees = voix.get("durees_couvrantes_s") or []
    plans = anim.get("plans") or []

    return {
        "mots_du_hook": float(len(str(repliques[0].get("replique", "")).split())),
        "nb_repliques": float(len(repliques)),
        "duree_s": float(sum(durees)) if durees else 0.0,
        "duree_plan_s": (float(sum(durees)) / len(plans)) if plans and durees else 0.0,
        "plans_animes": float(sum(1 for p in plans if p.get("anime"))),
        "relances": float(sum(1 for r in repliques if r.get("relance"))),
        "hook_emotion_forte": float(
            repliques[0].get("emotion") in ("colere", "surprise", "peur")
        ),
    }


EXPLICATIONS = {
    "mots_du_hook": "longueur de la première réplique",
    "nb_repliques": "nombre de prises de parole",
    "duree_s": "durée de l'épisode",
    "duree_plan_s": "durée moyenne d'un plan",
    "plans_animes": "nombre de plans animés par un modèle vidéo",
    "relances": "nombre de relances narratives",
    "hook_emotion_forte": "émotion forte dès la première réplique",
}


def bilan(mesure: str = "taux_completion") -> Bilan:
    """Compare mes décisions de production aux résultats réels.

    `mesure` : `taux_completion` (le meilleur signal), `duree_moyenne_s`,
    ou `vues` — les vues dépendent surtout de la distribution, elles disent
    donc moins de choses sur la vidéo elle-même.
    """
    _table()
    with db.connexion() as conn:
        lignes = conn.execute(
            "SELECT * FROM publications WHERE job_id IS NOT NULL"
        ).fetchall()

    publications = [
        Publication(
            id=ligne["id"], plateforme=ligne["plateforme"], titre=ligne["titre"],
            job_id=ligne["job_id"], vues=ligne["vues"] or 0,
            duree_moyenne_s=ligne["duree_moyenne_s"],
            taux_completion=ligne["taux_completion"],
            likes=ligne["likes"] or 0, partages=ligne["partages"] or 0,
        )
        for ligne in lignes
    ]

    observations = []
    for publication in publications:
        resultat = getattr(publication, mesure, None)
        traits = caracteristiques(publication.job_id or "")
        if resultat is None or not traits:
            continue
        observations.append((traits, float(resultat)))

    return Bilan(
        publications=publications,
        facteurs=_comparer(observations),
        mesure=EXPLICATIONS.get(mesure, mesure.replace("_", " ")),
    )


def _comparer(observations: list[tuple[dict[str, float], float]]) -> list[Facteur]:
    """Coupe à la médiane et compare les deux moitiés.

    Une comparaison de médianes plutôt qu'une corrélation : avec vingt points,
    un coefficient de corrélation donne un chiffre à trois décimales qui
    inspire une confiance qu'il ne mérite pas. « Les épisodes à hook court
    finissent 18 % plus souvent » se vérifie d'un coup d'œil.
    """
    if len(observations) < MINIMUM_PAR_GROUPE * 2:
        return []

    facteurs: list[Facteur] = []
    noms = sorted({nom for traits, _ in observations for nom in traits})

    for nom in noms:
        valeurs = [traits[nom] for traits, _ in observations if nom in traits]
        if len(set(valeurs)) < 2:
            continue                       # ce réglage n'a jamais varié

        seuil = median(valeurs)
        bas = [r for traits, r in observations if traits.get(nom, seuil) <= seuil]
        haut = [r for traits, r in observations if traits.get(nom, seuil) > seuil]
        if not bas or not haut:
            continue

        facteurs.append(Facteur(
            nom=EXPLICATIONS.get(nom, nom),
            explication=nom,
            groupe_bas=f"≤ {seuil:g}",
            groupe_haut=f"> {seuil:g}",
            valeur_bas=median(bas),
            valeur_haut=median(haut),
            n_bas=len(bas),
            n_haut=len(haut),
        ))

    facteurs.sort(key=lambda f: (f.exploitable, abs(f.ecart_pct)), reverse=True)
    return facteurs
