# Phase 0 — Research & Décisions techniques

Feature : **049-checklist-documents** | Date : 2026-06-03

Ce document consolide les décisions issues de l'exploration du code existant (modules `applications` et `documents`, frontend) et résout les points ouverts avant conception.

---

## D1 — Persistance du rattachement : JSON existant vs nouvelle table

**Decision** : Réutiliser le champ JSON `fund_applications.checklist`, chaque item portant déjà `document_id` (UUID nullable) et `status`. **Pas de nouvelle table, pas de migration Alembic.**

**Rationale** :
- Le champ et la forme d'item existent déjà (`{key, name, status, document_id, required_by}` — `backend/app/modules/applications/schemas.py:151`).
- Le pattern read-modify-write JSON est éprouvé (`update_section`, `service.py:254`) et déclenche l'audit automatiquement (`FundApplication` est `Auditable`).
- FR-011 (réutilisabilité d'un document sur plusieurs items/dossiers) est satisfait nativement : `document_id` est une simple référence ; le même UUID peut apparaître dans plusieurs items/applications sans contrainte d'unicité.
- Constitution VII (Simplicité/YAGNI) : une table de liaison `application_documents` n'apporte rien tant qu'on n'a pas besoin de métadonnées par lien ni du sens inverse (hors périmètre V1).

**Alternatives considérées** :
- *Table `application_documents` (FK app_id, document_id, item_key)* : normalisation propre, intégrité référentielle DB (ON DELETE), mais surcoût (migration, modèle, jointures) non justifié en V1 ; rejetée (YAGNI). À reconsidérer en V2 si le sens inverse « depuis /documents » est implémenté.

---

## D2 — Valeur canonique du statut d'item : `provided` / `missing`

**Decision** : Le statut canonique est la chaîne `status ∈ {"missing", "provided"}`. « Fourni » ⇔ `status == "provided"` **et** `document_id` valide.

**Rationale** :
- L'onglet Checklist frontend lit **déjà** `item.status === 'provided'` (`frontend/app/pages/applications/[id].vue:388-407`).
- La fiche de préparation lit **déjà** `item.get("status") == "provided"` (`backend/app/modules/applications/prep_sheet.py:113-117`).
- La génération initialise `status: "missing"` (`templates.py:240`) et les tests le vérifient (`test_templates.py:283`).
- → Deux consommateurs sur trois utilisent déjà `status`. C'est la source de vérité à conserver.

**Point de divergence à corriger (FR-019)** : le tool chatbot `get_application_checklist` (`backend/app/graph/tools/application_tools.py:517-521`) lit des clés **inexistantes** (`item.get("provided")`, `item.get("label")`, `item.get("required")`) — il est donc **déjà cassé** (affiche tout comme manquant, label « N/A »). Décision : le corriger pour lire `status == "provided"`, `name`, et dériver « requis » de `required_by` (tous les items du catalogue sont requis en V1). Mettre à jour son test (`test_tools/test_application_tools.py:106`) dont le mock utilise une forme fictive `{label, required, provided}`.

**Note** : les valeurs `"attached"` / `"validated"` aperçues dans des commentaires ne sont **pas** utilisées par les consommateurs ; on ne les introduit pas (V1 binaire missing/provided).

---

## D3 — Intégrité du lien à la suppression d'un document (FR-014, SC-005)

**Decision** : **Nettoyage eager des références** au moment de la suppression d'un document. `delete_document` (`documents/service.py`) appelle un helper `clear_document_references(db, account_id, document_id)` exposé par le module `applications`, qui parcourt les dossiers du compte et, pour chaque item référençant ce `document_id`, réinitialise l'item (`document_id = None`, `status = "missing"`) de façon atomique par item.

En complément (défense en profondeur), la **sérialisation** de la checklist (réponse API) valide chaque `document_id` (existence + même compte) via un chargement groupé ; un item dont le document est introuvable est présenté `status = "missing"`, `document = null`.

**Rationale** :
- Plusieurs consommateurs lisent l'état **stocké** directement (prep-sheet, tool chatbot), pas la version sérialisée. Le nettoyage eager garantit que l'état stocké reste vrai pour **tous** les consommateurs → SC-005 à 100 %.
- `Document` n'a aucune FK entrante ; sa suppression supprime fichier + `DocumentAnalysis`/`DocumentChunk` en cascade, mais **ne touche pas** le JSON checklist (`documents/service.py:664`). Le nettoyage doit donc être explicite.
- La validation à la sérialisation couvre les états transitoires/concurrents (un document supprimé entre deux requêtes) sans effet de bord d'écriture sur un GET.
- Cohérent avec la clarification « atomique par item » (chaque réinitialisation ne touche qu'un item).

**Alternatives considérées** :
- *Derive-at-read seul* : faudrait modifier prep-sheet + tool chatbot pour revalider l'existence du document à chaque lecture (couplage + requêtes supplémentaires) ; rejeté.
- *FK + ON DELETE SET NULL* : nécessiterait la table de liaison (D1) ; rejeté en V1.
- *Bloquer la suppression d'un document rattaché* : contredit le cas limite explicite « document supprimé depuis /documents ne doit pas casser » ; rejeté.

**Optimisation différée** : pour le scan du nettoyage, V1 charge les dossiers du compte et filtre en Python (échelle faible). Un index GIN sur `checklist` ou une requête de containment JSON est différé (YAGNI), à noter si la volumétrie augmente.

---

## D4 — Flux « téléverser depuis un item » (US1)

**Decision** : Réutiliser l'endpoint existant `POST /api/documents/upload` (composant `DocumentUpload` + composable `useDocuments.uploadDocuments`) **puis** appeler le nouvel endpoint de rattachement avec l'`id` du document créé. Flux en deux étapes côté frontend, aucun nouvel endpoint d'upload.

**Rationale** :
- `POST /api/documents/upload` porte déjà toutes les validations (MIME PDF/PNG/JPG/DOCX/XLSX, taille 10 MB, signature magique anti-spoofing, sanitisation du nom) → FR-001/FR-015 satisfaits sans duplication.
- Le document créé est un document **standard** (clarification 2026-06-03, option A) : visible sur /documents et sélectionnable ailleurs → cohérent avec ce flux (pas de document « privé »).

**Note sur l'analyse IA** : l'endpoint direct `/api/documents/upload` ne déclenche **pas** l'analyse IA (seul l'upload via chat le fait en SSE) ; le document reste `status=uploaded`, `document_type=None` jusqu'à une éventuelle ré-analyse. C'est le comportement **actuel** de la page /documents et il est conservé tel quel : la feature ne dépend pas de l'analyse (la nature attendue vient de la ligne de checklist, pas de `document_type` — D5). Aucune action requise ; la mention « analyse IA » de la spec reste un héritage du flux réutilisé, non bloquant.

---

## D5 — Pas de contrainte entre `document_type` et l'item

**Decision** : Aucune validation de correspondance entre la nature auto-devinée (`document_type`) du document et la `key`/nature attendue de l'item. La ligne de checklist sur laquelle l'utilisateur agit fait foi.

**Rationale** : conforme à la spec (stratégie « contextuelle + manuelle ») et aux Assumptions. Le sélecteur liste **tous** les documents du compte (filtres facultatifs par type/statut hérités de `DocumentList`, mais aucun filtrage imposé).

---

## D6 — Sécurité multi-tenant au rattachement (FR-010, FR-018)

**Decision** : Le endpoint de rattachement charge le dossier via `_get_user_application` (vérifie `user_id == current_user.id`) puis charge le document cible et **vérifie que `document.account_id == application.account_id`** (et que le document est accessible à l'utilisateur courant). En cas de non-correspondance : **403 Forbidden**, aucun changement d'état.

**Rationale** :
- RLS PostgreSQL filtre déjà par `account_id` (GUC posée dans `get_current_user`, `api/deps.py:97`), mais `documents.account_id` est **nullable** (legacy) → une vérification applicative explicite est nécessaire pour fermer le cas des documents legacy sans compte et garantir SC-003 (0 rattachement inter-comptes).
- Le contrôle d'accès au dossier réutilise le helper existant `_get_user_application` (`router.py:335`).

---

## D7 — Endpoints REST (forme & nommage)

**Decision** : Deux endpoints sur le routeur `applications` (préfixe `/api/applications`), kebab-case respecté pour les ressources :
- `PUT /api/applications/{application_id}/checklist/{item_key}/document` — rattacher **ou remplacer** (idempotent), body `{ "document_id": "<uuid>" }`.
- `DELETE /api/applications/{application_id}/checklist/{item_key}/document` — détacher.

Réponse : l'item de checklist mis à jour, **enrichi** du sous-objet `document` (id, original_filename, mime_type) et du `status` effectif, plus `checklist_progress` du dossier.

**Rationale** :
- `PUT … /document` modélise « l'état du document de cet item » : créer ou remplacer = même verbe idempotent (FR-007 remplacement = PUT avec un autre `document_id`). `DELETE` = détacher (FR-006).
- Le verbe porte sur la sous-ressource « document de l'item », cohérent REST.
- Retourner l'item enrichi + la progression évite des allers-retours (SC-001, mise à jour optimiste du store frontend).

**Alternatives considérées** :
- *PATCH `…/checklist/{item_key}` avec body générique* : plus proche de `update_section`, mais mélange détachement (document_id=null) et rattachement dans un même verbe ambigu ; `PUT/DELETE` sur la sous-ressource est plus explicite. Retenu PUT/DELETE.

---

## D8 — Progression (FR-008) : emplacements onglet + liste

**Decision** : Exposer un objet calculé `checklist_progress { provided: int, total: int }` :
- dans la réponse **détail** du dossier (en plus du tableau `checklist`),
- dans la réponse **liste** des dossiers (`GET /api/applications/`), à côté de `sections_progress` existant.

Frontend : barre/compteur « M / N documents fournis » dans l'onglet Checklist (`[id].vue`) + badge compact « M/N » sur la carte de dossier (`index.vue`, à côté de l'actuel « M/N sections »).

**Rationale** : la liste ne transporte pas le tableau `checklist` complet → un champ agrégé est nécessaire pour l'indicateur compact (clarification 2026-06-03). `provided` est compté sur le **statut effectif** (document valide), cohérent avec D3.

---

## D9 — Composants frontend : réutilisation maximale

**Decision** :
- **Réutilisés tels quels** : `DocumentUpload` (`@upload`), `DocumentList` (`@select`/`@delete`), `DocumentPreview` (props `documentId/mimeType/filename`), `FullscreenModal`, `useDocuments`.
- **Nouveaux (2)** :
  - `DocumentPicker.vue` = `FullscreenModal` + `DocumentList` (réutilisé) ; charge les documents du compte via `useDocuments.fetchDocuments`, émet `@select(documentId)`. C'est le sélecteur manquant (US2).
  - `ChecklistItemRow.vue` = une ligne d'item : badge statut, nom du fichier si fourni, actions contextuelles (Téléverser / Choisir un existant / Aperçu / Remplacer / Détacher). Encapsule la logique d'item pour garder `[id].vue` lisible (< 800 lignes, Constitution).

**Rationale** : un seul composant réellement neuf (`DocumentPicker`) plus une ligne d'item extraite pour la cohésion. Respecte « chercher avant de créer » et la contrainte de taille de fichier.

---

## D10 — Audit (FR-013)

**Decision** : Aucune mécanique d'audit additionnelle. Les mutations du champ `checklist` sur `FundApplication` (Auditable) génèrent automatiquement une ligne `audit_log` (field `checklist`) via le listener `before_flush`.

**Rationale** : confirmé par exploration (`core/auditable.py:84`, `FundApplication` dans `AUDITABLE_MODELS`). Le nettoyage eager (D3) passe aussi par une mutation du modèle → également audité. `source_of_change` reste `"manual"` par défaut (comme `update_section`).

---

## D11 — Atomicité par item sous concurrence (FR-021)

**Decision** : Encadrer chaque opération attach/detach (et le nettoyage D3) par un **verrou de ligne** sur le dossier : `SELECT … FOR UPDATE` via `with_for_update()` sur `FundApplication` au début de la transaction, avant le read-modify-write du champ JSON `checklist`.

**Rationale** :
- Le pattern réutilisé (`update_section`) réassigne **tout** le tableau `checklist`. Sans verrou, deux écritures concurrentes sur des items distincts du même dossier provoquent un *last-write-wins* qui écrase l'une des deux (chat + UI, ou onglets multiples) — ce qui contredit la clarification 2026-06-03 et FR-021.
- `with_for_update()` sérialise les transactions sur la ligne du dossier : la seconde relit l'état après commit de la première, donc sa modification d'un autre item **préserve** la première. Mécanisme minimal, sans `jsonb_set` ni table de liaison.

**Alternatives considérées** :
- *`jsonb_set` ciblé en SQL* : mise à jour d'un seul item sans relire le tableau ; plus fin mais quitte l'ORM et complexifie l'audit field-level. Rejeté en V1 (le verrou suffit à l'échelle visée).
- *Aucun verrou (last-write-wins)* : rejeté — viole FR-021.

