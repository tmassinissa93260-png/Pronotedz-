# 14 — Reproduire le visuel, les personnages et les voix d'une vidéo

> Ce que fait le système quand tu lui donnes une vidéo et que tu dis
> « je veux le même genre ».

---

## 14.1 Le principe : mesuré d'un côté, interprété de l'autre

Deux natures d'information sortent d'une vidéo, et les mélanger est la faute
qui rend un rapport d'analyse inutilisable.

| | Ce que c'est | Fiabilité | Coût |
|---|---|---|---|
| **Mesuré** | palette, contraste, netteté, grain, cadrage, rythme des coupes, hauteur de voix, timbre, débit | 90 à 99 % | 0 € |
| **Interprété** | qui sont les personnages, à quoi ils ressemblent, quelles règles régissent ce monde | 50 à 85 % | quelques centimes |

Le système ne les confond jamais. La palette de l'univers produit vient de
l'histogramme, pas de ce que le modèle croit avoir vu — un modèle nomme mal
les couleurs, un histogramme non. À l'inverse, aucune mesure ne sait dire
« contours noirs épais, aplats sans dégradé » : ça, c'est le travail du modèle.

Quand les deux se contredisent, **la mesure gagne**. C'est écrit dans le
prompt, et re-vérifié après la réponse.

---

## 14.2 Le visuel : ce qu'on mesure, et à quoi ça sert

`pdz.analyse.visuel` extrait six images-clés — au **milieu** des plans les plus
longs, là où l'image est stable — et mesure :

| Mesure | Comment | Ce que ça pilote |
|---|---|---|
| **Palette** | regroupement par teinte sur 40 000 pixels | la palette de l'univers |
| **Luminosité / contraste / saturation** | luminance perçue (Rec. 601) | `dark low-key lighting`, `high contrast`… |
| **Température** | R−B pondéré par la saturation | `warm color grade` / `cool color grade` |
| **Netteté** | variance du laplacien | distingue le rendu 3D du métrage filmé |
| **Grain** | haute fréquence dans les zones **plates** | `visible film grain` |
| **Cadrage** | centre de masse du gradient | `close-up` / `wide shot framing` |
| **Densité de mouvement** | écart entre images-clés, normalisé par le temps | indique si l'animation vaut le coût |

Deux détails qui font la différence :

- **Le regroupement par teinte plutôt qu'un k-means.** Sur des images d'un même
  univers, un k-means renvoie six nuances du même bleu et rate le rouge d'un
  logo — pourtant identitaire. Regrouper par teinte les sépare par construction.
- **Le grain mesuré dans les zones plates seulement.** Sur un contour, la haute
  fréquence est du dessin, pas du bruit. Sans ce masque, un dessin au trait net
  serait déclaré granuleux.

### La confiance

Si les six images-clés donnent des mesures très dispersées, le style n'est pas
constant : une moyenne unique ne décrirait alors aucune partie de la vidéo.
Le rapport le dit (`confiance 0.34`) au lieu de livrer un chiffre trompeur.

---

## 14.3 Les personnages : décrire assez pour redessiner

L'agent `analyse/charte` regarde les images-clés et rend, pour chaque
personnage vu **au moins deux fois** :

- un identifiant, un nom, une espèce (chaîne libre : « fraise », « vieille 4L ») ;
- une **apparence en anglais de 25 à 45 mots**, visuelle et concrète — matière,
  couleur, forme, proportions, vêtement, posture ;
- son caractère, tel que son attitude le laisse voir ;
- la voix qu'on lui devine (registre + ton).

Une apparence trop courte est **refusée** : si elle ne permet pas de répondre à
« quelle couleur ? quelle forme ? que porte-t-il ? », elle ne permettra pas de
refabriquer le personnage au plan suivant, et la série dérivera.

### Le mode transposition, actif par défaut

Ce module sait décrire un personnage assez précisément pour le refabriquer.
Utilisé tel quel sur une œuvre protégée, il produirait une copie.

Par défaut il **transpose** : il garde ce qui n'appartient à personne —
l'archétype (le lâche charmeur, la manipulatrice), la silhouette générale, le
rapport de forces, le style graphique — et change ce qui identifie : espèce,
nom, costume, couleurs propres au personnage. Un renard escroc en costume
devient un vieux téléphone à clapet cabossé au même caractère.

Il doit alors dire, pour chaque personnage, **ce qui a été gardé et ce qui a
été changé**. S'il ne le dit pas, la réponse est rejetée.

`--fidele` désactive la transposition. À réserver à tes propres vidéos.

Deux filets supplémentaires : le prompt interdit de nommer une œuvre, une
marque ou un studio ; et le validateur de `Style` refuse ensuite un rendu qui
contiendrait malgré tout « naruto », « ghibli » ou « disney ».

---

## 14.4 Les voix : mesurer plutôt que lire des adjectifs

ElevenLabs décrit ses voix par des mots — *warm*, *narrative*, *young*. Ces
mots ne permettent de choisir entre rien.

`pdz.analyse.voix` mesure, sur du signal :

| Mesure | Méthode | Ce que ça règle |
|---|---|---|
| **Hauteur (f0)** | autocorrélation par FFT + interpolation parabolique | le critère n°1 de ressemblance |
| **Étendue mélodique** | p90/p10 en demi-tons | `style` (le jeu) |
| **Timbre** | centroïde spectral des trames voisées | voix sombre ou claire |
| **Débit syllabique** | sommets de l'enveloppe d'énergie, séparés d'un creux ≥ 4 dB | `speed` |
| **Stabilité** | écart-type de f0, en demi-tons | `stability` |

