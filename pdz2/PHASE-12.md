# Phase 12 — Journal de production

## POURQUOI CETTE VIDÉO EST-ELLE COMME ÇA ?

C'est la question à laquelle il faut savoir répondre six mois plus tard. Un
épisode qu'on ne peut pas expliquer après coup n'est pas reproductible : il
est simplement arrivé.

```
$ pdz2 journal --episode ep/ --probe
épisode ep — Comment fonctionne une voiture électrique ?
  état     : delivered
  début    : 2026-08-22 14:00:04
  fin      : 2026-08-23 12:42:56 (81772s)
  dépensé  : 0.0000 USD
  outils   : ffmpeg : ffmpeg version 6.1.1-3ubuntu5 ; espeak-ng : eSpeak NG 1.51

  décision   9
  DÉGRADÉ    6
  CONSTAT    6
  capacité   2
  LIMITE     3

  08-22 14:00:24 [décision ] direction   director_brief-9762dcce
             brief de réalisation par human
  08-22 14:00:24 [LIMITE   ] visual_bible
             style visuel non décidé
  08-23 04:08:14 [DÉGRADÉ  ] routing     S00
             [perceptual] provider_availability : génération vidéo par IA →
             stratégie déterministe locale
  …

15 point(s) non résolu(s) — à lire avant de publier :
  [LIMITE] style visuel non décidé
  [LIMITE] aucun timing de mot mesuré
  [CONSTAT] provider_capability [minor]
```

## LE JOURNAL SE RELIT, IL NE S'ÉCRIT PAS

C'est la décision de conception de cette phase, et elle est la seule qui rende
le journal utile.

Un journal **tenu au fil de l'eau** diverge de la production dès la première
reprise : une étape rejouée, un contrat remplacé, un processus interrompu, et
le récit ne correspond plus aux fichiers. Il faudrait alors choisir à qui
faire confiance — et un journal auquel on ne fait pas confiance ne sert à rien.

Un journal **reconstruit** depuis le dossier d'épisode ne peut pas mentir :

| entrée du journal | contrat d'où elle vient |
| --- | --- |
| `DÉGRADÉ` | `render_spec_executable.degradations` |
| `CONSTAT` | `observation_report.checks` en échec, `temporal_plan.findings` |
| `REFUS` | `validation_report.issues` bloquantes, transitions `failed` |
| `décision` | `director_brief`, stratégie de chaque `render_spec_executable` |
| `dépense` | transitions de la machine à états portant un coût |
| `capacité` | sonde de la phase 11, datée |
| `LIMITE` | ce que la chaîne sait ne pas savoir faire |

Deux tests verrouillent la propriété dans les deux sens : chaque dégradation
déclarée dans un contrat apparaît au journal, et supprimer les contrats les
fait disparaître du journal. Le journal est une **vue**, pas une source.

## LES LIMITES SONT DÉCLARÉES, PAS MASQUÉES

Trois limites remontent d'elles-mêmes sur l'épisode de référence :

- **style visuel non décidé** — le brief n'a pas tranché, un préréglage
  déclaré a été appliqué selon le ton ; l'épisode n'a pas de parti pris qui
  lui soit propre.
- **aucun timing de mot mesuré** — eSpeak NG ne rend pas de marques de mot
  exploitables ; rien n'est calé à la syllabe.
- **sous-titres calés au caractère** — le découpage des cartons est
  proportionnel au nombre de caractères, faute de timings de mots.

Aucune de ces trois n'est un bug corrigé en silence. Elles sont dans le
livrable, et le journal les met sous les yeux de qui doit décider de publier.

## `unresolved` : CE QU'IL FAUT LIRE AVANT DE PUBLIER

La propriété `unresolved` réunit les constats, les dégradations et les limites
— tout ce que personne n'a corrigé. Sur l'épisode de référence : 15 points.
C'est le seul endroit du système où un humain reçoit, en un bloc, ce que les
machines ont dû accepter.

    HUMANS JUDGE WHAT MACHINES CANNOT MEASURE

