# 15 — Reconnaître la musique, et savoir pourquoi mes vidéos marchent

---

## 15.1 La musique : `pdz musique`

```bash
pdz musique ma-video.mp4
```

Deux choses, séparées parce qu'elles n'ont ni le même coût ni la même fiabilité.

### Ce qui est mesuré — toujours, gratuitement

| Mesure | Comment | Vérifié |
|---|---|---|
| **Tempo** | autocorrélation de la fonction d'attaque | 90 et 120 BPM retrouvés à 10 % près |
| **Tonalité** | chroma sur 12 classes de hauteur + profils de Krumhansl-Kessler | La mineur retrouvé sur un accord La-Do-Mi |
| **Énergie** | niveau de la musique rapporté au niveau global | — |
| **Passages sans parole** | énergie de modulation à 4 Hz | ne déborde jamais de plus d'1 s sur la parole |

### Ce qui est identifié — quand c'est possible

Le titre du morceau vient d'[AudD](https://audd.io), qui compare une empreinte
acoustique à une base de plus de cent millions de titres. **300
identifications gratuites**, puis environ 5 $ pour 1 000 — un demi-centime.

Shazam n'a pas d'API publique ; AudD est ce qui s'en approche le plus avec une
tarification lisible. ACRCloud fait la même chose et vise plutôt le suivi de
diffusion à grande échelle.

### Le vrai travail : isoler la musique de la voix

Un service de reconnaissance à qui on envoie « voix + musique » se trompe
beaucoup plus souvent. Le programme repère donc d'abord les passages où
personne ne parle et n'envoie que ceux-là.

Pour ça, il fallait savoir reconnaître la parole. **Le détecteur de voisement
écrit pour l'analyse de voix ne convenait pas**, et c'est mesuré : un accord
tenu est parfaitement périodique, sa fondamentale tombe dans le domaine de la
voix parlée, et il est donc déclaré « voisé ». Sur une musique mélodique, ce
détecteur ne trouvait **aucun** passage instrumental.

Le critère retenu est celui de la discrimination parole/musique classique :
**l'énergie de modulation autour de 4 Hz**. La parole ouvre et ferme la bouche
au rythme des syllabes, 3 à 7 fois par seconde ; la musique module au rythme de
la mesure — 2 Hz à 120 BPM — ou pas du tout.

Et là encore, **pas de seuil fixe** : mesuré, la musique seule tombe entre 0,43
et 0,46 selon son tempo, la parole entre 0,51 et 0,66 selon son débit. Un seuil
unique placé au milieu se trompe aux extrêmes. Le seuil est donc calibré sur la
vidéo elle-même, exactement comme celui de la détection des coupes. Quand la
vidéo est homogène — que de la parole, ou que de la musique — il n'y a pas de
frontière à trouver, et le programme le dit au lieu d'en inventer une.

### Ce que ça ne fait pas

- **Trouver une musique qui n'est pas publiée.** Musique libre de droits d'un
  petit catalogue, son fait maison, reprise amateur : introuvables. Un échec ne
  veut pas dire « il n'y a pas de musique ».
- **Donner le droit d'utiliser le morceau.** Identifier n'est pas autoriser.
  C'est justement pour ça que la commande finit par un critère de recherche —
  `120 BPM · La mineur · énergique` — à taper sur une banque de musique libre.

L'appel est facturé même quand rien n'est trouvé. Le garde-fou est donc en
amont : un seul extrait envoyé, le meilleur, et aucun appel du tout quand
aucune musique n'a été détectée.

---

## 15.2 « Pourquoi cette vidéo a percé ? » — ce que j'ai trouvé en cherchant

Tu m'as demandé d'aller voir les outils qui font ça. Je l'ai fait. Voilà le
résultat, sans enjoliver.

### Les outils existent, et ils sont nombreux

Tikalyzer, Viral Hook Analyzer, HookScorer, HookLab, Retti.ai, VidCognition,
Tareno… Ils promettent tous la même chose : tu donnes une vidéo, ils te rendent
une **courbe de rétention**, un **score de hook**, et les endroits où les gens
partent.

### Mais leur courbe de rétention n'est pas une mesure

C'est le point à retenir. Les données de rétention d'une vidéo sont **privées**
et n'appartiennent qu'au compte qui l'a publiée. Aucun outil tiers n'y a accès,
et ces outils ne prétendent d'ailleurs pas le contraire quand on lit les
petites lignes :

- HookScorer parle d'une courbe de rétention **prédite** à partir du script ;
- Retti.ai annonce une courbe **générée par IA**, « avant même que tu regardes
  tes analytics » ;
- les outils qui analysent une chaîne concurrente précisent qu'ils travaillent
  sur des **données publiques**, pas sur les analytics privés.

