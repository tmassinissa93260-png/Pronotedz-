"""La page locale : regarder ce qui est sorti, valider ce qui attend.

Volontairement minuscule et sans dépendance côté navigateur — pas de build,
pas de node_modules, un seul fichier. Elle tourne sur 127.0.0.1 : rien n'est
exposé sur le réseau, et il n'y a donc ni compte ni mot de passe à gérer.

Elle sert à trois choses, et rien d'autre :

  · **revoir** les épisodes produits, avec leur coût réel ;
  · **valider** un script en attente sans ouvrir un terminal ;
  · **voir le budget** du mois avant de lancer dix épisodes de plus.

    pdz web
"""

from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from pdz import db
from pdz.config import config

application = FastAPI(title="Pronotedz", docs_url=None, redoc_url=None)

STYLE = """
:root { color-scheme: light dark; --bord: #8883; }
body { font: 15px/1.55 system-ui, sans-serif; max-width: 860px;
       margin: 2rem auto; padding: 0 1rem; }
h1 { font-size: 1.4rem; } h2 { font-size: 1.1rem; margin-top: 2.2rem; }
table { border-collapse: collapse; width: 100%; }
td, th { border-bottom: 1px solid var(--bord); padding: .45rem .3rem;
         text-align: left; font-size: .92rem; }
.jauge { height: 9px; background: #8882; border-radius: 5px; overflow: hidden; }
.jauge div { height: 100%; }
.carte { border: 1px solid var(--bord); border-radius: 10px;
         padding: 1rem; margin: 1rem 0; }
video { width: 260px; border-radius: 8px; }
button { font: inherit; padding: .4rem .9rem; border-radius: 7px;
         border: 1px solid var(--bord); cursor: pointer; }
.rien { opacity: .6; font-style: italic; }
.repl { margin: .35rem 0; } .qui { font-weight: 600; }
"""


def _page(titre: str, corps: str) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><meta charset=utf-8>"
        f"<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(titre)}</title><style>{STYLE}</style>{corps}"
    )


def _quand(horodatage: float) -> str:
    return dt.datetime.fromtimestamp(horodatage).strftime("%d/%m %H:%M")


@application.get("/", response_class=HTMLResponse)
def accueil() -> HTMLResponse:
    cfg = config()
    debut_mois = dt.datetime.now().replace(day=1, hour=0, minute=0,
                                           second=0, microsecond=0).timestamp()

    with db.connexion() as conn:
        jobs = conn.execute(
            "SELECT * FROM jobs ORDER BY cree_le DESC LIMIT 20"
        ).fetchall()
        depense = conn.execute(
            "SELECT COALESCE(SUM(cout), 0) t FROM appels_ia WHERE cree_le > ?",
            (debut_mois,),
        ).fetchone()["t"]
        attentes = conn.execute(
            "SELECT * FROM validations WHERE statut = 'en_attente' ORDER BY cree_le"
        ).fetchall()

    part = min(100.0, depense / max(1e-9, cfg.budget_mensuel_eur) * 100)
    couleur = "#2a9d4a" if part < 60 else ("#c99700" if part < 90 else "#c0392b")

    morceaux = [
        "<h1>Pronotedz</h1>",
        f"<p>{depense:.2f} € dépensés ce mois-ci sur "
        f"{cfg.budget_mensuel_eur:.0f} €</p>",
        f"<div class=jauge><div style='width:{part:.0f}%;background:{couleur}'></div></div>",
    ]

    # ── Ce qui attend une décision ───────────────────────────────────────
    morceaux.append("<h2>En attente de ma validation</h2>")
    if not attentes:
        morceaux.append("<p class=rien>Rien n'attend.</p>")
    for v in attentes:
        contenu = db.charger(v["contenu"], {})
        morceaux.append(
            f"<div class=carte><b>{html.escape(v['type'])}</b> "
            f"<span class=rien>{v['job_id']} · {v['etape_cle']}</span>"
            f"{_apercu_script(contenu)}"
            f"<form method=post action='/valider' style='margin-top:.8rem'>"
            f"<input type=hidden name=validation_id value='{v['id']}'>"
            f"<button name=decision value=approuve>Valider</button> "
            f"<button name=decision value=rejete>Refuser</button>"
            f"</form></div>"
        )

    # ── Ce qui est sorti ─────────────────────────────────────────────────
    morceaux.append("<h2>Productions</h2><table>"
                    "<tr><th>quand<th>univers<th>état<th>coût<th></tr>")
    for job in jobs:
        entree = db.charger(job["entree"], {})
        video = _video_du_job(job["id"])
        lecteur = (f"<video controls preload=metadata "
                   f"src='/video/{job['id']}'></video>" if video else "")
        morceaux.append(
            f"<tr><td>{_quand(job['cree_le'])}"
            f"<td>{html.escape(str(entree.get('univers', '?')))}"
            f"<br><span class=rien>{html.escape(str(entree.get('situation',''))[:70])}</span>"
            f"<td>{html.escape(job['statut'])}"
            f"<td>{job['cout_total']:.3f} €<td>{lecteur}</tr>"
        )
    morceaux.append("</table>")

    if not jobs:
        morceaux.append(
            "<p class=rien>Aucune production. Lance "
            "<code>pdz episode &lt;univers&gt; \"&lt;sujet&gt;\"</code>.</p>"
        )

    return _page("Pronotedz", "".join(morceaux))


def _apercu_script(contenu: dict) -> str:
    """Affiche un script de façon lisible, pas comme un bloc de JSON."""
    repliques = contenu.get("repliques")
    if not isinstance(repliques, list):
        return (f"<pre style='white-space:pre-wrap;font-size:.85rem'>"
                f"{html.escape(json.dumps(contenu, ensure_ascii=False, indent=2)[:1200])}"
                f"</pre>")

    lignes = [f"<p><b>{html.escape(str(contenu.get('titre', '')))}</b><br>"
              f"<span class=rien>{html.escape(str(contenu.get('promesse', '')))}</span></p>"]
    for r in repliques:
        lignes.append(
            f"<div class=repl><span class=qui>{html.escape(str(r.get('personnage','')))}</span> — "
            f"{html.escape(str(r.get('replique','')))} "
            f"<span class=rien>({html.escape(str(r.get('emotion','')))})</span></div>"
        )
    return "".join(lignes)


def _video_du_job(job_id: str) -> Path | None:
    """Retrouve le fichier produit par un job. Le nom contient le job.

    On vérifie l'existence à chaque affichage : un fichier déplacé ou effacé
    doit faire disparaître le lecteur, pas produire une vidéo cassée.
    """
    dossier = config().dossier_sorties
    if not dossier.exists():
        return None
    for chemin in dossier.glob("*.mp4"):
        if job_id in chemin.name:
            return chemin
    return None


@application.get("/video/{job_id}")
def video(job_id: str):
    chemin = _video_du_job(job_id)
    if chemin is None:
        return HTMLResponse("Vidéo introuvable", status_code=404)
    return FileResponse(chemin, media_type="video/mp4")


@application.post("/valider")
def valider(validation_id: str = Form(...), decision: str = Form(...)):
    if decision not in ("approuve", "rejete"):
        return HTMLResponse("Décision inconnue", status_code=400)
    with db.connexion() as conn:
        conn.execute(
            "UPDATE validations SET statut = ?, decision = ?, decide_le = ?"
            " WHERE id = ?",
            (decision, decision, db.maintenant(), validation_id),
        )
    return RedirectResponse("/", status_code=303)
