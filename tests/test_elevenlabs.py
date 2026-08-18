"""Regroupement des timings ElevenLabs en mots.

L'appel réseau n'est pas testable ici (la politique réseau de l'environnement
bloque api.elevenlabs.io), mais la partie qui compte — transformer
l'alignement caractère par caractère en mots datés — l'est entièrement.
"""

from pdz.ia.elevenlabs import mots_depuis_alignement


def _align(texte: str, pas: float = 0.1) -> dict:
    """Fabrique un alignement où chaque caractère dure `pas` secondes."""
    return {
        "characters": list(texte),
        "character_start_times_seconds": [i * pas for i in range(len(texte))],
        "character_end_times_seconds": [(i + 1) * pas for i in range(len(texte))],
    }


def test_les_mots_sont_reconstitues():
    mots = mots_depuis_alignement(_align("Un bip court"))
    assert [m.texte for m in mots] == ["Un", "bip", "court"]


def test_les_bornes_collent_aux_caracteres():
    mots = mots_depuis_alignement(_align("ab cd", pas=0.1))
    # "ab" = caractères 0-1 → 0 à 200 ms ; "cd" = caractères 3-4 → 300 à 500 ms
    assert (mots[0].debut_ms, mots[0].fin_ms) == (0, 200)
    assert (mots[1].debut_ms, mots[1].fin_ms) == (300, 500)


def test_les_espaces_multiples_ne_creent_pas_de_mots_vides():
    mots = mots_depuis_alignement(_align("a   b"))
    assert [m.texte for m in mots] == ["a", "b"]


def test_la_ponctuation_reste_collee_au_mot():
    """Elle doit rester dans le mot : c'est elle qui déclenche la coupure de carte."""
    mots = mots_depuis_alignement(_align("Bien. Mais"))
    assert [m.texte for m in mots] == ["Bien.", "Mais"]


def test_un_alignement_incoherent_est_ignore_sans_planter():
    assert mots_depuis_alignement({}) == []
    assert mots_depuis_alignement({"characters": ["a", "b"],
                                   "character_start_times_seconds": [0.0],
                                   "character_end_times_seconds": [0.1]}) == []


def test_les_pauses_font_deriver_lestimation():
    """C'est là que les timings réels changent quelque chose.

    Notre estimation répartit la durée au prorata de la longueur des mots.
    Elle est correcte sur un débit régulier — mais une voix marque une pause
    après une virgule ou un point, et aucune estimation ne peut le deviner.
    L'écart s'accumule : mesuré à 271 ms sur une phrase de 6 s à deux pauses,
    soit un karaoké qui décroche visiblement en fin de phrase.
    """
    from pdz.video.soustitres import mots_depuis_texte

    phrase = "Attends, c'est pas ce que tu crois. Ecoute moi, je te jure."

    # Alignement réaliste : 550 ms de silence après chaque ponctuation forte.
    debuts, fins, t = [], [], 0.0
    for i, c in enumerate(phrase):
        debuts.append(t)
        pause = c == " " and i > 0 and phrase[i - 1] in ",.!?"
        t += 0.55 if pause else 0.075
        fins.append(t)

    reels = mots_depuis_alignement({
        "characters": list(phrase),
        "character_start_times_seconds": debuts,
        "character_end_times_seconds": fins,
    })
    estimes = mots_depuis_texte(phrase, 0, round(t * 1000))

    ecart_max = max(abs(a.debut_ms - b.debut_ms)
                    for a, b in zip(reels, estimes, strict=True))
    assert ecart_max > 200, f"écart attendu en fin de phrase, mesuré {ecart_max} ms"


# ── Classement des 401 ───────────────────────────────────────────────────
#
# Mesuré en production (run #75) : deux répliques synthétisées avec succès,
# puis 401 sur la troisième — et l'épisode s'arrête sur « Vérifie
# ELEVENLABS_API_KEY dans .env. » Une clé refusée échoue à la PREMIÈRE
# requête, jamais à la troisième : le diagnostic envoyait chercher un
# problème inexistant, et jetait la seule explication disponible, celle
# qu'ElevenLabs renvoie dans le corps de sa réponse.

import httpx
import pytest

from pdz.ia.elevenlabs import _lever
from pdz.moteur.erreurs import ErreurConfig, ErreurQuota


def _401(statut: str | None, message: str = "") -> httpx.Response:
    corps = {"detail": {"status": statut, "message": message}} if statut else {}
    return httpx.Response(
        401, json=corps,
        request=httpx.Request("POST", "https://api.elevenlabs.io/v1/text-to-speech/x"),
    )


def test_un_401_de_quota_nest_pas_un_probleme_de_cle():
    """`ErreurQuota`, pas `ErreurConfig` : la clé est bonne, l'arrêt n'est pas
    définitif, et le repli garde un sens."""
    with pytest.raises(ErreurQuota) as e:
        _lever(_401("quota_exceeded", "You have 12 credits remaining"))
    assert "Crédits ElevenLabs épuisés" in str(e.value)
    assert "ELEVENLABS_API_KEY" not in str(e.value)
    assert "12 credits remaining" in str(e.value), "le détail du fournisseur doit survivre"


def test_un_401_dactivite_inhabituelle_explique_le_runner():
    """Le cas le plus probable ici : ElevenLabs coupe le palier gratuit quand
    les requêtes viennent d'une IP de centre de données — ce qu'est un runner
    GitHub Actions."""
    with pytest.raises(ErreurQuota) as e:
        _lever(_401("detected_unusual_activity", "Free Tier usage disabled"))
    assert "palier gratuit" in str(e.value)
    assert "GitHub Actions" in str(e.value)


def test_un_vrai_401_de_cle_reste_une_erreur_de_config():
    """Non-régression : quand la clé EST en cause, le message d'avant reste,
    et il reste actionnable."""
    with pytest.raises(ErreurConfig) as e:
        _lever(_401("invalid_api_key", "Invalid API key"))
    assert "ELEVENLABS_API_KEY" in str(e.value)


def test_un_401_sans_corps_exploitable_accuse_toujours_la_cle():
    """Sans explication du fournisseur, l'hypothèse de la clé reste la bonne
    par défaut — mais elle ne doit plus être la SEULE."""
    with pytest.raises(ErreurConfig):
        _lever(_401(None))


def test_un_401_au_corps_illisible_ne_plante_pas():
    r = httpx.Response(
        401, text="<html>gateway</html>",
        request=httpx.Request("POST", "https://api.elevenlabs.io/v1/text-to-speech/x"),
    )
    with pytest.raises(ErreurConfig):
        _lever(r)


def test_une_reponse_valide_ne_leve_rien():
    _lever(httpx.Response(
        200, request=httpx.Request("GET", "https://api.elevenlabs.io/v1/voices")))