Vérifié sur des sons de hauteur connue : la hauteur est retrouvée **à moins de
2 Hz**, et le débit à 3 % près sur un signal modulé à cadence imposée.

Deux pièges traités explicitement :

- **L'octave.** Avec des harmoniques francs, un détecteur naïf verrouille sur
  2×f0 et annonce une voix aiguë là où elle est grave. L'interpolation
  parabolique et la fenêtre de recherche l'évitent — un test le vérifie.
- **Le creux de 4 dB.** Sans lui, une voyelle tenue est comptée cinq fois et le
  débit triple. La règle du plancher a d'ailleurs été corrigée après mesure :
  un seuil calé sur la médiane surestimait le débit de 50 %.

### L'appariement

`pdz voix apparier <univers> --source <video>` :

1. mesure la voix de la référence ;
2. fait dire **la même phrase** à chaque voix candidate (~110 caractères) ;
3. mesure les candidates exactement pareil ;
4. prend la plus proche dans cet espace de mesures.

Comparer des mesures à des mesures, jamais une mesure à un adjectif. La phrase
sonde est fixe — sinon on comparerait autant les textes que les voix — et
neutre de ton, sinon on mesurerait l'interprétation.

Les sondes sont mises en cache : douze candidates coûtent 1 320 caractères,
**une seule fois dans la vie du projet**.

Deux règles ensuite :

- **Deux personnages ne peuvent pas recevoir la même voix**, même si c'est la
  meilleure pour les deux. Un dialogue où les deux interlocuteurs ont la même
  voix est inécoutable. L'attribution se fait du personnage le plus contraint
  au moins contraint — celui dont la meilleure voix devance nettement sa
  deuxième choisit en premier.
- **Les réglages ne viennent pas tous du même endroit.** `stability` et `style`
  décrivent le jeu voulu : ils viennent de la **cible**. `speed` est une
  correction : c'est le rapport entre le débit visé et le débit naturel de la
  voix retenue. Reprendre aveuglément la vitesse de la cible corrigerait une
  erreur qui n'existe pas.

### Ce que ça ne fait pas

Ça **ne clone pas** une voix : ça en choisit une dans un catalogue existant.
Cloner la voix d'une personne réelle demande son accord — ce n'est pas une
limite technique, c'en est une tout court.

Le module ne sépare pas non plus les locuteurs. Si deux personnes parlent dans
l'extrait, la mesure est une moyenne des deux, c'est-à-dire personne : utilise
`--debut` et `--duree` pour isoler un passage où une seule s'exprime.

---

## 14.5 L'ADN : de la mesure à la contrainte

`pdz.analyse.adn` fait la traduction, **en Python et pas avec un modèle** :

```
médiane des plans = 1,4 s          →  environ 2 plans par réplique
débit = 5,8 syllabes/s             →  199 mots/minute, donc 12 mots/réplique
pics d'énergie à 18 %, 47 %, 79 %  →  relances à ces trois endroits
palette + contraste + grain        →  consignes d'image
```

Passer des nombres exacts à un LLM pour qu'il en ressorte d'autres nombres,
c'est payer pour dégrader une information qu'on avait déjà. Une division ne se
trompe jamais ; un modèle à qui on demande « combien de répliques pour 45
secondes à 190 mots/minute ? » répond un nombre plausible et faux une fois sur
trois.

Deux bornes de sécurité : la durée de plan est ramenée dans [0,8 s ; 4 s] et le
débit dans [110 ; 230] mots/minute. Sans elles, une seule référence au montage
extrême ferait exploser le coût d'un épisode — 150 images pour 45 secondes.

---

## 14.6 Ce que l'analyse ne dira jamais

Cette liste part **avec** chaque rapport. Un rapport chiffré sans elle laisse
croire qu'il explique un succès alors qu'il ne fait que le décrire.

1. **La forme se mesure, la réussite ne s'explique pas.** On n'observe que les
   vidéos qui ont percé, jamais les milliers d'identiques qui n'ont rien fait.
   C'est un biais du survivant, et aucune mesure ne le corrige.
2. **Rien ne dit où les gens décrochaient.** La courbe de rétention n'est pas
   dans le fichier vidéo.
3. **Le sujet et l'écriture ne sont pas transférés.** Ce sont pourtant eux qui
   comptent le plus. Seule la forme l'est.

S'y ajoutent, automatiquement, les mesures dont la confiance est tombée sous
0,6 : elles sont signalées comme ordres de grandeur, pas comme consignes.

---

## 14.7 En pratique

```bash
# 1. Mesurer une vidéo de référence — quelques secondes, 0 €
pdz analyser ma-reference.mp4
#    → str_a1b2c3d4  (la « forme », enregistrée)

# 2. En tirer un univers jouable — quelques centimes
pdz charte ma-reference.mp4 --id mon-monde --nom "Mon Monde"
#    → univers/mon-monde.yaml, personnages et style compris

# 3. Donner à chacun une voix qui ressemble à celle de la référence
pdz voix apparier mon-monde --source ma-reference.mp4

# 4. Produire, en épousant la forme mesurée mais sur MON sujet
pdz episode mon-monde "une dispute pour la dernière place" --forme str_a1b2c3d4
```

Rien à recopier d'une commande à l'autre à la main sauf l'identifiant de forme,
que `pdz analyser` affiche déjà tout prêt.
