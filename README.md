# My Social Networks API

## 1. Contexte et objectifs

Ce projet a été réalisé dans le cadre du cours « API & Web Services » (Master Data Engineering). Le sujet consiste à concevoir une API REST permettant de supporter un nouveau service de type réseau social, en respectant des besoins fonctionnels précis (utilisateurs, groupes, événements, discussions, médias, sondages, billetterie) tout en étant force de proposition lorsque certains comportements ne sont pas entièrement spécifiés.

L’objectif principal est de livrer une API cohérente, documentée, testable via Swagger, et sécurisée par des validations métier et des contrôles d’accès.

---

## 2. Stack technique

- Framework : FastAPI
- ORM : SQLAlchemy
- Base de données : SQLite
- Authentification : JWT Bearer Token
- Documentation : OpenAPI/Swagger (générée automatiquement)

---

## 3. Démarrage du projet

### 3.1. Installation des dépendances

Créer et activer un environnement virtuel, puis installer les dépendances :

```bash
python -m venv .venv
source .venv/bin/activate   # macOS / Linux
.venv\Scripts\activate      # Windows

pip install -r requirements.txt
```
Le fichier requirements.txt a été généré via pip freeze afin de garantir la reproductibilité exacte de l’environnement d’exécution.
### 3.2. Lancement de l'API
```bash
uvicorn app.main:app --reload
```

* API : http://127.0.0.1:8000
* Documentation Swagger : http://127.0.0.1:8000/docs

---

## 4. Authentification

L'API utilise un schéma JWT de type Bearer.

1. Créer un utilisateur :
   * `POST /auth/register`
2. Se connecter :
   * `POST /auth/login` (retourne un `access_token`)
3. Dans Swagger, cliquer sur « Authorize » et renseigner :
   * `Bearer <access_token>`