Autrement dit : ce sont des modèles qui donnent leur avis sur ta vidéo. Ça peut
être utile comme second regard. Ce n'est pas une mesure, et ça ne dit pas
pourquoi la vidéo de quelqu'un d'autre a marché.

### Et le biais qui rend la question insoluble

Même avec la vraie courbe d'une vidéo virale, on ne saurait pas *pourquoi* elle
a marché : on n'observe que les vidéos qui ont percé. Les milliers de vidéos au
hook identique, au même rythme, avec la même musique, qui n'ont rien fait, ne
sont nulle part. Comparer les gagnantes entre elles ne dit rien sur ce qui
sépare une gagnante d'une perdante.

### Où la vraie courbe existe, elle

**Dans TikTok Studio et YouTube Studio, pour tes propres vidéos.** Seconde par
seconde, avec le moment exact où les gens partent. C'est gratuit, c'est exact,
et c'est déjà dans ton compte.

Il faut un compte Créateur ou Business, et l'historique ne remonte qu'à 60
jours — donc il faut exporter régulièrement.

---

## 15.3 La réponse du programme : `pdz resultats`

Plutôt que de deviner pourquoi la vidéo d'un autre a marché, le programme relie
ce qu'il a **décidé** à la production à ce que ton audience a **fait** ensuite.

```bash
# 1. Après avoir publié un épisode
pdz resultats publie job_a1b2c3 --url https://tiktok.com/@moi/video/123

# 2. Une fois par semaine : TikTok Studio → Analytiques → exporter en CSV
pdz resultats importer ~/Téléchargements/export.csv

# 3. Ce qui ressort
pdz resultats bilan
```

Les colonnes de l'export sont reconnues automatiquement — français ou anglais,
n'importe quel ordre. Les nombres aussi : `12 345`, `1.2K`, `43 %`, `00:00:07`.

Les réglages comparés sont ceux que le système peut changer la fois d'après :

- la longueur de la première réplique ;
- le nombre de prises de parole ;
- la durée de l'épisode et la durée moyenne d'un plan ;
- le nombre de plans animés par un modèle vidéo ;
- le nombre de relances narratives ;
- une émotion forte dès la première réplique, ou non.

### Sur ton catalogue, le biais du survivant disparaît

C'est tout l'intérêt. Tes épisodes ratés sont là aussi, dans la même base, avec
les mêmes mesures. La comparaison porte enfin sur les deux moitiés de la
population, pas seulement sur les gagnants.

### Deux règles tenues strictement

**1. Aucune conclusion sous 10 épisodes publiés.** En dessous, l'écart entre
deux groupes est indiscernable du hasard. Un test vérifie ce refus : cinq
épisodes avec un écart énorme et parfaitement net ne doivent produire **aucune**
leçon. Un outil qui annonce « les hooks courts marchent 40 % mieux » sur cinq
vidéos est plus nuisible que pas d'outil du tout.

**2. On dit « associé à », jamais « fait que ».** Un hook court et une bonne
rétention peuvent tous deux venir d'un meilleur sujet. Le tableau range, il
n'explique pas — et l'avertissement part avec le tableau, il n'est pas
affichable seul.

### Ce que ça ne mesurera jamais

Le sujet et l'écriture. Ce sont eux qui pèsent le plus, et ils ne se réduisent
pas à un nombre. Tout ce que ce module compare, ce sont des réglages de forme —
utile pour arrêter de se tromper sur la forme, insuffisant pour faire une bonne
vidéo.

---

## Sources

- [Best Music Recognition APIs in 2026 — AudD](https://audd.io/resources/articles/best-music-recognition-apis.html)
- [ACRCloud vs AudD vs Shazam — comparatif 2026](https://trackradar.ai/compare/acrcloud-vs-audd-vs-shazam)
- [Song Recognition API Pricing 2026 — AUTOVJCLUB](https://autovj.club/en/guide/song-recognition/)
- [AudD Music Recognition API Docs](https://docs.audd.io/)
- [10 Best Retention Graph Analyzers — OpusClip](https://www.opus.pro/blog/best-retention-graph-analyzers)
- [HookScorer — AI YouTube Hook Analyzer](https://hookscorer.com/)
- [Retti.ai — YouTube Retention Analysis](https://retti.ai/youtube-retention-analysis)
- [TikTok Analytics : guide complet 2026](https://socialhunt.co/resources/tiktok-analytics-complete-guide)
- [TikTok Retention Rate Benchmarks 2026](https://retensis.com/blog/tiktok-retention-rate-benchmarks-2026)
- [How to Export TikTok Analytics — Graphed](https://www.graphed.com/blog/how-to-export-tiktok-analytics)
