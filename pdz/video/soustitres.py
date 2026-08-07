"""Sous-titres karaoké au format ASS — le mot s'allume quand il est prononcé.

C'est un standard absolu du vertical, pas une option : beaucoup de vidéos
démarrent sans le son, les sous-titres sont donc le canal principal des
premières secondes.

Aucune IA ici, aucun coût : c'est du calcul de temps. FFmpeg les incruste
avec libass.

Voir docs/11-etat-de-lart.md § 11.5.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Mot:
    texte: str
    debut_ms: int
    fin_ms: int

    @property
    def duree_cs(self) -> int:
        """Durée en centisecondes — l'unité des balises karaoké ASS."""
        return max(1, round((self.fin_ms - self.debut_ms) / 10))


@dataclass
class StyleSousTitres:
    police: str = "DejaVu Sans"
    taille: int = 92
    couleur: str = "&H00FFFFFF"          # blanc — ASS est en &HAABBGGRR
    couleur_active: str = "&H0000E5FF"   # jaune vif : le mot en cours
    contour: str = "&H00000000"
    epaisseur_contour: float = 5.0
    ombre: float = 2.0
    gras: bool = True

    # Position verticale, en part de la hauteur. 0,62 place le texte au-dessus
    # des boutons de l'interface TikTok — sinon il passe dessous et devient
    # illisible sur la moitié des lectures.
    position_ratio: float = 0.62

    mots_par_carte: int = 3              # 3 mots à l'écran : le repère du vertical
    marge_laterale: int = 90
    majuscules: bool = False             # style documentaire : tout en capitales

    # Largeur moyenne d'un caractère, en part de la taille de police. Mesuré
    # sur DejaVu Sans Bold en capitales. Sert à rétrécir les mots trop longs
    # plutôt que de les laisser déborder de l'écran.
    largeur_caractere: float = 0.62

    def taille_pour(self, texte: str, largeur_ecran: int) -> int:
        """Réduit la police si le texte déborderait.

        Un mot qui sort du cadre est un défaut visible immédiatement — et il
        arrive dès qu'on affiche un mot à la fois (« quatre-vingt-trois »).
        """
        utile = largeur_ecran - 2 * self.marge_laterale
        besoin = len(texte) * self.taille * self.largeur_caractere
        if besoin <= utile:
            return self.taille
        return max(48, int(self.taille * utile / besoin))


@dataclass
class Carte:
    """Un groupe de mots affichés ensemble."""

    mots: list[Mot] = field(default_factory=list)

    @property
    def debut_ms(self) -> int:
        return self.mots[0].debut_ms

    @property
    def fin_ms(self) -> int:
        return self.mots[-1].fin_ms


def decouper_en_cartes(mots: list[Mot], par_carte: int = 3) -> list[Carte]:
    """Groupe les mots par paquets lisibles.

    Une coupure est forcée sur la ponctuation forte : afficher « bien. Mais »
    ensemble casse la lecture.
    """
    cartes: list[Carte] = []
    courante: list[Mot] = []

    for mot in mots:
        courante.append(mot)
        fin_de_phrase = mot.texte.rstrip()[-1:] in ".!?…"
        if len(courante) >= par_carte or fin_de_phrase:
            cartes.append(Carte(courante))
            courante = []

    if courante:
        cartes.append(Carte(courante))
    return cartes


def _ass_temps(ms: int) -> str:
    """0:00:01.23 — le format de temps ASS, au centième."""
    cs = round(ms / 10)
    h, reste = divmod(cs, 360000)
    m, reste = divmod(reste, 6000)
    s, cs = divmod(reste, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def generer_ass(mots: list[Mot], *, largeur: int = 1080, hauteur: int = 1920,
                style: StyleSousTitres | None = None) -> str:
    """Produit un fichier ASS complet, prêt pour `ffmpeg -vf ass=...`."""
    st = style or StyleSousTitres()
    cartes = decouper_en_cartes(mots, st.mots_par_carte)

    # ASS positionne depuis le bas quand l'alignement est 2 (bas-centre).
    marge_basse = round(hauteur * (1 - st.position_ratio))

    entete = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {largeur}
PlayResY: {hauteur}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,{st.police},{st.taille},{st.couleur_active},{st.couleur},{st.contour},&H00000000,{-1 if st.gras else 0},0,0,0,100,100,0,0,1,{st.epaisseur_contour},{st.ombre},2,{st.marge_laterale},{st.marge_laterale},{marge_basse},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lignes = []
    for carte in cartes:
        mots_carte = [
            Mot(m.texte.upper() if st.majuscules else m.texte, m.debut_ms, m.fin_ms)
            for m in carte.mots
        ]
        brut = " ".join(m.texte for m in mots_carte)
        # \k<centisecondes> : libass colore le mot pendant sa durée.
        texte = "".join(f"{{\\k{m.duree_cs}}}{m.texte} " for m in mots_carte).strip()

        # Rétrécissement au cas par cas si le texte dépasserait du cadre.
        taille = st.taille_pour(brut, largeur)
        if taille != st.taille:
            texte = f"{{\\fs{taille}}}" + texte

        lignes.append(
            f"Dialogue: 0,{_ass_temps(carte.debut_ms)},{_ass_temps(carte.fin_ms)},"
            f"Karaoke,,0,0,0,,{texte}"
        )

    return entete + "\n".join(lignes) + "\n"


def mots_depuis_texte(texte: str, debut_ms: int, duree_ms: int) -> list[Mot]:
    """Répartit les mots d'une réplique sur sa durée.

    Approximation utilisée tant qu'on n'a pas les vrais timings d'ElevenLabs :
    la durée est distribuée au prorata de la longueur des mots, ce qui colle
    mieux que de la répartir également.
    """
    decoupe = texte.split()
    if not decoupe:
        return []

    poids = [max(1, len(m)) for m in decoupe]
    total = sum(poids)

    mots: list[Mot] = []
    curseur = debut_ms
    for mot, p in zip(decoupe, poids, strict=True):
        part = round(duree_ms * p / total)
        mots.append(Mot(mot, curseur, curseur + part))
        curseur += part

    mots[-1].fin_ms = debut_ms + duree_ms   # rattrape les arrondis
    return mots
