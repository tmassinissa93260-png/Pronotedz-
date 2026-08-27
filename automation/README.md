# autopilot

Petit prototype d'automatisation **locale**. Un fichier de règles décrit quoi
surveiller et quoi faire ; le moteur applique la première règle qui correspond
à chaque fichier.

Indépendant du reste du dépôt : aucun import de `pdz` ou `pdz2`, **aucune
dépendance externe** (Python 3.11 et sa bibliothèque standard).

## Démarrage

```bash
cd automation
python autopilot.py init                 # écrit rules.json (exemple commenté)
$EDITOR rules.json                       # adapte watch_dir et les règles
python autopilot.py run --dry-run        # montre ce qui se passerait, sans rien toucher
python autopilot.py run                  # applique
python autopilot.py watch --interval 5   # boucle jusqu'à Ctrl-C
```

`--dry-run` marche aussi sur `watch`. Commence toujours par là.

## Fichier de règles

```json
{
  "watch_dir": "~/Downloads",
  "log_file": "autopilot.log.jsonl",
  "recursive": false,
  "skip_hidden": true,
  "settle_seconds": 2,
  "rules": [
    {
      "name": "Images vers Photos/AAAA-MM",
      "match": { "ext": ["jpg", "png"] },
      "action": { "type": "move", "dest": "~/Photos/{year}-{month}" }
    }
  ]
}
```

| Champ | Rôle |
| --- | --- |
| `watch_dir` | dossier surveillé (`~` accepté ; un chemin relatif part du fichier de règles) |
| `log_file` | journal JSONL des actions appliquées ; omis = pas de journal |
| `recursive` | descendre dans les sous-dossiers (défaut `false`) |
| `skip_hidden` | ignorer les fichiers commençant par `.` (défaut `true`) |
| `settle_seconds` | ignorer un fichier modifié il y a moins de N secondes, pour ne pas attraper un téléchargement en cours |

### Critères (`match`)

Tous les critères présents doivent passer. Un `match` vide accepte tout.

| Critère | Exemple | Effet |
| --- | --- | --- |
| `ext` | `["pdf", ".JPG"]` | extension, insensible à la casse et au point initial |
| `glob` | `"rapport-*.pdf"` | motif sur le nom de fichier |
| `exclude_glob` | `"20??-??-??-*"` | écarte les noms qui collent au motif |
| `name_contains` | `"facture"` | sous-chaîne, insensible à la casse |
| `min_size_kb` / `max_size_kb` | `500` | taille du fichier |
| `older_than_days` | `7` | âge minimum depuis la dernière modification |

### Actions (`action`)

| `type` | Champs | Effet |
| --- | --- | --- |
| `move` | `dest` | déplace vers `dest` (créé si absent) |
| `copy` | `dest` | copie, source conservée |
| `rename` | `template` | renomme sur place, dans le même dossier |
| `delete` | — | supprime |
| `run` | `command` | lance une commande (liste d'arguments ou chaîne) |

`dest`, `template` et chaque argument de `command` acceptent des variables :
`{name}` `{stem}` `{ext}` `{parent}` `{path}` `{date}` `{year}` `{month}` `{day}`
(les dates viennent de la date de modification du fichier).

```json
{ "name": "Miniature", "match": { "ext": ["png"] },
  "action": { "type": "run", "command": ["convert", "{path}", "-resize", "50%", "{parent}/mini-{name}"] } }
```

### Le piège du `rename` en boucle

En mode `watch`, une règle `rename` repasse sur le fichier qu'elle vient de
renommer. `exclude_glob` est là pour ça : la règle écarte ses propres sorties.

```json
{ "name": "Factures horodatées",
  "match": { "ext": ["pdf"], "name_contains": "facture",
             "exclude_glob": "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-*" },
  "action": { "type": "rename", "template": "{date}-{stem}.{ext}" } }
```

Sans ça : `facture.pdf` → `2026-08-27-facture.pdf` → `2026-08-27-2026-08-27-facture.pdf`…
En filet de sécurité, un `rename` dont le gabarit redonne le nom actuel est
signalé `skip` (`=` à l'écran) plutôt que suffixé en `-1`.

Une règle avec `"enabled": false` est ignorée — pratique pour garder une règle
destructrice sous le coude sans qu'elle tourne.

## Garde-fous

- **Rien n'est jamais écrasé** : si la cible existe, le fichier devient `nom-1.ext`, `nom-2.ext`…
- **`--dry-run`** n'écrit rien, journal compris.
- Une règle qui échoue est journalisée en `error` et **n'interrompt pas la passe**.
- `rename` refuse un `template` contenant `/` ou `\` : il renomme, il ne déplace pas.
- Les commandes `run` sont exécutées **sans shell** (pas d'interprétation de `|`, `>`, `*`).
- `run` en échec (code retour ≠ 0) est journalisé, jamais relancé automatiquement.

Code de sortie : `0` tout va bien, `1` au moins une action en erreur, `2` fichier
de règles invalide — utilisable tel quel dans cron ou un timer systemd.

## Journal

Une ligne JSON par action appliquée :

```json
{"time":"2026-08-27T09:12:04+00:00","rule":"Images","action":"move","file":"/home/moi/Downloads/a.jpg","dry_run":false,"status":"ok","target":"/home/moi/Photos/2026-08/a.jpg"}
```

## Tests

```bash
cd automation
python -m unittest discover -s tests
```

## Le lancer en fond

`watch` suffit pour un prototype. Pour du périodique sans processus résident,
préfère `run` via cron :

```cron
*/10 * * * * cd /chemin/vers/automation && /usr/bin/python3 autopilot.py run --config rules.json
```

## Limites assumées

Prototype : scrutation par intervalle (pas d'`inotify`), pas de reprise après
interruption, pas de corbeille (`delete` supprime vraiment), une seule règle
appliquée par fichier et par passe.