## CE QUE LE JOURNAL EMPORTE POUR PLUS TARD

- `contract_versions` — les 37 contrats et leurs versions, pour relire
  l'épisode quand les contrats auront bougé.
- `tool_versions` — versions réelles de ffmpeg et d'eSpeak NG, **lues** sur les
  binaires, jamais supposées.
- `transitions` — le journal complet de la machine à états.
- `parent_id` — l'instantané d'épisode d'où le journal a été tiré.

## LE CONTRAT REFUSE UN RÉCIT INCOHÉRENT

- entrées dans le désordre → refus (« journal : entrées dans le désordre ») ;
- fin avant début → refus ;
- entrée sans fuseau horaire → refus.

Un journal qui accepterait un ordre faux ferait croire à des causalités
inversées, ce qui est pire que pas de journal du tout.

## LA CHAÎNE ENTIÈRE, EN UNE COMMANDE

Les douze phases étant en place, `pdz2 create` les enchaîne :

```
$ pdz2 create --episode ep2/ --topic "Comment fonctionne une voiture électrique ?" \
              --corpus docs/ --brief ep2/brief.json
=== pdz2 research — déjà fait, sauté
=== pdz2 direct  … capabilities … script … voice … timeline … bible … shots …
    motion … specs … validate … route … assets … render … observe … diagnose …
    edit … master … subtitle … deliver … costs … journal

8 plans concaténés sans ré-encodage vidéo
27.440s, 1080×1920, 30.00 i/s, 2626 Kio
  [ok  blocking] final_duration   observé 27.44     attendu 27.44
  [ok  blocking] final_format     observé 0.5625    attendu 0.5625
  [ok  blocking] final_has_audio  observé 1.0       attendu 1.0
  [ok  blocking] final_not_black  observé 0.0       attendu 0.0
  [ok  minor   ] final_loudness   observé -16.13    attendu -14.0
  [ok  major   ] final_true_peak  observé -1.49     attendu -1.5
  [ok  major   ] final_not_frozen observé 0.005092  attendu 0.001

19 point(s) non résolu(s) — à lire avant de publier
ÉPISODE PRODUIT : ep2/final.mp4
```

Vérifié par `ffprobe` : H.264 1080×1920 à 30 i/s, AAC 48 kHz, 27,44 s,
2 690 045 octets.

L'orchestrateur n'a aucune intelligence propre : il appelle les commandes de
phase dans l'ordre du graphe et s'arrête à la première qui refuse. Deux
comportements méritent d'être notés.

**Il saute ce qui est déjà fait.** Rejouer une étape terminée exige un
rembobinage explicite — la machine à états le refuse, à juste titre. Reprendre
`create` après avoir rempli le brief est pourtant le parcours normal :
l'orchestrateur saute donc les étapes `DONE` et le dit, plutôt que de buter.

**Il s'arrête devant le brief.** Sans brief rempli, `create` fait la recherche,
écrit le gabarit avec les éléments réellement trouvés, et rend la main avec le
code 3. Ce n'est pas un refus par manque d'implémentation : c'est la seule
décision de la chaîne qu'aucune mesure de ce système ne prend.

    HUMANS JUDGE WHAT MACHINES CANNOT MEASURE

## COMMANDE

```
pdz2 journal --episode DIR [--probe] [-q] [-v]
```

`--probe` sonde en plus l'environnement et date ses capacités dans le journal.

## TESTS — 13, plus l'orchestrateur

Journal : reconstruction depuis le dossier (4), propagation dans les deux sens
(2), constats, refus, dépenses et capacités (4), invariants du contrat (3).

Orchestrateur : l'arrêt volontaire devant le brief, la reprise qui saute une
étape déjà faite, et un test qui vérifie que `create` couvre **toutes** les
étapes du graphe sauf `FINAL_QA` (franchie par `deliver`) et `REPAIR` (qui ne
se déclenche que sur diagnostic).
