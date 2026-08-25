# Phase 11 — Matrice de capacités et gouverneur de coût

## CE QUE CETTE MACHINE SAIT FAIRE, MESURÉ AUJOURD'HUI

```
$ pdz2 capabilities --measure
encodage mesuré : 60 images 320×180 en 0.22s
synthèse mesurée : 4.05s d'audio en 0.015s
aucun adaptateur vidéo déclaré : la matrice n'en invente pas — les stratégies
déterministes locales sont le seul chemin réel
2 entrée(s), 4 capacité(s) mesurée(s), 0 non mesurée(s)

ffmpeg/libx264  [ken_burns, parallax_2_5d, procedural, still]
    ffmpeg version 6.1.1-3ubuntu5 en /usr/bin/ffmpeg
    cost_per_second_usd        0 USD/s          MESURÉE le 2026-08-23
        méthode : binaire local sondé sur le PATH : aucun compte, aucun jeton,
        aucune facturation — le coût monétaire est nul, le coût machine ne l'est pas
    encode_fps            277.58 images/s       MESURÉE le 2026-08-23
        méthode : 60 images 320×180 RGB brutes encodées en H.264, images relues
        par ffprobe
espeak-ng/fr
    eSpeak NG 1.51 en /usr/bin/espeak-ng
    cost_per_second_usd        0 USD/s          MESURÉE le 2026-08-23
    speech_realtime_ratio 272.14 s audio/s machine MESURÉE le 2026-08-23
        méthode : phrase de calibrage de 73 caractères synthétisée, durée lue
        sur les trames du WAV
```

Ces quatre nombres viennent d'outils qui ont réellement tourné pendant la
sonde. Sans `--measure`, `encode_fps` et `speech_realtime_ratio` sortent
`INCONNUE`, **sans valeur** : le contrat interdit de chiffrer ce qui n'a pas
été mesuré.

## ANNOUNCED ≠ MEASURED ≠ UNKNOWN

C'est le §14, et le contrat le tient plutôt que la documentation :

| état | ce que ça veut dire | le contrat exige |
| --- | --- | --- |
| `MEASURED` | vérifié soi-même | une date **et** une méthode **et** une valeur |
| `ANNOUNCED` | le fournisseur le dit | rien — et ce n'est jamais digne de confiance |
| `UNKNOWN` | jamais vérifié, ou périmé | **aucune valeur chiffrée** |

Trois refus au niveau du contrat, pas du moteur :

```python
CapacityValue(name="cost_per_second_usd", value=0.4, provenance=MEASURED,
              method="au doigt mouillé")
# → « cost_per_second_usd : déclarée MEASURED sans date — une capacité non
#     datée est UNKNOWN »

CapacityValue(name="cost_per_second_usd", value=0.4, provenance=MEASURED,
              measured_at=NOW)
# → « ... sans méthode — une mesure se rejoue ou n'existe pas »

CapacityValue(name="cost_per_second_usd", value=0.4, provenance=UNKNOWN)
# → « ... UNKNOWN avec une valeur — on ne chiffre pas ce qu'on ne sait pas »
```

### Une mesure périme

Au-delà de trente jours, `is_stale()` rend vrai et `trustworthy()` rend faux.
Les fournisseurs changent leurs modèles sans prévenir ; une capacité vérifiée
il y a deux mois est une capacité inconnue qui s'ignore. `matrix.stale_values()`
liste exactement ce qu'il faut re-mesurer.

## AUTORISER AVANT, PAS CONSTATER APRÈS

Un compteur qui additionne les dépenses passées ne gouverne rien. Le
`CostGovernor` **autorise** :

```
$ pdz2 costs --episode ep/ --authorize 3.50 --stage render --provider kling --model v2
REFUSÉ [unmeasured_cost] : kling/v2 absent de la matrice de capacités :
on ignore ce que cette dépense coûte
```

Trois refus distincts, parce qu'ils appellent trois réactions différentes :

| refus | situation | quoi faire |
| --- | --- | --- |
| `BUDGET_EXHAUSTED` | il ne reste rien | arrêter |
| `WOULD_EXCEED` | cette dépense-ci passerait au-dessus | la réduire |
| `UNMEASURED_COST` | on ignore ce que ça coûte | mesurer d'abord |

Le troisième est le plus important, et c'est celui qui manque partout
ailleurs. Il se déclenche même quand le budget est intact : un coût seulement
**annoncé** est refusé, un coût **mesuré il y a trois mois** est refusé.
Engager une dépense dont on ignore le montant, c'est perdre le contrôle du
budget d'un seul coup.

`estimate()` suit la même règle : il rend `None` plutôt qu'un chiffre issu
d'une brochure. Une estimation fondée sur une annonce n'est pas une
estimation, c'est un pari.

## LE REGISTRE N'OUVRE PAS UNE SECONDE COMPTABILITÉ

`pdz2 costs` ne tient pas ses propres comptes : il **relit** les transitions
de la machine à états, celles qui portent un coût. Deux comptabilités qui
divergent valent moins qu'une seule qui tient — la même règle que « une seule
timeline audio » en phase 2.

Le contrat `CostLedger` refuse par ailleurs un registre dont le total dépasse
son plafond : un tel objet ne devrait pas pouvoir exister, puisque la dépense
aurait dû être refusée avant d'avoir lieu.

## CE QUE LA MATRICE N'INVENTE PAS

Aucun adaptateur vidéo n'est joignable dans cet environnement, et
`NO_VIDEO_PROVIDERS` est vide. La sonde ne crée donc **aucune entrée** pour
Kling, Veo, Runway ou qui que ce soit : elle le dit et s'arrête là. Le chemin
de code qui sondera un adaptateur réel existe (`_declared_video_providers`) et
sera emprunté dès qu'un adaptateur sera branché ; il traduira son coût annoncé
en `ANNOUNCED`, ce que le gouverneur refusera jusqu'à première facture relevée.

Un test le verrouille : la matrice ne déclare que les stratégies
**réellement implémentées** (`still`, `ken_burns`, `parallax_2_5d`,
`procedural`) et jamais `direct_i2v` ni `3d`.

## COMMANDES

```
pdz2 capabilities [--episode DIR] [--measure]
pdz2 costs --episode DIR [--authorize USD --stage ÉTAPE --provider P --model M]
```

## TESTS — 26

Provenance (7), autorisation et refus (10), sonde réelle (6), registre (3).
Les tests de sonde font tourner ffmpeg et eSpeak NG pour de vrai ; celui qui
exige ffmpeg se saute proprement s'il est absent.
