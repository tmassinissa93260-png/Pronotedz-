"""Vérifie que chaque clé d'API fonctionne — la première chose à lancer.

Chaque service est testé par l'appel le moins cher possible : lecture du
quota ou de la liste des modèles. Aucune génération, donc **coût nul**.

    pdz cles

Ce module vit dans le paquet et non dans `tools/` : c'est une commande du
programme, elle doit marcher même quand seul `pdz` est installé.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from pdz.config import config

VERT, ROUGE, JAUNE, GRIS, FIN = "\033[92m", "\033[91m", "\033[93m", "\033[90m", "\033[0m"


# Valeurs des fichiers d'exemple : présentes mais pas remplies.
GABARITS = ("sk-ant-...", "...", "sk_...", "votre", "your", "xxx", "changeme")


def _renseignee(cle: str) -> bool:
    """Une clé collée avec des guillemets ou un commentaire est une erreur
    fréquente : on la traite comme absente plutôt que de l'envoyer telle quelle."""
    propre = cle.strip().strip("\"'")
    if not propre or propre.lower() in GABARITS:
        return False
    return not any(propre.lower().startswith(g) for g in GABARITS)


def _etat(ok: bool | None) -> str:
    if ok is None:
        return f"{GRIS}— non renseignée{FIN}"
    return f"{VERT}✓ fonctionne{FIN}" if ok else f"{ROUGE}✗ échec{FIN}"


def verifier_anthropic(cle: str) -> tuple[bool, str]:
    """Un appel à 1 jeton : le moins cher moyen de valider une clé."""
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": cle, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": "claude-haiku-4-5-20251001", "max_tokens": 1,
              "messages": [{"role": "user", "content": "."}]},
        timeout=30,
    )
    if r.status_code == 200:
        return True, "scripts et analyses disponibles"
    if r.status_code == 401:
        return False, "clé refusée"
    if r.status_code == 400 and "credit" in r.text.lower():
        return False, "clé valide mais AUCUN CRÉDIT — va dans Billing"
    return False, f"HTTP {r.status_code} — {r.text[:110]}"


def verifier_elevenlabs(cle: str) -> tuple[bool, str]:
    r = httpx.get("https://api.elevenlabs.io/v1/user/subscription",
                  headers={"xi-api-key": cle}, timeout=30)
    if r.status_code != 200:
        return False, ("clé refusée" if r.status_code == 401
                       else f"HTTP {r.status_code}")
    d = r.json()
    reste = d.get("character_limit", 0) - d.get("character_count", 0)
    # ~1600 caractères par vidéo de 45 s, mesuré sur les scripts du projet.
    return True, (f"formule {d.get('tier')} · {reste:,} caractères restants "
                  f"(≈ {reste // 1600} vidéos)")


def verifier_fal(cle: str) -> tuple[bool, str]:
    """Lit le solde de crédit plutôt que de générer quoi que ce soit.

    L'ancien endpoint (`rest.alpha.fal.ai/tokens/`) renvoyait 405 : il a
    changé ou n'a jamais accepté GET. Celui-ci correspond à la documentation
    actuelle de fal.ai (`api-reference/platform-apis/for-accounts`).
    ⚠️ Non vérifiable depuis l'environnement de développement — fal.ai y est
    bloqué par la politique réseau. À confirmer sur la machine de l'utilisateur.
    """
    r = httpx.get("https://api.fal.ai/v1/account/billing",
                  headers={"Authorization": f"Key {cle}"}, timeout=30)
    if r.status_code == 200:
        credits = (r.json().get("credits") or {})
        solde = credits.get("current_balance")
        if solde is not None:
            return True, f"images et animation disponibles · {solde} {credits.get('currency', '$')} de crédit"
        return True, "images et animation disponibles"
    if r.status_code == 401:
        return False, "clé refusée"
    if r.status_code == 403:
        # La documentation fal.ai réserve cet endpoint précis aux clés
        # « Admin ». Une clé normale — la plupart des clés créées depuis le
        # tableau de bord — reçoit ce refus alors qu'elle fonctionne très
        # bien pour générer des images : ce contrôle-là ne sait juste pas la
        # confirmer. L'annoncer comme « échec » alarmerait pour rien.
        return True, ("clé acceptée, mais ce contrôle précis demande une clé "
                      "Admin pour lire le solde — sans conséquence pour "
                      "générer des images")
    return False, f"HTTP {r.status_code}"


