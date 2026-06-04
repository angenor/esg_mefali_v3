# Phase 1 — Data Model

Feature : **049-checklist-documents** | Date : 2026-06-03

> Rappel : **aucune nouvelle table, aucune migration**. On décrit ici les entités existantes réutilisées, l'évolution de leur représentation logique, et les transitions d'état.

---

## Entités

### FundApplication (existante — inchangée au niveau schéma DB)

Table `fund_applications` (`backend/app/models/application.py`). `Auditable`, multi-tenant (`account_id NOT NULL`).

Champ pertinent :

| Champ | Type DB | Notes |
|-------|---------|-------|
| `checklist` | `JSON` (default `[]`) | Liste ordonnée d'items de documents requis (voir ci-dessous). |
| `account_id` | `UUID NOT NULL` | Sert à la validation multi-tenant du rattachement. |
| `user_id` | `UUID NOT NULL` | Propriétaire ; contrôle d'accès via `_get_user_application`. |
| `target_type` | Enum | Détermine la composition de la checklist (inchangé en V1). |

**Aucune colonne ajoutée.** L'audit des modifications de checklist est automatique (mutation du champ `checklist`).

### Item de checklist (sous-structure JSON — forme conservée)

Élément du tableau `checklist`. Forme **stockée** (inchangée) :

| Clé | Type | Description | Règles |
|-----|------|-------------|--------|
| `key` | `str` | Identifiant stable de l'item (ex. `company_registration`). | Unique dans la checklist ; défini par le catalogue (`templates.py`). Non modifiable (V1). |
| `name` | `str` | Libellé français du document requis. | Lecture seule. |
| `status` | `str` | `"missing"` \| `"provided"`. | `"provided"` ⇔ `document_id` non nul **et** document valide. |
| `document_id` | `str (UUID)` \| `null` | Référence au `Document` rattaché. | `null` ⇔ `status == "missing"`. |
| `required_by` | `str` | Type de destinataire à l'origine de l'exigence. | Lecture seule. |

**Invariant** : `status == "provided"` ⟺ `document_id != null`. Maintenu par les opérations attach/detach et par le nettoyage à la suppression d'un document.

### Document (existante — inchangée)

Table `documents` (`backend/app/models/document.py`). `UUIDMixin`, `TimestampMixin` (non Auditable).

| Champ | Type | Notes |
|-------|------|-------|
| `id` | `UUID` | Référencé par `checklist[].document_id`. |
| `user_id` | `UUID NOT NULL` | Propriétaire. |
| `account_id` | `UUID NULL` (legacy) | **Vérifié applicativement** au rattachement (== `application.account_id`). |
| `original_filename` | `str` | Affiché sur l'item « Fourni » (FR-004). |
| `mime_type` | `str` | Utilisé pour l'aperçu (FR-005). |
| `status` | Enum | `uploaded`/`processing`/`analyzed`/`error` — sans incidence sur le rattachement. |
| `document_type` | Enum \| null | Nature auto-devinée — **aucune contrainte** vis-à-vis de l'item (D5). |

**Relation logique** : `checklist[].document_id → documents.id`, **non contrainte par FK** (référence souple dans le JSON). Réutilisable : un même `document.id` peut être référencé par plusieurs items et/ou plusieurs dossiers (FR-011).

---

## Représentation enrichie en sortie d'API (sérialisation)

La réponse API enrichit chaque item (sans changer le stockage) :

```
ChecklistItemOut:
  key: str
  name: str
  status: "missing" | "provided"        # statut EFFECTIF (revalidé)
  required_by: str
  document_id: UUID | null
  document: DocumentRef | null          # null si pas/plus rattaché

DocumentRef:
  id: UUID
  original_filename: str
  mime_type: str
  status: str                           # statut du document (info)

ChecklistProgress:
  provided: int                         # nb d'items au statut effectif "provided"
  total: int                            # nb total d'items
```

- `document` est peuplé par **chargement groupé** des `document_id` non nuls de la checklist (évite N+1), filtré au compte du dossier.
- Si un `document_id` ne résout pas un document valide (supprimé / autre compte), alors `document = null` et `status = "missing"` (statut effectif), même si le stockage n'a pas encore été nettoyé.

---

## Transitions d'état d'un item

```
                 attach(document_id valide, même compte)
   ┌──────────┐  ───────────────────────────────────────▶  ┌───────────┐
   │ missing  │                                              │ provided  │
   │ doc=null │  ◀───────────────────────────────────────   │ doc=<uuid>│
   └──────────┘   detach()  /  document supprimé (cleanup)   └───────────┘
        ▲                                                          │
        │                 replace(autre document_id)              │
        └──────────────────────  (provided → provided) ◀──────────┘
                         document_id passe à la nouvelle valeur
```

| Transition | Déclencheur | Effet stocké | Garde |
|------------|-------------|--------------|-------|
| missing → provided | `PUT …/document` (US1/US2) | `document_id = X`, `status = "provided"` | document X existe, `account_id` == dossier, item `key` existe |
| provided → provided | `PUT …/document` avec `Y ≠ X` (US4 remplacement) | `document_id = Y`, `status = "provided"` | idem (l'ancien lien n'est pas supprimé du stockage Document) |
| provided → missing | `DELETE …/document` (US4 détachement) | `document_id = null`, `status = "missing"` | item `key` existe et est rattaché |
| provided → missing | Suppression du document référencé (FR-014) | `document_id = null`, `status = "missing"` | nettoyage eager sur tous les items du compte référençant ce document |

Chaque transition est **atomique par item** (clarification 2026-06-03) : seule la sous-structure de l'item ciblé est réécrite ; les autres items du même dossier ne sont pas affectés. Garantie sous concurrence par un **verrou de ligne `with_for_update()`** sur le dossier pendant le read-modify-write (voir research D11).

---

## Règles de validation (récapitulatif testable)

- **V1** : rattacher exige un `document_id` résolvant un document du **même compte** que le dossier — sinon `403` (FR-010, SC-003).
- **V2** : `item_key` doit exister dans la checklist du dossier — sinon `404` (FR-016).
- **V3** : `application_id` doit exister et appartenir à l'utilisateur — sinon `404` (FR-016, FR-018).
- **V4** : invariant `status == "provided" ⟺ document_id != null` après toute opération.
- **V5** : `checklist_progress.provided` = nombre d'items au statut **effectif** `provided` ; `total` = longueur de la checklist (FR-008, SC-004).
- **V6** : checklist vide → réponse cohérente (`total = 0`), UI « Aucun document requis » (FR-017).
- **V7** : suppression d'un document → tous les items le référençant repassent à `missing` (FR-014, SC-005).