**Note** : `update_section` existant n'utilise pas de verrou (dette pré-existante non traitée ici) ; les nouvelles opérations checklist, elles, le posent.

---

## Synthèse des impacts code (sans imposer le découpage des tâches)

| Zone | Fichier | Nature |
|------|---------|--------|
| Backend | `modules/applications/schemas.py` | + `AttachDocumentRequest`, enrichissement `ChecklistItem` (`document`, statut effectif), `ChecklistProgress` |
| Backend | `modules/applications/service.py` | + `attach_checklist_document`, `detach_checklist_document`, `compute_checklist_progress`, `clear_document_references`, enrichissement sérialisation |
| Backend | `modules/applications/router.py` | + `PUT`/`DELETE` `…/checklist/{item_key}/document` ; `checklist_progress` dans détail + liste |
| Backend | `modules/documents/service.py` | `delete_document` → appel `clear_document_references` |
| Backend | `graph/tools/application_tools.py` | Fix parité `get_application_checklist` |
| Frontend | `pages/applications/[id].vue` | Onglet Checklist éditable + progression |
| Frontend | `pages/applications/index.vue` | Badge progression M/N |
| Frontend | `components/documents/DocumentPicker.vue` | Nouveau |
| Frontend | `components/applications/ChecklistItemRow.vue` | Nouveau |
| Frontend | `composables/useApplications.ts` | + `attachDocument`, `detachDocument` |
| Frontend | `stores/applications.ts` + types | `ChecklistItem.document?`, mutators, `checklist_progress` |

**Aucune migration. Aucune dépendance nouvelle.**
