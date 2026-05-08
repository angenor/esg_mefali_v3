# Clarifications — F20 Bibliothèque Ressources

**Mode**: autonome (Phase A SpecKit, autonomie totale demandée par le caller).
**Date**: 2026-05-08
**Spec**: [spec.md](./spec.md)

Toutes les ambiguïtés de F20 ont été levées avec des décisions par défaut motivées par le projet et les features déjà mergées (F01–F23). Aucune question bloquante remontée.

## Décisions consignées

### Q1 — Storage des fichiers `template_doc`

**Question** : où stocker les fichiers téléchargeables (politique anti-corruption, charte ESS, etc.) ?
**Options** : (A) S3/MinIO, (B) FileSystem local sous `/uploads/resources/`, (C) base64 inline en BDD.
**Décision** : **B (local sous `/uploads/resources/<filename>`)**.
**Rationale** : cohérent avec F04 (documents PME stockés en local), pas de dépendance cloud en MVP, réversible plus tard. Limite 10 Mo par fichier. `Content-Disposition: attachment` obligatoire au service.

### Q2 — Cardinalité fiche intermédiaire ↔ intermediary

**Question** : un intermédiaire peut-il avoir plusieurs fiches `intermediary_guide` simultanément (ex. par langue) ?
**Options** : (A) 1 seule fiche publiée par intermédiaire, (B) N publiées par langue.
**Décision** : **A (1 seule fiche `published` à instant T par intermédiaire)**.
**Rationale** : MVP français-only (FR-024), simplicité du modèle. Versions historiques possibles via versioning F04 mais une seule courante. Index unique partiel applicatif côté service (vérif au moment du publish).

### Q3 — Multi-tenant pour la table `resources`

**Question** : la table `resources` doit-elle être isolée par tenant (`account_id`) ou être un catalogue global admin-only ?
**Options** : (A) per-tenant avec `account_id`, (B) catalogue global admin-only sans `account_id` (EXEMPT F03).
**Décision** : **B (catalogue global, ajout à `EXEMPT_MODELS`)**.
**Rationale** : aligné sur sources F01, intermediaries F07, funds F07, skills F23. Pas de sens de cloner une bibliothèque de ressources pédagogiques par compte. Lecture publique, mutation admin-only via `app.current_role=admin`.

### Q4 — Versioning des éditions sur ressources publiées

**Question** : éditer une ressource publiée doit-il créer une nouvelle version ou écraser ?
**Options** : (A) édition in-place qui écrase, (B) création d'une nouvelle version draft (F04 patch+1).
**Décision** : **B (nouvelle version draft `<major>.<minor>.<patch+1>`)**.
**Rationale** : aligné sur F23 (skills) et F07 (offers). Préserve l'historique pour auditabilité. L'ancienne reste publiée tant que la nouvelle n'est pas validée 4-yeux. Bump major manuel uniquement.

### Q5 — Compteur `view_count` atomicité

**Question** : comment garantir l'atomicité de l'incrément face à 100+ requêtes simultanées ?
**Options** : (A) lecture/écriture transactionnelle, (B) `UPDATE ... SET view_count = view_count + 1` SQL atomique, (C) cache Redis avec flush périodique.
**Décision** : **B (UPDATE atomique côté SQL)**.
**Rationale** : pas de Redis en MVP (cohérent CLAUDE.md). PostgreSQL gère l'incrément concurrent. Pas de lock applicatif requis. Tests : 100 requêtes simultanées → exactement 100 incréments.

### Q6 — Whitelist provider vidéo

**Question** : quels providers vidéo accepter ?
**Décision** : **YouTube (`youtube.com/embed`, `youtu.be`), Vimeo (`vimeo.com`, `player.vimeo.com`), chemins relatifs `/uploads/videos/`**.
**Rationale** : suffit pour MVP. Validation à la création/édition. Les autres URL sont rejetées 422.

### Q7 — Algorithme de recommandation

**Question** : comment calculer le score de pertinence pour `recommend_resources_for_user()` ?
**Décision** : **score déterministe = (matching catégorie × 3) + (matching audience × 2) + (view_count normalisé × 1)**.
**Rationale** : pas de ML en MVP. Reproductible, testable, explicable. Score normalisé sur les ressources publiées en français.

### Q8 — Garde-fou anti-mutation LLM

**Question** : les tools LangChain peuvent-ils muter les ressources ?
**Décision** : **NON, lecture seule (`search_resources`, `get_resource_content`, `recommend_resources_for_user`)**.
**Rationale** : pattern F23 (skills) — un test de conformité bloque tout tool dont le nom matche `^(create|update|delete|publish|unpublish)_resource`.

### Q9 — Sanitisation du markdown

**Question** : comment éviter les XSS dans le rendu markdown utilisateur ?
**Décision** : **DOMPurify côté frontend après rendu HTML**, validation côté backend (rejet des balises `<script>`, `<iframe>` hors providers whitelist).
**Rationale** : double barrière. Limite contenu 50 000 caractères. Cohérent avec le rendu existant des messages chat.

### Q10 — FAQ comme entité distincte ou contenu structuré ?

**Question** : créer une table `faq_items` atomique ou stocker les FAQ comme markdown sectionné ?
**Décision** : **stocker comme `content_md` structuré (sections H2 par question)**.
**Rationale** : MVP simple. Permet de réutiliser le rendu markdown unique. Une table atomique sera ajoutée si besoin post-MVP (recherche par question, ranking).

## Décisions opérationnelles

- **Migration Alembic** : numéro **038**, `down_revision='033_create_skills'` à confirmer en plan (la dernière migration mergée est 033 selon l'historique CLAUDE.md ; vérifier dans le repo).
- **spec_number** : 038
- **Branche** : `feat/F20-bibliotheque-ressources` (créée par le caller)
- **Ressources legacy** : aucun module `app/modules/resources/` préexistant — création from scratch.
- **Conservation 2 sprints** : pas applicable (rien à conserver).

## Aucune question remontée à l'utilisateur

Toutes les ambiguïtés ont été résolues sur la base de :
- la spec source `F20-bibliotheque-ressources.md`
- les patterns établis par les features mergées (F01, F03, F07, F09, F23)
- les conventions du projet (CLAUDE.md)
- les hypothèses documentées dans la section Assumptions de la spec
