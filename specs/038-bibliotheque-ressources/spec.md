# Feature Specification: F20 — Bibliothèque Ressources + Fiches par Intermédiaire

**Feature Branch**: `feat/F20-bibliotheque-ressources`
**Spec Number**: 038
**Created**: 2026-05-08
**Status**: Draft
**Source**: `documents_et_brouillons/features_a_implementer/F20-bibliotheque-ressources.md`
**Module(s) source(s)**: Module 6.3 (Bibliothèque de Ressources)
**Priorité**: P1 — accompagnement utilisateur, différenciateur « fiches par intermédiaire »
**Dépendances**: F01 (sources), F02 (multi-tenant), F09 (admin pour saisie). Toutes mergées.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Consulter un guide pratique sourcé en français (Priority: P1)

Une PME ouvre la bibliothèque de ressources, filtre par catégorie « Financement » puis ouvre le guide « Comment monter un dossier GCF ». Elle lit le contenu structuré en étapes, voit les chiffres cliquables menant aux sources F01 (taxonomie UEMOA, GCF Investment Framework), et identifie la prochaine action concrète.

**Why this priority**: c'est la promesse coeur du Module 6.3. Sans guides sourcés en français, la PME francophone reste livrée à elle-même et la différenciation « accompagnement contextualisé Afrique de l'Ouest » disparaît. Cette story livre seule un MVP utile (lecture + sourçage).

**Independent Test**: déployer uniquement le pipeline de lecture (table `resources` + endpoints `GET /api/resources` et `GET /api/resources/{slug}` + page `/resources` + page `/resources/[slug]`) avec un seed minimal de 3 guides ESG. La PME peut naviguer, filtrer, ouvrir une fiche, cliquer sur une source — sans qu'aucune autre user story ne soit livrée.

**Acceptance Scenarios**:

1. **Given** une PME authentifiée sur `/resources` et 5 guides ESG publiés en français, **When** elle filtre par catégorie « gouvernance », **Then** seuls les guides associés à la catégorie « gouvernance » s'affichent triés par date de mise à jour décroissante.
2. **Given** un guide « Politique anti-corruption » au statut publié contenant 3 références sourcées, **When** la PME ouvre `/resources/politique-anti-corruption`, **Then** le contenu markdown est rendu, chaque référence est cliquable et ouvre la modale source F01 avec titre / éditeur / date / URL.
3. **Given** un guide existe en version `1.0` puis est superseded par `1.1`, **When** la PME ouvre l'URL canonique `/resources/<slug>`, **Then** elle voit la version courante (1.1) avec un badge `Mis à jour le <date FR>` et l'historique reste accessible côté admin uniquement.

---

### User Story 2 — Lire la fiche pratique d'un intermédiaire pour soumettre un dossier (Priority: P1)

Une PME a identifié BOAD comme intermédiaire d'accès au fonds vert qu'elle vise (F07). Depuis la page de l'intermédiaire, elle clique sur « Voir la fiche pratique » et accède à `/financing/intermediaries/{id}/guide` : process de soumission étape par étape, contacts vérifiés, délais typiques, conseils gagnants, points d'attention, FAQ contextualisée. Elle copie l'email de contact et prépare son dossier en se basant sur les conseils.

**Why this priority**: c'est le différenciateur explicite du module. Aujourd'hui une PME ne sait pas par où commencer avec BOAD/PNUD/etc. Cette fiche réduit drastiquement le coût d'entrée. Elle est strictement liée à F07 (Intermediary) déjà mergée, donc déployable indépendamment dès que les fiches sont seedées.