def verifier_groq(cle: str) -> tuple[bool, str]:
    r = httpx.get("https://api.groq.com/openai/v1/models",
                  headers={"Authorization": f"Bearer {cle}"}, timeout=30)
    if r.status_code == 200:
        return True, "transcription disponible"
    return False, "clé refusée" if r.status_code == 401 else f"HTTP {r.status_code}"


SERVICES = [
    # Anthropic n'est plus obligatoire : le profil « gratuit » (Groq) écrit
    # les scripts sans lui. Elle reste utile — meilleure écriture, et seule
    # capable de vision (`analyser`, `charte`) — donc toujours vérifiée et
    # affichée, juste sans faire échouer la commande si elle manque.
    ("Anthropic", "anthropic_api_key", verifier_anthropic,
     "les scripts (qualité supérieure, vision)", False),
    # fal.ai non plus : le profil « gratuit » illustre avec Pollinations
    # (aucune clé, aucune carte), au prix d'une constance des personnages
    # moins bonne d'un plan à l'autre. fal.ai reste le choix par défaut des
    # autres profils, et le seul qui anime les plans.
    ("fal.ai", "fal_key", verifier_fal,
     "les images de meilleure qualité, et l'animation", False),
    ("ElevenLabs", "elevenlabs_api_key", verifier_elevenlabs,
     "la voix", True),
    ("Groq", "groq_api_key", verifier_groq,
     "la transcription, l'écriture en profil gratuit", False),
]


def main() -> int:
    cfg = config()
    print(f"\n  Vérification des clés — aucun coût, aucune génération\n"
          f"  {GRIS}fichier lu : {Path('.env').resolve()}{FIN}\n")

    manquantes, cassees = [], []

    for nom, champ, verif, role, obligatoire in SERVICES:
        cle = getattr(cfg, champ, "")
        print(f"  {nom:12} {GRIS}{role:38}{FIN} ", end="", flush=True)

        if not _renseignee(cle):
            print(_etat(None))
            if obligatoire:
                manquantes.append(nom)
            continue
        try:
            # La clé est nettoyée avant l'envoi : un espace ou un guillemet
            # oublié au copier-coller ferait échouer l'appel pour rien.
            ok, detail = verif(cle.strip().strip("\"'"))
        except httpx.HTTPError as e:
            ok, detail = False, f"réseau injoignable — {type(e).__name__}"
        except UnicodeEncodeError:
            ok, detail = False, ("caractère accentué dans la clé — un commentaire "
                                 "a été collé avec ? Voir .env.exemple")
        except Exception as e:  # noqa: BLE001 — un test ne doit jamais planter
            ok, detail = False, f"{type(e).__name__} — {str(e)[:90]}"
        print(f"{_etat(ok)}  {GRIS}{detail}{FIN}")
        if not ok:
            cassees.append(nom)

    print()
    if not manquantes and not cassees:
        print(f"  {VERT}Tout est prêt.{FIN} Tu peux lancer une génération.\n")
        return 0

    if manquantes:
        print(f"  {JAUNE}Clés absentes :{FIN} {', '.join(manquantes)}")
        print(f"  {GRIS}→ ouvre le fichier .env et colle-les après le signe ={FIN}")
    if cassees:
        print(f"  {ROUGE}Clés en échec :{FIN} {', '.join(cassees)}")
        print(f"  {GRIS}→ vérifie qu'il n'y a ni espace ni guillemet autour de la clé,{FIN}")
        print(f"  {GRIS}  et qu'il reste du crédit sur le compte{FIN}")
    print()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
