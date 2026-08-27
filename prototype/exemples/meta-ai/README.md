# Jeu d'essai : images réelles produites par Meta AI

Ces quatre images ont été fabriquées par **Meta AI**, à partir des prompts photo
générés par ce prototype (`app/output/project.json`), collés à la main.

Elles servent à deux choses :

1. **Preuve que les prompts sont bons.** Les mêmes prompts, donnés à un autre
   générateur, rendent des images justes et cohérentes. Quand une image sortie
   d'ici est mauvaise, c'est le générateur qu'il faut mettre en cause, pas le
   cerveau.
2. **Jeu d'essai pour l'étape `analyser`.** Une image réelle, pas un rendu de
   synthèse approximatif, pour vérifier que l'analyse décrit ce qui est
   vraiment là et que le prompt d'animation qui en découle tient debout.

| Fichier | Plan | Ce que la voix dit |
| --- | --- | --- |
| `shot_01_batterie.jpg` | 1 | l'énergie stockée dans la batterie alimente le système |
| `shot_02_electronique.jpg` | 2 | l'énergie est contrôlée par l'électronique de puissance |
| `shot_03_moteur.jpg` | 3 | l'énergie active le moteur, générant une rotation |
| `shot_04_roues.jpg` | 4 | le moteur entraîne les roues, la voiture se déplace |

## S'en servir

```bash
python -m app.main analyser --shot 3 --image exemples/meta-ai/shot_03_moteur.jpg
```

Ou depuis le workflow : étape `analyser`, champ image
`exemples/meta-ai/shot_03_moteur.jpg`.

## Pour comparaison

Le run `produire` du 27/08 avec `fal-ai/flux/schnell` en 1080×1920 avait rendu,
sur ces mêmes prompts : du texte « L08 » en miroir malgré `no text`, une tige
métallique sortant d'une roue, un rectangle gris posé sur une calandre. C'est
ce constat qui a fait passer le défaut à `fal-ai/flux/dev` en 768×1344.