Certaines routes sont publiques (ex. consultation d'événements publics, achat de billet), tandis que d'autres exigent un token.

---

## 5. Modèle fonctionnel 

### 5.1 Utilisateurs

* Inscription, connexion, récupération du profil courant.
* Contrainte : unicité de l'email.

### 5.2 Groupes

* Paramètres : type (public/privé/secret), autorisation de publication par les membres, autorisation de création d'événements par les membres, icône, cover.
* Relations : membres (1..n), administrateurs (1..n), avec la règle « au moins un administrateur ».

### 5.3 Événements

* Paramètres : nom, description, date de début, date de fin, lieu, cover, public/privé, rattachement optionnel à un groupe.
* Relations : participants (0..n), organisateurs (1..n).
* Accès :
   * événement public : visible par tous
   * événement privé : visible uniquement par organisateurs, participants, ou membres du groupe rattaché le cas échéant

### 5.4 Discussions et messages

* Une discussion est liée soit à un groupe, soit à un événement (contrainte d'exclusivité).
* Les messages sont postés par les membres/participants autorisés.
* Les messages supportent des réponses (threading) via `parent_message_id`, permettant de répondre à un message précis au sein d'une même discussion.

### 5.5 Albums photo, photos, commentaires

* Un album est associé à un événement.
* Les photos et commentaires sont réservés aux participants/organisateurs selon les droits d'accès à l'événement.

### 5.6 Sondages

* Les sondages sont créés par les organisateurs d'un événement.
* Chaque question possède plusieurs options ; un participant choisit une seule option par question.
* Contrainte : un utilisateur ne peut voter qu'une fois par question.

### 5.7 Billetterie (événements publics)

* Disponible uniquement pour les événements publics.
* Les organisateurs peuvent créer des types de billets (nom, montant, quantité limitée).
* Achat public (sans authentification).
* Contrainte : une adresse email ne peut acheter qu'un seul billet par événement.

### 5.8 Bonus : Shopping list

* Un événement peut activer une shopping list via `shopping_list_enabled`.
* Contrainte : les items sont uniques par événement (`(event_id, name)`).
* Opérations : création, lecture, mise à jour, suppression.
* Droits : participants/organisateurs ; mise à jour/suppression réservées au créateur de l'item ou à un organisateur.

---

## 6. Endpoints principaux (vue d'ensemble)

Remarque : la liste exhaustive est disponible via Swagger.

### 6.1 Auth

* `POST /auth/register`
* `POST /auth/login`
* `GET /auth/me`

### 6.2 Groupes

* `POST /groups`
* `GET /groups`
* `GET /groups/{group_id}`
* `PATCH /groups/{group_id}`
* `GET /groups/{group_id}/members`
* `POST /groups/{group_id}/members/{user_id}`
* `DELETE /groups/{group_id}/members/{user_id}`
* `GET /groups/{group_id}/admins`
* `POST /groups/{group_id}/admins/{user_id}`
* `DELETE /groups/{group_id}/admins/{user_id}`

### 6.3 Événements

* `POST /events`
* `GET /events`
* `GET /events/{event_id}`
* `POST /events/{event_id}/join`
* `DELETE /events/{event_id}/participants/me`
* `GET /events/{event_id}/participants`
* `GET /events/{event_id}/organizers`
* `POST /events/{event_id}/organizers/{user_id}`
* `DELETE /events/{event_id}/organizers/{user_id}`
* `POST /events/{event_id}/invite-group-members`

### 6.4 Discussions et messages

* `POST /discussions`
* `GET /discussions/{discussion_id}`
* `GET /discussions/by-group/{group_id}`
* `GET /discussions/by-event/{event_id}`
* `POST /discussions/{discussion_id}/messages`
* `GET /discussions/{discussion_id}/messages`
* `GET /discussions/{discussion_id}/messages/{message_id}/replies`
* `DELETE /discussions/{discussion_id}/messages/{message_id}`

### 6.5 Albums / Photos / Commentaires

* `POST /albums`
* `GET /albums/{album_id}`
* `GET /albums/by-event/{event_id}`
* `POST /albums/{album_id}/photos`
* `GET /albums/{album_id}/photos`
* `POST /albums/photos/{photo_id}/comments`
* `GET /albums/photos/{photo_id}/comments`

### 6.6 Sondages

* `POST /polls`
* `GET /polls/by-event/{event_id}`
* `GET /polls/{poll_id}`
* `POST /polls/questions/{question_id}/vote`
* `GET /polls/{poll_id}/results`

### 6.7 Billetterie

* `POST /events/{event_id}/tickets/types` (organizer)
* `GET /events/{event_id}/tickets/types` (public)
* `POST /events/{event_id}/tickets/purchase` (public)
* `GET /events/{event_id}/tickets/purchases` (organizer)

### 6.8 Shopping list (bonus)

* `POST /events/{event_id}/shopping-items`
* `GET /events/{event_id}/shopping-items`
* `PATCH /events/{event_id}/shopping-items/{item_id}`
* `DELETE /events/{event_id}/shopping-items/{item_id}`

---

## 7. Validations et règles métier importantes

* Emails : validés (format) et uniques en base.
* Événements : `start_date` doit être strictement antérieure à `end_date`.
* Discussions : une discussion doit être liée soit à un groupe, soit à un événement (jamais les deux).
* Messages (threads) : une réponse (`parent_message_id`) doit pointer vers un message existant de la même discussion.
* Sondages :
   * au moins une question
   * au moins deux options par question
   * options uniques par question (insensible à la casse/espaces)
   * un vote maximum par utilisateur et par question
* Billetterie : un achat par email et par événement ; stock limité par type de billet.
* Shopping list : items uniques par événement (nom), et droits de modification/suppression.

---

## 8. Notes importantes pour les tests via Swagger

### 8.1 Clés étrangères optionnelles : utiliser `null` et pas `0`

Swagger peut proposer par défaut la valeur `0` pour les champs entiers. Or, `0` ne correspond généralement à aucun identifiant existant.

* Si une clé étrangère est optionnelle (ex. `group_id` lors de la création d'un événement), utiliser :
   * `null` si l'association n'est pas souhaitée
   * ou un identifiant réellement existant (`1`, `2`, etc.)



### 8.2 Contraintes sur les dates d'événements

Pour créer un événement, il est obligatoire de rentrer manuellement :

* `end_date` soit postérieure à `start_date`

Dans le cas contraire, la requête est rejetée par validation.

---

## 9. Base de données et évolution du schéma

La base utilisée est SQLite (fichier `app.db`) et l'initialisation est effectuée via `Base.metadata.create_all()`.

Cette méthode crée les tables si elles n'existent pas mais ne met pas à jour une table existante en cas de modification du modèle. Ainsi, lors d'une évolution du schéma (par exemple ajout de `parent_message_id` pour les threads), il est nécessaire, dans le contexte du TP, de recréer la base en supprimant `app.db` puis en relançant l'application.

---