**Independent Test**: créer 1 fiche `intermediary_guide` liée à BOAD, exposer `GET /api/intermediaries/{id}/guide` et la page `/financing/intermediaries/{id}/guide`, vérifier que le rendu utilise les sections structurées (process, contacts, délais, conseils, points d'attention, FAQ) et que les sources F01 sont cliquables sur chaque chiffre.

**Acceptance Scenarios**:

1. **Given** la BOAD est référencée dans `intermediaries` et possède une fiche `intermediary_guide` publiée, **When** la PME ouvre `/financing/intermediaries/{boad_id}/guide`, **Then** la fiche est rendue avec les 6 sections (process, contacts, délais, conseils, points d'attention, FAQ) et le titre indique `Comment travailler avec la BOAD`.
2. **Given** un intermédiaire sans fiche pratique publiée, **When** la PME ouvre `/financing/intermediaries/{id}/guide`, **Then** un état vide explicite s'affiche : « Aucune fiche pratique disponible pour cet intermédiaire pour le moment » + bouton retour vers la liste.
3. **Given** la fiche affiche un délai typique « 90 jours », **When** la PME clique sur le chiffre, **Then** la modale source F01 cite la source vérifiée (rapport BOAD ou retour terrain documenté) avec un badge `verified`.

---

### User Story 3 — Télécharger un modèle de document pour combler un écart ESG (Priority: P2)

Une PME a obtenu un score gouvernance bas (F13) et reçoit la recommandation « Mettre en place une politique anti-corruption ». Elle clique sur un lien depuis la recommandation qui l'amène à la ressource « Modèle Politique Anti-Corruption ». Elle télécharge le document `.docx`, le personnalise et le téléverse à nouveau dans son module documents (F04 documents).

**Why this priority**: P2 car opérationnellement utile mais non-bloquant pour le MVP. Le téléchargement d'un fichier statique est un raccourci par rapport à la rédaction guidée. Permet de fermer la boucle « score bas → action concrète » sans dépendre d'un autre module.

**Independent Test**: seed 3 templates (`template_doc`) avec `file_url` pointant vers `/uploads/resources/<filename>`, vérifier que la page de la ressource affiche un bouton « Télécharger » qui sert le fichier sans authentification (lecture publique pour les ressources publiées).

**Acceptance Scenarios**:

1. **Given** une ressource de type `template_doc` au statut publié avec `file_url=/uploads/resources/politique-anticorruption.docx`, **When** la PME clique sur le bouton « Télécharger », **Then** le fichier `.docx` est servi avec le bon `Content-Type` et `Content-Disposition: attachment` et le compteur `view_count` est incrémenté de 1.
2. **Given** une ressource `template_doc` non publiée (`draft`), **When** un visiteur tente d'accéder à son URL, **Then** la requête renvoie 404 (la ressource n'existe pas pour le public).

---

### User Story 4 — Visionner une formation vidéo courte (Priority: P2)

Une PME ouvre une ressource de type `video` intitulée « Les critères ESS BOAD en 3 min ». La page affiche un lecteur intégré, la durée annoncée, le résumé, les sources documentaires utilisées dans la vidéo et 2-3 ressources liées (autres guides BOAD).

**Why this priority**: complète l'offre pédagogique mais non-bloquant pour le MVP. La vidéo peut être hébergée sur YouTube/Vimeo/local — l'embed minimal suffit en MVP.

**Independent Test**: seed 1 ressource `video` avec `video_url`, vérifier qu'un lecteur s'affiche, que `duration_seconds` est rendu en `mm:ss`, et que la liste des ressources liées (3 max, mêmes catégories) apparaît en bas de page.

**Acceptance Scenarios**:

1. **Given** une ressource `video` publiée avec `video_url=https://www.youtube.com/embed/<id>` et `duration_seconds=180`, **When** la PME ouvre la page, **Then** le lecteur s'affiche avec la durée `3:00` et le compteur `view_count` est incrémenté de 1.
2. **Given** une URL vidéo non reconnue (provider hors liste autorisée), **When** la page se charge, **Then** un fallback texte s'affiche avec un lien externe `Voir la vidéo`.

---

### User Story 5 — Administrer le catalogue de ressources depuis le back-office (Priority: P1)

Un administrateur (rôle `ADMIN` F02) ouvre `/admin/resources`, crée une nouvelle ressource via l'éditeur markdown, lui associe une source vérifiée F01, choisit un type, des catégories, une audience cible et une langue, sauvegarde en `draft`, fait relire, puis publie. Workflow 4-yeux : `created_by != verified_by` (cohérent avec F09).

**Why this priority**: P1 car sans CRUD admin, le catalogue ne peut pas vivre. Sans cette story, on ne peut pas seeder ni mettre à jour le contenu. Indépendamment testable via l'interface admin (F09 déjà mergée).

**Independent Test**: connecter un compte ADMIN, créer une ressource `guide`, associer une source F01 vérifiée, sauvegarder en draft, publier, vérifier qu'elle apparaît côté public.

**Acceptance Scenarios**:

1. **Given** un admin sur `/admin/resources/new`, **When** il sauvegarde un brouillon avec `title`, `slug`, `content_md`, `source_id` (vérifié), `type=guide`, `language=fr`, **Then** la ressource est créée en statut `draft`, l'événement audit F03 est tracé `source_of_change=admin` et un message de confirmation s'affiche.
2. **Given** une ressource en `draft` validée par un second admin (≠ créateur), **When** ce second admin clique sur « Publier », **Then** le statut passe à `published`, `valid_from=today`, l'audit log enregistre l'action `publish` et la ressource devient visible côté public.
3. **Given** une PME (rôle ≠ ADMIN), **When** elle tente d'appeler `POST /api/admin/resources`, **Then** la requête retourne 403 et l'événement est tracé dans l'audit log.
4. **Given** un admin tente de publier une ressource sans `source_id`, **When** il valide, **Then** la requête retourne 422 avec message « Une ressource ne peut être publiée sans source vérifiée F01 ».

---

### User Story 6 — L'assistant IA recommande une ressource depuis le chat (Priority: P3)

Pendant une conversation ESG, l'utilisateur demande « Comment je peux améliorer mon score gouvernance ? ». L'agent appelle le tool `recommend_resources_for_user`, identifie 2-3 ressources pertinentes (modèle de politique, guide de gouvernance) et les présente sous forme de cartes cliquables dans le chat.

**Why this priority**: P3 car nice-to-have. La recherche de ressources fonctionne déjà via la page `/resources`. La recommandation contextuelle est un bonus de fluidité conversationnelle.

**Independent Test**: appeler le tool `recommend_resources_for_user` avec un profil PME ayant un score gouvernance < 50, vérifier que la liste retournée contient au moins 1 ressource taggée `governance` triée par pertinence (catégorie match + audience match).

**Acceptance Scenarios**:

1. **Given** un utilisateur authentifié avec un score gouvernance F13 = 35, **When** l'agent appelle `recommend_resources_for_user`, **Then** la réponse contient 1-5 ressources publiées dont au moins une avec catégorie `governance`, ordonnées par pertinence décroissante.
2. **Given** un utilisateur sans score F13, **When** l'agent appelle `recommend_resources_for_user`, **Then** la réponse fallback retourne les 3 ressources publiées les plus consultées (`view_count` desc) toutes catégories confondues.

---

### Edge Cases

- **Ressource superseded** : la version `1.0` ne doit jamais s'afficher publiquement après transition vers `1.1` (gérée par `superseded_by` F04). L'URL canonique `/resources/<slug>` sert la version courante uniquement.
- **Slug doublon** : la création d'une ressource avec un slug déjà existant retourne 422 avec message clair.
- **Source non vérifiée** : tentative de publier une ressource pointant vers une source `draft`/`pending` ou `outdated` retourne 422.
- **`intermediary_id` orphelin** : si l'intermédiaire est supprimé ou désactivé, la fiche `intermediary_guide` reste lisible mais affiche un bandeau d'avertissement « Cet intermédiaire n'est plus actif ».
- **Fichier upload manquant** : `template_doc` avec `file_url` pointant vers un fichier introuvable retourne 404 explicite + log d'erreur structuré.
- **Lecture concurrente du compteur `view_count`** : en cas d'incrément simultané, la mise à jour doit être atomique (UPDATE ... SET view_count = view_count + 1).
- **Multi-tenant** : le catalogue est admin-only sans `account_id` (cohérent avec EXEMPT_MODELS F03 — sources, indicators, etc.). Les PME lisent en lecture publique les ressources `published`.
- **Langue absente** : si une PME demande une ressource en `en` mais que seule la version `fr` existe, l'API retourne la version `fr` avec un avertissement.
- **Vidéo provider non autorisé** : whitelist stricte (YouTube, Vimeo, local). Les autres URL sont bloquées à l'upload.
- **FAQ longue** : un type `faq` peut contenir plusieurs questions/réponses dans `content_md` (markdown sectionné). Pas de table dédiée FAQ atomique en MVP.
- **Recherche full-text** : indexation GIN sur `title + description` uniquement (le contenu markdown reste hors index pour limiter le coût).
- **Versioning F04** : éditer une ressource publiée crée automatiquement une nouvelle version `<major>.<minor+1>` en draft, l'ancienne reste publiée tant que la nouvelle n'est pas validée.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Modèle et données

- **FR-001**: Le système DOIT exposer une entité `Resource` regroupant 5 types : `guide`, `template_doc`, `video`, `faq`, `intermediary_guide`.
- **FR-002**: Chaque ressource DOIT être rattachée à une source F01 vérifiée (`source_id NOT NULL`, source au statut `verified`).
- **FR-003**: Chaque ressource publiée DOIT avoir un slug URL unique, immuable après publication.
- **FR-004**: Les ressources de type `intermediary_guide` DOIVENT être liées à un intermédiaire (`intermediary_id NOT NULL` pour ce type) ; les autres types DOIVENT avoir `intermediary_id IS NULL`.
- **FR-005**: Les ressources DOIVENT supporter le versioning F04 (`version`, `valid_from`, `valid_to`, `superseded_by`).
- **FR-006**: Les ressources DOIVENT supporter le workflow de publication F09 (`publication_status` ∈ `draft|published|archived`) et le 4-yeux (`created_by != verified_by` pour publier).
- **FR-007**: Le système DOIT tracer chaque mutation sur `Resource` dans l'audit log F03 avec `source_of_change=admin` côté CRUD admin et `source_of_change=llm` si une mutation passe par un tool LangChain (interdit en MVP — voir FR-027).

#### Lecture publique

- **FR-008**: Les utilisateurs (authentifiés ou non) DOIVENT pouvoir lister les ressources publiées via `GET /api/resources` avec filtres `type`, `category`, `language`, `intermediary_id`, paramètre de recherche `q` (sur `title + description`), pagination (`page`, `limit` 1-50).
- **FR-009**: Les utilisateurs DOIVENT pouvoir lire le détail d'une ressource via `GET /api/resources/{slug}` qui retourne content markdown + sources liées + ressources liées.
- **FR-010**: Les utilisateurs DOIVENT pouvoir accéder à `GET /api/intermediaries/{id}/guide` qui retourne la fiche `intermediary_guide` publiée pour cet intermédiaire (ou 404 explicite).
- **FR-011**: Le système DOIT incrémenter atomiquement `view_count` quand `POST /api/resources/{slug}/view` est appelé. Cet endpoint DOIT être anonyme (pas d'auth requise).
- **FR-012**: Seules les ressources `published` (et non superseded) DOIVENT être visibles publiquement.

#### CRUD admin

- **FR-013**: Les administrateurs (rôle `ADMIN` F02) DOIVENT pouvoir créer une ressource via `POST /api/admin/resources`.
- **FR-014**: Les administrateurs DOIVENT pouvoir modifier une ressource via `PATCH /api/admin/resources/{id}` ; modifier une ressource publiée DOIT créer une nouvelle version en `draft` (F04 patch+1).
- **FR-015**: Les administrateurs DOIVENT pouvoir supprimer (soft-delete via `valid_to=today` + `publication_status=archived`) une ressource via `DELETE /api/admin/resources/{id}` uniquement si elle est en `draft`.
- **FR-016**: Les administrateurs DOIVENT pouvoir publier une ressource via une action dédiée qui vérifie : ressource en `draft`, `source_id` vérifiée, second validateur ≠ créateur (4-yeux F09).
- **FR-017**: Toute action admin DOIT être tracée dans l'audit log F03 (`create|update|publish|archive`).
- **FR-018**: Les endpoints admin DOIVENT retourner 403 pour tout utilisateur non-ADMIN.

#### Tools LangChain

- **FR-019**: L'agent IA DOIT disposer d'un tool `search_resources(query, type, category)` qui retourne les ressources publiées correspondantes (top 10).
- **FR-020**: L'agent IA DOIT disposer d'un tool `get_resource_content(slug)` qui retourne le markdown publié + sources F01 d'une ressource.
- **FR-021**: L'agent IA DOIT disposer d'un tool `recommend_resources_for_user()` qui se base sur le profil utilisateur, ses scores ESG/carbone/crédit, ses candidatures actives pour proposer 1-5 ressources pertinentes.
- **FR-022**: Les tools DOIVENT être en lecture seule (aucun tool LLM ne peut créer/éditer/supprimer une ressource — interdit par garde-fou de conformité F23).
- **FR-023**: Les tools DOIVENT être ajoutés à la whitelist globale (transverse aux 7 nœuds métier) car la recherche de ressources est utile partout.

#### Frontend

- **FR-024**: Le système DOIT exposer une page `/resources` (liste filtrable + barre de recherche) en français, dark mode-compatible.
- **FR-025**: Le système DOIT exposer une page `/resources/[slug]` (rendu markdown sourcé F01 + bouton téléchargement si template + lecteur vidéo si video + ressources liées) en français, dark mode-compatible.
- **FR-026**: Le système DOIT exposer une page `/financing/intermediaries/[id]/guide` rendant la fiche pratique de l'intermédiaire en français, dark mode-compatible.
- **FR-027**: Le système DOIT exposer des pages admin `/admin/resources` (liste), `/admin/resources/new` (création) et `/admin/resources/[id]` (édition) avec éditeur markdown WYSIWYG et workflow draft/published.

#### Seed initial

- **FR-028**: Le système DOIT être livré avec au moins 15 ressources seedées en français : ≥ 5 guides ESG, ≥ 5 fiches intermédiaires (BOAD, PNUD, BAD, FEM/GEF, GCF), ≥ 3 templates documents (politique anti-corruption, charte ESS, registre des risques), ≥ 2 FAQ contextualisées.
- **FR-029**: Chaque ressource seedée DOIT être rattachée à une source F01 vérifiée existante.
- **FR-030**: Le seed DOIT être idempotent (relancer le script ne crée pas de doublons — vérification par `slug`).

#### Contraintes de sécurité et conformité

- **FR-031**: Les ressources DOIVENT être exemptées de Row-Level Security PME (catalogue admin-only sans `account_id`, ajoutées à `EXEMPT_MODELS`), mais l'admin doit avoir `app.current_role=admin` pour muter (cohérent F03).
- **FR-032**: Le contenu markdown DOIT être assaini côté frontend avant rendu (DOMPurify-like) pour empêcher l'injection XSS.
- **FR-033**: Les fichiers téléchargeables DOIVENT être servis avec un `Content-Disposition: attachment` et la taille limite est 10 Mo par fichier.
- **FR-034**: Les URLs vidéo DOIVENT être validées contre une whitelist (YouTube, Vimeo, ou chemin relatif `/uploads/`).

### Key Entities *(include if feature involves data)*

- **Resource** : entité de catalogue représentant une ressource pédagogique (guide, modèle de document, vidéo, FAQ, fiche intermédiaire). Attributs clés : `id` (UUID), `type` (enum 5 valeurs), `title` (≤ 200 chars), `slug` (unique), `description`, `content_md` (markdown), `file_url` (nullable), `video_url` (nullable), `duration_seconds` (nullable), `category` (JSON array de tags), `target_audience` (JSON array : `pme_micro|pme_small|pme_medium`), `language` (enum `fr|en`), `source_id` (FK sources F01 NOT NULL), `intermediary_id` (FK intermediaries F07, NOT NULL ssi type=`intermediary_guide`), `version|valid_from|valid_to|superseded_by` (F04), `publication_status` (F09), `view_count` (int, atomique), `created_by|verified_by` (4-yeux), `created_at|updated_at`. Catalogue admin-only (sans `account_id`), exempté F03 du mixin Auditable mais audité par middleware admin.
- **Relation Resource × Source** : chaque ressource pointe vers UNE source principale F01 (`source_id`). Les chiffres dans `content_md` peuvent référencer d'autres sources via balisage markdown spécial → résolus côté rendu (`<SourceLink>` cliquable).
- **Relation Resource × Intermediary** : pour les fiches `intermediary_guide` uniquement. Cardinalité 1 intermédiaire ↔ N fiches mais 1 seule fiche `published` à la fois (les autres sont `draft`/`archived`/superseded).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: une PME peut trouver et ouvrir une ressource pertinente (guide ESG ou fiche intermédiaire) en moins de 30 secondes depuis l'arrivée sur `/resources`.
- **SC-002**: au moins 15 ressources de qualité (sourcées F01, rédaction originale, validées 4-yeux) sont disponibles à la mise en production.
- **SC-003**: 100 % des chiffres ou affirmations factuelles dans les ressources publiées renvoient vers une source F01 cliquable et vérifiée.
- **SC-004**: 100 % des ressources publiées sont en français avec accents correctement encodés.
- **SC-005**: la page `/financing/intermediaries/{id}/guide` est accessible pour au moins 5 intermédiaires majeurs (BOAD, PNUD, BAD, FEM/GEF, GCF) à la mise en production.
- **SC-006**: 0 ressource publiée ne peut exister sans `source_id` vérifié (garde-fou applicatif + base de données).
- **SC-007**: 0 mutation de ressource via tool LangChain (garde-fou de conformité analogue à F23).
- **SC-008**: la couverture de tests automatisés sur le périmètre F20 est ≥ 80 %.
- **SC-009**: les pages publiques `/resources` et `/resources/[slug]` chargent en < 1,5 seconde sur connexion 3G simulée pour une liste de 50 ressources.
- **SC-010**: l'incrément `view_count` est atomique : 100 requêtes simultanées de `POST /api/resources/{slug}/view` produisent exactement 100 incréments.
- **SC-011**: le rapport public `view_count` est cohérent à ± 0 entre la valeur retournée par l'API et la valeur en base (pas de cache divergent).
- **SC-012**: la recherche full-text par mot-clé (`q=`) retourne des résultats pertinents (au moins une ressource pour des requêtes courantes : « gouvernance », « BOAD », « politique »).
- **SC-013**: 100 % des ressources `template_doc` ont un `file_url` valide pointant vers un fichier servi correctement (pas de 404).
- **SC-014**: la migration Alembic `038_create_resources` passe le round-trip `up/down/up` sur PostgreSQL sans perte de données.
- **SC-015**: l'éditeur markdown admin permet de saisir et prévisualiser une ressource complète sans assistance technique en moins de 10 minutes.

---

## Assumptions

- **Storage** : les fichiers `template_doc` sont stockés en local sous `/uploads/resources/<filename>` (pas de S3/MinIO en MVP, cohérent avec F04 documents).
- **Cache** : pas de cache Redis dédié en MVP — utilisation d'un cache in-memory côté backend (TTL court) si nécessaire pour les listes les plus consultées.
- **Asynchrone** : pas de queue Celery — toutes les opérations CRUD sont synchrones FastAPI/SQLAlchemy async.
- **UUID v4** pour les identifiants (cohérent avec le reste du codebase).
- **Devise** : XOF pour tous les montants éventuels mentionnés dans le contenu (cohérent avec F04 Money typed).
- **Langue par défaut** : `fr` avec accents (é, è, ê, à, ç, ù) obligatoires.
- **Multi-tenant** : `Resource` est un catalogue admin-only, ajouté à `EXEMPT_MODELS` (cohérent F03 — pas d'`account_id`). Les PME y accèdent en lecture publique sans isolation par tenant.
- **Audit** : `Resource` n'utilise pas le mixin `Auditable` (catalogue exempté F03) mais les actions admin sont tracées via le middleware `AdminAuditContextMiddleware` déjà en place (F03/F09).
- **Versioning F04** : les éditions sur ressources publiées créent une nouvelle version draft avec bump patch (`1.0` → `1.0.1`) — pas de bump majeur automatique en MVP.
- **Editeur WYSIWYG** : `toast-ui/editor` (déjà mentionné dans CLAUDE.md, à installer côté frontend).
- **Conservation legacy** : aucun module existant `app/modules/resources/` à refactoriser — création from scratch.
- **Whitelist provider vidéo** : YouTube (`youtube.com/embed`, `youtu.be`), Vimeo (`vimeo.com`, `player.vimeo.com`), et chemins relatifs `/uploads/videos/` uniquement.
- **Limite de contenu** : `content_md` ≤ 50 000 caractères (≈ 30 pages), `description` ≤ 500 caractères, `title` ≤ 200 caractères.
- **Cardinalité fiche intermédiaire** : un intermédiaire peut avoir plusieurs versions historiques mais une seule fiche `published` à un instant T (contrainte applicative + index unique partiel).
- **Sourçage des chiffres** : balise markdown spéciale `[texte](#source:<source_id>)` parsée côté rendu en `<SourceLink>` cliquable (cohérent avec le reste du frontend F01).
- **Recommandations** : algorithme déterministe sans ML — score de pertinence basé sur (matching catégorie × 3) + (matching audience × 2) + (`view_count` normalisé × 1).
- **FAQ** : les FAQ sont stockées comme `content_md` structuré (sections H2 par question) — pas de table `faq_items` atomique en MVP.

---

## Dependencies

- **F01** (sources, mergée) : `source_id` FK obligatoire, `<SourceLink>` cliquable.
- **F02** (multi-tenant + roles, mergée) : rôle `ADMIN` requis pour CRUD admin, `EXEMPT_MODELS` pour la table.
- **F03** (audit log, mergée) : actions admin tracées via middleware existant.
- **F04** (versioning + Money, mergée) : `version`, `valid_from`, `valid_to`, `superseded_by` (mais peu d'usage Money car contenu pédagogique).
- **F07** (offre fonds intermédiaire, mergée) : FK vers `intermediaries.id` pour `intermediary_guide`.
- **F09** (back-office admin, mergée) : workflow draft/published + 4-yeux + pages admin.
- **F23** (skills, mergée) : pattern de garde-fou « no LLM mutation » réutilisé.

---

## Out of Scope (post-MVP)

- Système de favoris utilisateur (étoiles, listes personnelles)
- Commentaires utilisateurs sur les ressources
- Recommandations personnalisées par ML / collaborative filtering
- Multi-format export (PDF, ePub) des ressources
- Streaming vidéo P2P / hébergement vidéo natif
- Translations automatiques (FR ↔ EN)
- Marketplace de ressources tierces
- Partage social (Twitter, LinkedIn)
- Notifications push sur nouvelles ressources
- Statistiques détaillées par utilisateur (parcours de lecture)
- Système de quiz / certification après lecture
- Versionning conversationnel (diff inter-versions admin)
- Workflow de relecture éditoriale multi-rôles (au-delà du 4-yeux F09)
