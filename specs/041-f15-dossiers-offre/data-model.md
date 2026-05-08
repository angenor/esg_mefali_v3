# Phase 1 — Data Model : F15 Génération de Dossiers par Offre

**Spec** : 041 | **Migration** : `041_templates_and_application_refactor` | **Date** : 2026-05-08

## Vue d'ensemble

F15 introduit une nouvelle table catalogue `templates_dossier` et enrichit la table métier existante `fund_applications`. Aucune autre table n'est modifiée ; toutes les autres entités (Offer F07, Skill F23, Source F01, Attestation F08, Project F06, CompanyProfile, Fund, Intermediary) sont consommées en lecture seule.

```
                       ┌─────────────────────────┐
                       │   templates_dossier     │ (NEW catalogue admin-only)
                       │  - id (PK)              │
                       │  - name                 │
                       │  - offer_id (FK F07)    │ NULLABLE pour fallback générique
                       │  - language (fr|en)     │
                       │  - sections (JSONB)     │
                       │  - required_documents   │
                       │  - tone, vocab, anti_p  │
                       │  - skill_id (FK F23)    │ NOT NULL
                       │  - source_id (FK F01)   │ NOT NULL
                       │  - VersioningMixin F04  │
                       │  - status (draft|publ.) │
                       │  - captured_by, verif_by│ 4-yeux
                       └────────────┬────────────┘
                                    │ FK template_id NOT NULL
                                    ▼
       ┌──────────────────────────────────────────────────────┐
       │                  fund_applications                   │ (PATCH)
       │  - existing fields (account_id, status, sections...)│
       │  + template_id (FK templates_dossier) NOT NULL       │
       │  + language (fr|en) NOT NULL                         │
       │  + attestation_id (FK attestations) NULLABLE         │
       │  + snapshot_at, snapshot_data (JSONB) — F04 pattern  │
       │  + export_path (str(500)) NULLABLE                   │
       │  + project_id (déjà ajouté par F06)                  │
       │  + offer_id (déjà ajouté par F07)                    │
       │  + UNIQUE INDEX partial(project_id, offer_id) WHERE  │
       │    status != 'cancelled'                             │
       └──────────────────────────────────────────────────────┘
```

## Entité 1 — `templates_dossier`

### Schema

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | UUID PK | NOT NULL, default uuid4 | Identifiant unique |
| `name` | VARCHAR(200) | NOT NULL, UNIQUE | Nom lisible (ex. « Dossier GCF via BOAD — Mitigation v2.3 ») |
| `offer_id` | UUID FK offers.id | NULLABLE (CASCADE on delete RESTRICT) | Offre cible. NULL = template fallback générique par instrument |
| `instrument_type` | VARCHAR(50) | NOT NULL CHECK IN ('subvention','prêt_concessionnel','equity','blending','mixte') | Type d'instrument (sert au fallback) |
| `language` | VARCHAR(2) | NOT NULL CHECK IN ('fr','en') | Langue par défaut |
| `sections` | JSONB | NOT NULL | Liste ordonnée `[{key, title, instructions, target_length, tone, required: bool}]` |
| `required_documents` | JSONB | NOT NULL | Liste pièces requises union, chacune `{title, mandatory, source_id, origin}` |
| `tone` | VARCHAR(100) | NOT NULL | Ton imposé (ex. « formel banque », « narratif IFI ») |
| `vocabulary_hints` | JSONB | NULLABLE | Vocabulaire métier `{terme: alias[]}` |
| `anti_patterns` | JSONB | NULLABLE | Liste de patterns à éviter (strings) |
| `skill_id` | UUID FK skills.id | NOT NULL ON DELETE RESTRICT | Skill F23 fournissant `prompt_expert`, `procedure`, `tool_whitelist`, `sources` |
| `source_id` | UUID FK sources.id | NOT NULL ON DELETE RESTRICT | Source F01 (référentiel officiel du template) |
| `version` | VARCHAR(50) | NOT NULL DEFAULT '1.0' | Versioning F04 (regex `^\d+\.\d+$`) |
| `valid_from` | DATE | NOT NULL DEFAULT CURRENT_DATE | F04 |
| `valid_to` | DATE | NULLABLE | F04 (NULL = courant) |
| `superseded_by` | UUID self-FK | NULLABLE ON DELETE SET NULL | F04 anti-cycle trigger |
| `status` | VARCHAR(20) | NOT NULL DEFAULT 'draft' CHECK IN ('draft','published') | Workflow F09 |
| `captured_by` | UUID FK users.id | NOT NULL ON DELETE RESTRICT | Auteur draft |
| `verified_by` | UUID FK users.id | NULLABLE ON DELETE RESTRICT | Vérificateur (4-yeux) |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

