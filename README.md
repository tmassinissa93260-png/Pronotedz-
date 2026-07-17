# Pronotedz

Plateforme de gestion scolaire pour les établissements algériens (collège/lycée),
inspirée de Pronote : emploi du temps, absences/retards, notes/bulletins et
cahier de texte, pour l'administration, les enseignants, les élèves et les parents.

## Stack

- Django 5.2 + PostgreSQL (SQLite par défaut en local)
- Templates Django server-rendered + Bootstrap 5
- `django-environ` pour la configuration via `.env`

## Installation locale

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo   # jeu de données de démonstration
python manage.py runserver
```

En production, définissez `DATABASE_URL=postgres://user:password@host:5432/pronotedz`
dans `.env` (laissez vide pour utiliser SQLite en local/sandbox).

## Comptes de démonstration

Après `python manage.py seed_demo`, mot de passe commun : **`Pronotedz2026!`**

| Rôle | Identifiant |
|---|---|
| Administration | `admin.direction` |
| Enseignant (Mathématiques) | `prof.mathématiques` |
| Élève | `eleve.202600001` |
| Parent (2 enfants) | `parent.benali` |

Voir la sortie de la commande `seed_demo` pour la liste complète des comptes créés.

## Tests

```bash
python manage.py test
```

Couvre : le calcul des moyennes/bulletins, le scoping des permissions (un
parent ne peut pas accéder aux données d'un enfant qui n'est pas le sien via
manipulation d'URL), et un test de fumée par tableau de bord/rôle.
