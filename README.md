# Pronotedz

Plateforme de gestion scolaire pour les établissements algériens (collège/lycée),
inspirée de Pronote, pour l'administration, les enseignants, les élèves et les parents.

## Fonctionnalités

- Emploi du temps, absences/retards (avec justificatifs), notes/bulletins,
  cahier de texte/devoirs
- Messagerie interne (scopée : un enseignant ne peut contacter que les
  élèves/parents des classes qu'il enseigne réellement)
- Vie scolaire (observations, encouragements, avertissements, sanctions)
- Actualités / kiosque de l'établissement
- Prise de rendez-vous parents-professeurs
- Réservation de salles/matériel
- Espace documents partagés (par classe ou établissement entier)
- Sondages/enquêtes

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

## Déploiement sur Render.com

Le fichier `render.yaml` à la racine décrit un déploiement complet (web
service + base PostgreSQL gratuite) :

1. Créez un compte sur [render.com](https://render.com) (gratuit).
2. Dans le tableau de bord Render : **New** → **Blueprint**, puis connectez
   ce dépôt GitHub.
3. Render détecte `render.yaml` et propose de créer le service web et la
   base de données. Validez.
4. Le build installe les dépendances, exécute les migrations et recrée le
   jeu de données de démonstration (`seed_demo`) automatiquement à chaque
   déploiement.
5. Une fois le déploiement terminé, l'URL fournie par Render (ex.
   `https://pronotedz.onrender.com`) donne accès à l'application avec les
   mêmes comptes de démonstration que ci-dessous.

Limites du plan gratuit à connaître : le service se met en veille après 15
minutes d'inactivité (le premier chargement peut prendre ~30s), et le
stockage de fichiers (photos, justificatifs, documents déposés) n'est pas
persistant entre redéploiements sur ce plan — seules les données en base
(comptes, notes, absences...) le sont.

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
manipulation d'URL, un enseignant ne peut pas contacter les élèves d'une
classe qu'il n'enseigne pas, les doubles réservations sont bloquées), et un
test de fumée par tableau de bord/rôle.