### Contraintes additionnelles

- `CHECK (verified_by IS NULL OR verified_by != captured_by)` — 4-yeux strict (cohérent F01).
- `CHECK (status = 'draft' OR verified_by IS NOT NULL)` — un template `published` doit avoir un vérificateur.
- Trigger `prevent_supersede_cycle` (F04) déjà en place s'applique automatiquement.

### Indexes

- `idx_templates_offer_lang_status (offer_id, language, status)` — recherche par offre.
- `idx_templates_instrument_lang_status (instrument_type, language, status)` — recherche fallback.
- `idx_templates_skill (skill_id)` — jointures graphe.
- `idx_templates_published_active (status) WHERE valid_to IS NULL` — listing actifs.

### RLS PostgreSQL

```sql
ALTER TABLE templates_dossier ENABLE ROW LEVEL SECURITY;
ALTER TABLE templates_dossier FORCE ROW LEVEL SECURITY;

CREATE POLICY templates_public_read_published
  ON templates_dossier
  FOR SELECT
  USING (status = 'published' AND valid_to IS NULL);

CREATE POLICY templates_admin_full_access
  ON templates_dossier
  FOR ALL
  USING (current_setting('app.current_role', true) = 'ADMIN')
  WITH CHECK (current_setting('app.current_role', true) = 'ADMIN');
```

`templates_dossier` est ajouté à `EXEMPT_MODELS` côté F03 audit middleware (catalogue admin-only — cohérent F23 `skills`). Les mutations admin sont auditées via `AdminAuditContextMiddleware` (`source_of_change = 'admin'`).

### Transitions d'état

```
   draft ─────publish (4-yeux: verified_by != captured_by)─────▶ published
     │                                                                  │
     │                                                                  │
     ◀───── unpublish ──────────────────────────────────────────────────┘

   published ──── new_version (1.x → 2.0) ───▶ new draft (superseded_by = old.id, valid_to = today)

   draft ────────────── soft_delete ──────────▶ marked valid_to = today (no physical delete)
```

### Validators applicatifs (Pydantic v2)

- `name` : 5..200 caractères, unicité validée DB.
- `sections` : list non vide, max 30 éléments, chaque section validée via sub-schema `SectionDef`.
- `required_documents` : list, chaque doc `{title: str(1..200), mandatory: bool, source_id: UUID, origin: 'fund'|'intermediary'|'both'|'template'}`.
- `tone`, `vocabulary_hints`, `anti_patterns` : bornes raisonnables (cohérent F23).
- `version` : regex `^\d+\.\d+$`.

### Sub-schema `SectionDef`

| Champ | Type | Contraintes |
|-------|------|-------------|
| `key` | str | regex `^[a-z][a-z0-9_]{1,50}$`, unique dans le template |
| `title` | str | 3..200 |
| `instructions` | str | 10..2000 |
| `target_length` | int | 100..5000 (mots) |
| `tone` | str optional | inherit template tone si absent |
| `required` | bool | default true |

## Entité 2 — `fund_applications` (PATCH)

### Colonnes ajoutées

| Colonne | Type | Contraintes |
|---------|------|-------------|
| `template_id` | UUID FK templates_dossier.id | NOT NULL post-backfill, ON DELETE RESTRICT |
| `language` | VARCHAR(2) | NOT NULL DEFAULT 'fr' CHECK IN ('fr','en') |
| `attestation_id` | UUID FK attestations.id | NULLABLE ON DELETE SET NULL |
| `export_path` | VARCHAR(500) | NULLABLE — path local du dernier PDF exporté |

### Index ajouté

```sql
CREATE UNIQUE INDEX idx_fund_applications_project_offer_unique
  ON fund_applications (project_id, offer_id)
  WHERE status != 'cancelled';
```

→ Idempotence FR-023 : tentative de doublon → `IntegrityError` capturé en service → ressource existante renvoyée.

### Snapshot existant (F04 — étendu en contenu)

`fund_applications.snapshot_at TIMESTAMPTZ` et `fund_applications.snapshot_data JSONB` sont déjà créés par F04. F15 **n'ajoute pas** de colonne ; il enrichit le **contenu** sérialisé (cf. R-003 dans research.md, bloc `template_snapshot`).

## Backfill (migration 041)

