# F20 — Bibliothèque Ressources + Fiches par Intermédiaire

**Module(s) source(s)** : Module 6.3 (Bibliothèque de Ressources)
**Priorité** : P1 — accompagnement utilisateur, différenciateur "fiches par intermédiaire"
**Dépendances** : F01 (sources), F02 (multi-tenant), F09 (admin pour saisie)
**Estimation** : 1.5 sprints

## Contexte & motivation

Module 6.3 :
- Guides pratiques ESG en français (chaque guide sourcé)
- Modèles de documents (politiques, procédures)
- Formations vidéo courtes
- FAQ contextualisées
- **Fiches par intermédiaire** : "Comment soumettre à BOAD", "Comment travailler avec PNUD", etc.

**État actuel** :
- Aucun module backend `app/modules/resources/`
- Aucun modèle `Resource`, `Guide`, `FAQ`, `VideoTutorial`, `IntermediaryGuide`
- Aucun endpoint API ressources
- Aucune page frontend `/resources`, `/library`, `/guides`
- Aucun champ `submission_guide` / `how_to_apply` sur `Intermediary`

**Conséquences** :
- PME livrée à elle-même quand elle veut comprendre comment travailler avec un intermédiaire spécifique
- Pas de modèles de politiques pour combler les écarts ESG
- Promesse Module 6 incomplète

## User stories

- **PME** : « Je veux accéder à un guide "Comment monter un dossier GCF" en français, sourcé, étape par étape. »
- **PME** : « Quand je clique sur l'intermédiaire BOAD dans la liste, je veux voir une fiche pratique : process, contacts, délais typiques, conseils, points d'attention. »
- **PME** : « Je veux télécharger un modèle de politique anti-corruption pour combler mon score gouvernance. »
- **PME** : « Je veux suivre une formation vidéo courte (3 min) sur "Les critères ESS BOAD". »
- **Admin** : « Je peux créer/éditer ces ressources depuis le back-office (F09). »

## Périmètre fonctionnel

### Modèles

Table `resources` (générique) :
- `id: UUID PK`
- `type: enum('guide', 'template_doc', 'video', 'faq', 'intermediary_guide')`
- `title: str(200)`
- `slug: str(200) UNIQUE`
- `description: text`
- `content_md: text` (markdown sourcé F01)
- `file_url: str | null` (pour templates téléchargeables)
- `video_url: str | null` (Youtube/Vimeo/local)
- `duration_seconds: int | null`
- `category: jsonb` (tags : `["esg", "carbon", "credit"]`)
- `target_audience: jsonb` (`["pme_micro", "pme_small", "pme_medium"]`)
- `language: enum('fr', 'en')`
- `source_id: UUID FK sources.id NOT NULL` (F01)
- `intermediary_id: UUID FK intermediaries.id | null` (pour `intermediary_guide`)
- `version`, `valid_from`, `valid_to` (F04)
- `publication_status` (F09)
- `view_count: int default 0`

### Fiches par intermédiaire

Type spécial `intermediary_guide` qui structure :
- Process de soumission (étapes)
- Contacts (téléphone, email, portail)
- Délais typiques
- Conseils gagnants (best practices)
- Points d'attention
- FAQ contextualisée

Liée via `intermediary_id`.

### API

- `GET /api/resources` (liste publique, filtrable par type/category/language)
- `GET /api/resources/{slug}`
- `GET /api/intermediaries/{id}/guide` (raccourci vers la fiche dédiée)
- `POST /api/admin/resources` (admin only F09)
- `PATCH /api/admin/resources/{id}`
- `DELETE /api/admin/resources/{id}`
- `POST /api/resources/{slug}/view` (incrémente view_count, anonyme)

### UI Frontend

Page `pages/resources/index.vue` :
- Liste des ressources par catégorie (cards)
- Filtres : type, language, category
- Barre de recherche

Page `pages/resources/[slug].vue` :
- Rendu markdown du content
- Sources cliquables (F01)
- Bouton "Télécharger" si template_doc
- Player vidéo si video
- Section "Ressources liées"

Page `pages/financing/intermediaries/[id]/guide.vue` :
- Fiche pratique de l'intermédiaire
- Lié à la fiche fonds (F07)

Page admin `pages/admin/resources/*` (F09) :
- CRUD ressources
- Éditeur markdown WYSIWYG (toast-ui/editor — déjà mentionné dans CLAUDE.md, à installer)

## Hors-scope (post-MVP)

- Système de favoris
- Commentaires utilisateurs sur les ressources
- Recommandations personnalisées (ML)
- Multi-format export (PDF, ePub)
- Streaming vidéo P2P
- Translations automatiques
- Marketplace de ressources tierces

## Exigences techniques

### Backend

- Migration Alembic `034_resources_table.py`
- Modèle `app/models/resource.py`
- Module `app/modules/resources/` : service, router
- Module admin `app/modules/admin/resources_router.py`
- Tools LangChain :
  - `search_resources(query, type, category)` → liste
  - `get_resource_content(slug)` → markdown
  - `recommend_resources_for_user()` (basé profil + scores)
- Seed initial : 10-15 ressources (guides ESG, fiches BOAD/UNDP/PNUD)
- Tests :
  - Test public access (no auth)
  - Test admin CRUD
  - Test search

### Frontend

- Pages `pages/resources/*`, `pages/financing/intermediaries/[id]/guide.vue`, `pages/admin/resources/*`
- Composants `ResourceCard.vue`, `ResourceMarkdownRenderer.vue`, `IntermediaryGuideView.vue`
- Composable `useResources.ts`
- Installer `toast-ui/editor` pour admin
- Dark mode

### Base de données

- Table `resources`
- Index : `(type, publication_status, valid_to)`, full-text sur `title + description`

## Critères d'acceptation

- [ ] Modèle `Resource` créé
- [ ] CRUD admin fonctionnel (F09)
- [ ] Pages publiques `/resources` et `/resources/[slug]` créées
- [ ] Page `/financing/intermediaries/[id]/guide` créée
- [ ] 15+ ressources seedées (au moins 5 guides ESG, 5 fiches intermédiaires, 3 templates docs, 2 FAQ)
- [ ] Sources cliquables F01 sur chaque chiffre/affirmation
- [ ] Test E2E : naviguer ressources → ouvrir fiche BOAD → contacter via lien
- [ ] Couverture tests ≥ 80 %

## Risques & garde-fous

- **Risque** : seed initial chronophage (rédaction 15 ressources). **Garde-fou** : prioriser fiches intermédiaires les plus demandées, accepter ressources draft pour MVP.
- **Risque** : informations obsolètes (changement contact intermédiaire). **Garde-fou** : versioning F04, alertes admin si > 6 mois sans review.
- **Risque** : violation droit d'auteur (textes copiés). **Garde-fou** : rédaction originale obligatoire, sources citées (F01), revue admin avant publish.
