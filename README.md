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
- QCM interactifs avec correction automatique
- Devoirs : dépôt en ligne par l'élève + correction par l'enseignant
- Notifications in-app + email (absences, nouveaux messages, notes publiées),
  architecture prête pour l'ajout futur de SMS/WhatsApp
- Accusés de lecture sur les actualités (suivi par publication côté admin)
- Import CSV des comptes élèves/enseignants/parents
- Mode sombre/clair et interface bilingue français/arabe avec bascule RTL
- Multi-tenant réel : plusieurs établissements totalement isolés dans la
  même base (chaque compte, classe, année scolaire, actualité, sondage...
  est rattaché à un seul établissement, y compris dans Django admin)

## Stack

- Django 5.2 + PostgreSQL (SQLite par défaut en local)
- Templates Django server-rendered + Bootstrap 5 (build RTL inclus pour l'arabe)
- `django-environ` pour la configuration via `.env`
- `reportlab` pour la génération des bulletins PDF

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

`seed_demo` crée aussi un **second établissement** isolé (Collège El Amir
Abdelkader, admin `admin.oran`) avec sa propre année scolaire, classe et
comptes — pour démontrer et tester que rien ne fuite d'un établissement à
l'autre (dashboard, messagerie, actualités, sondages, import CSV, et
Django admin).

## Langue et RTL

Le sélecteur de langue (bouton FR/AR dans l'en-tête et sur la page de
connexion) bascule l'interface entre le français et l'arabe, avec passage
automatique en RTL (feuille de style Bootstrap dédiée). Pour régénérer les
fichiers de traduction après avoir ajouté du texte dans les templates :

```bash
python manage.py makemessages -l fr -l ar --no-location \
  --ignore="venv/*" --ignore="static/vendor/*" --ignore="staticfiles/*"
# éditer locale/ar/LC_MESSAGES/django.po
python manage.py compilemessages
```

## Fonctionnalités IA (optionnel)

L'assistant IA élève (et les futurs générateur de QCM / appréciations assistées)
utilisent l'API Claude d'Anthropic. Sans clé configurée, ces fonctionnalités
affichent un message explicatif au lieu de planter — l'application entière
fonctionne normalement sans elles.

Pour les activer, définissez dans `.env` :

```
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-opus-4-8   # optionnel, valeur par défaut
```

Chaque établissement a un budget mensuel de tokens configurable par l'admin
(modèle `BudgetIA`, visible dans `/admin/`) pour maîtriser les coûts API.

## Tests

```bash
python manage.py test
```

Couvre : le calcul des moyennes/bulletins, le scoping des permissions (un
parent ne peut pas accéder aux données d'un enfant qui n'est pas le sien via
manipulation d'URL, un enseignant ne peut pas contacter les élèves d'une
classe qu'il n'enseigne pas, les doubles réservations sont bloquées), et un
test de fumée par tableau de bord/rôle.