### Étape 1 — Créer 9 templates fallback

Pour chaque `(instrument_type, language)` parmi `{subvention, prêt_concessionnel, equity, blending, mixte}` × `{fr, en}`, insérer un template `published` (skip combo sans Skill disponible) avec :
- `name = f"Template fallback {instrument_type} ({language})"`
- `offer_id = NULL`
- `skill_id` = ID de `skill_esg_diagnostic` (existante seed F23) en fallback universel
- `source_id` = ID d'une source seed F01 « Mefali — Catalogue interne templates » (créée par cette migration si non existante, status `verified`, captured_by = compte admin technique seedé)
- `sections` = liste minimale 5 sections (résumé, projet, impacts ESG, plan financier, équipe)
- `tone = "formel"`, `language = fr|en`
- `status = 'published'`, `captured_by = system_admin`, `verified_by = system_admin_verifier` (couple admin technique seedé F02)

### Étape 2 — Lier toutes les `fund_applications` existantes

Pour chaque `FundApplication` sans `template_id` :
1. Déterminer `instrument_type` depuis `offer.fund.instrument_type` (F07) ou via mapping legacy `target_type` :
   - `fund_direct`, `intermediary_bank` → `subvention` (best-guess) ou `prêt_concessionnel`
   - `intermediary_agency`, `intermediary_developer` → `subvention`
2. Déterminer `language` depuis `offer.accepted_languages[0]` (FK F07) ou défaut `'fr'`.
3. Lier au template fallback `(instrument_type, language)`.
4. Marquer le champ JSONB de la candidature `legacy_backfill = true` (clé dans `sections[0].metadata` ou nouvelle clé `notes`).

### Étape 3 — Appliquer NOT NULL

Après backfill, `ALTER TABLE fund_applications ALTER COLUMN template_id SET NOT NULL`.

### Étape 4 — Seed templates publiés (10 prioritaires)

Insérés via `seed_templates.py`, idempotent par `name` :
- 4 templates par instrument (FR) + 2 templates EN (GCF Direct Access + Acumen) + 4 templates spécifiques (GCF/BOAD Mitigation, GCF/BOAD Adaptation, SUNREF/AFD, FEM/UNDP Blending).

### Sécurité de la migration

- Round-trip `up/down/up` testé sur PostgreSQL **et** SQLite (in-memory) en CI.
- Transaction unique : si une étape échoue, rollback complet.
- Idempotence : `seed_templates.py` vérifie `name` avant insertion.

## Mapping `target_type` legacy → `instrument_type`

| Legacy `target_type` | F15 `instrument_type` |
|----------------------|------------------------|
| `fund_direct` | `subvention` (par défaut), reclasser manuellement post-backfill si erreur |
| `intermediary_bank` | `prêt_concessionnel` |
| `intermediary_agency` | `subvention` |
| `intermediary_developer` | `equity` |

> Le champ `target_type` est conservé sur `fund_applications` (legacy) pour 2 sprints, puis dropped via une migration séparée hors scope F15.

## Validateurs Pydantic (résumé exécutif)

- `TemplateCreate` (admin) : `name`, `instrument_type`, `language`, `sections` (≥ 1), `required_documents`, `tone`, `skill_id`, `source_id`. `offer_id` optionnel.
- `TemplateUpdate` : tous champs optionnels sauf `version` (auto-bump si `published`).
- `TemplatePublish` : `verified_by` requis, vérification 4-yeux.
- `FundApplicationCreateBatch` : `project_id`, `offer_ids: list[UUID]` (1..10), `language` (optionnel, hérite de l'offre).
- `GenerateSectionRequest` : `application_id`, `section_key`, `user_inputs: dict optional`.
- `AttachAttestationRequest` : `application_id`, `attestation_id` (`null` pour détacher).
- `ExportRequest` : `application_id`, `with_attestation: bool = false`.

## Conformité audit & multi-tenant

- `FundApplication` est déjà dans `AUDITABLE_MODELS` (F03). Toutes mutations (création, set template_id, set language, set attestation_id, set status, set snapshot_data) génèrent des lignes `audit_log` automatiquement via le mixin `Auditable` + listener `before_flush`.
- `TemplateDossier` est dans `EXEMPT_MODELS` (cohérent F23) — l'audit passe via le middleware admin.
- RLS F02 sur `fund_applications` : déjà en place (4 policies pme_access_own_account, admin_full_access, etc.). Les nouvelles colonnes sont automatiquement filtrées par account_id.
