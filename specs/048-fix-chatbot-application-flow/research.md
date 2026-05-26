# Phase 0 — Research & Decisions

**Feature**: 048-fix-chatbot-application-flow
**Date**: 2026-05-25

Toutes les inconnues de Technical Context sont résolues ci-dessous. Chaque décision s'appuie sur la lecture du code existant (chemins + lignes cités).

---

## D1 — Exposer `create_fund_application` quelle que soit la page (FR-001, FR-001a, FR-002)

**État actuel** :
- `create_fund_application` est défini dans `backend/app/graph/tools/application_tools.py:170` (fonctionnel, accepte `offer_id`/`project_id`).
- Il figure dans `PAGE_TOOL_MAPPING["financing"]` et `["candidatures"]` et `MODULE_TOOL_MAPPING["financing"]`/`["application"]` (`tool_selector_config.py:189,217,341,359`).
- `select_tools_for_node` (`tool_selector.py:65-71`) choisit **soit** les tools de page (si le slug est connu) **soit** les tools du nœud (fallback). Logique mutuellement exclusive : quand le slug est connu mais sans rapport (`documents`, `dashboard`…), les tools du nœud d'exécution (= intention routée) sont **ignorés**.

**Décision** : refactorer `select_tools_for_node` pour construire `base_names = page_tools ∪ node_module_tools ∪ GLOBAL_WHITELIST`, puis appliquer une **troncature priorisée** si `> MAX_TOOLS_PER_TURN` :
1. `GLOBAL_WHITELIST` (toujours conservé) ;
2. tools du **nœud d'exécution** (intention détectée par le routeur F013) ;
3. tools de **page** (contexte d'affichage) — rognés en dernier.

**Rationale** : le routeur multi-tour F013 classifie déjà l'intention et route vers le nœud `financing`/`application` quand l'utilisateur demande un dossier. Le seul défaut est que le slug de page écrase ce signal. Unir + prioriser le nœud rend l'outil disponible **par intention**, conforme à la clarification Q3=B, sans transformer l'outil en « toujours actif » global (Q3=A rejeté) ni ajouter une couche d'intention séparée (principe VII). Budget : `GLOBAL_WHITELIST` (22) + nœud `application` (~13) = 35 ≤ 36 ; les tools de page ne sont ajoutés que s'il reste de la marge.

**Dépendance à vérifier (tâche Phase 2)** : confirmer que le routeur route bien « génère un dossier de candidature » vers le nœud `application`/`financing` même depuis `/documents`. Si la classification reste sur `chat`, renforcer les mots-clés/exemples du classifieur F013 (`nodes.py`) pour l'intention « créer/candidater/dossier ».

**Alternatives considérées** :
- *Ajouter `create_fund_application` à `GLOBAL_WHITELIST`* (Q3=A) : simple mais expose l'outil à chaque tour partout (bruit, risque d'appel hors contexte) — rejeté car non aligné Q3=B.
- *Router systématiquement vers le nœud financement sur mot-clé* : trop intrusif, casse les autres parcours — rejeté.

---

## D2 — Mémoire ESG proactive entre sessions (FR-007 à FR-012, FR-008a, FR-008b)

**État actuel** :
- Persistance **correcte** : `create_project_esg_assessment` (service `project_service.py:78`) dédoublonne déjà les drafts (**409** si un draft existe pour le couple projet/référentiel) ; `save_project_esg_criterion_response` fait un **UPSERT** (update si la réponse existe). Les validators F047 (2026-05-23) empêchent désormais les `normalized_score=0` silencieux.
- Découverte **déjà possible** : `list_project_esg_assessments` et `get_project_esg_assessment` sont dans `GLOBAL_WHITELIST` (`tool_selector_config.py:75-80`) — donc disponibles depuis n'importe quelle page (FR-008b **déjà satisfait au niveau outil**).
- **Lacune** : `_load_full_context_for_state` (`app/api/chat.py:398`) ne charge que `{profile, projects actifs}`. Aucun résumé des évaluations ESG n'est injecté → le LLM ignore l'existence des évaluations et présente les critères comme « manquants » au lieu d'appeler les tools de lecture.

**Décision (FR-008a)** : enrichir `_load_full_context_for_state` d'un résumé **léger** des évaluations ESG-projet de l'utilisateur (jointure sur les projets actifs déjà chargés) : par évaluation `{project_id, project_name, referential_code, state, score, coverage_rate, covered_count, missing_count}`. Propager via un nouveau champ `ConversationState.user_project_esg_assessments` (analogue à `user_projects`) et l'injecter dans les prompts financement/application/ESG avec une directive : « avant d'affirmer qu'un critère manque, appelle `get_project_esg_assessment` pour vérifier l'état réel ».

**Décision (FR-006 analogue ESG)** : la dédup draft existe déjà ; aucune action sauf vérifier que le LLM **réutilise** l'assessment existant (via le résumé proactif + docstring `create_project_esg_assessment` qui dit déjà « Don't use when… reprendre via get »). Ajouter au besoin une directive prompt explicite pour éviter de tenter un second `create` (qui renverrait 409 et embrouillerait la réponse).

**Rationale** : approche hybride (Q2=A) — résumé proactif au démarrage (évite l'hallucination « manquant ») + lecture détaillée à la demande (maîtrise le volume de contexte). Réutilise l'infra existante (`get_active_projects_for_user`, tools F047), conforme YAGNI.

**Alternatives considérées** :
- *Charger toutes les réponses critère dans le contexte* (Q2=C) : coût tokens élevé, rejeté.
- *Nouvel outil de recherche d'assessment par nom* (Q2=B pur) : redondant, `list_projects` + `list_project_esg_assessments` couvrent déjà le besoin une fois le résumé proactif en place — rejeté.

---

## D3 — Génération réelle du document de candidature (FR-003a, Q1=B)

**État actuel** :
- Le tool chat `export_application` (`application_tools.py:424`) est un **stub** : `_export_application` (`:151`) retourne un chemin factice `/uploads/applications/{id}.{fmt}` **sans écrire de fichier**.
- Le **vrai** export existe : `app/modules/applications/export.py:136` `export_application(application, format) -> (bytes, content_type, filename)` (rendu DOCX via python-docx, PDF). Exposé par l'endpoint REST `POST /api/applications/{id}/export` (`router.py:192`).

**Décision** : câbler le tool chat `export_application` au vrai module `applications/export.py` : générer les bytes, écrire le fichier sous `/uploads/applications/{id}.{fmt}`, puis l'**enregistrer comme document utilisateur** (table `documents`) afin qu'il apparaisse dans `/documents` (FR-004). Retourner au LLM l'URL réelle téléchargeable.

**Enregistrement du document (lève U2)** : le modèle `Document` (`models/document.py`, table `documents`) expose les champs nécessaires (`user_id`, `account_id`, `filename`, `original_filename`, `mime_type`, `file_size`, `storage_path`, `status`, `document_type`). Le service `documents/service.py` ne fournit que `upload_document(...)` (pour un `UploadFile` entrant) — il **manque** une fonction pour enregistrer un fichier **déjà généré sur disque**. Décision : ajouter une petite fonction `register_generated_document(db, *, user_id, account_id, storage_path, original_filename, mime_type, file_size, document_type)` dans `documents/service.py` qui insère la ligne `Document` (status final, pas d'analyse OCR). Le tool `export_application` l'appelle après écriture du fichier. `mime_type` selon format (`application/vnd.openxmlformats-officedocument.wordprocessingml.document` pour docx, `application/pdf` pour pdf).

**Séquence conversationnelle attendue** (orchestrée par prompt, non par code) : `create_fund_application` → générer les sections clés manquantes (`generate_application_section`) → `export_application` qui produit le fichier réel. Le document compile sections + checklist + infos projet/offre (lève C1 : ne jamais exporter un dossier sans contenu de section clé).

**Rationale** : réutilise le moteur de rendu existant (principe VII) ; supprime l'incohérence stub/réel qui faisait croire à une génération inexistante.

**Format par défaut** : **DOCX** (éditable par la PME), cohérent avec F009. `export.py::export_application` gère déjà docx et pdf.

---

## D4 — Gating ESG avant génération (FR-003b, Q4=A)

**État actuel** :
- La couverture/critères manquants d'une évaluation sont calculés et stockés (`project_esg_assessments.missing_criteria`, `coverage_rate`) ; les critères `is_required` du référentiel sont identifiables (`_load_applicable_criteria`, `Criterion.is_required`).
- Les critères « effectifs » d'une **offre** (fonds × intermédiaire) sont calculés par `compute_effective_offer` (F07, « le plus restrictif gagne »).

**Décision** : avant de produire le dossier/document, le chatbot DOIT vérifier que les critères ESG **requis** du référentiel associé à l'offre sont couverts par l'évaluation ESG-projet du projet cible. Si des critères requis manquent → **ne pas générer** ; retourner la liste des critères manquants et guider l'utilisateur pour les compléter (réutilise le parcours US2 / `save_project_esg_criterion`). Implémenté comme **garde amont** dans le tool de génération (et reflété dans la directive prompt).

**Résolution offre→référentiel (lève U1)** : il n'existe **aucun** FK direct `offer.referential_id`/`project.referential_id` (vérifié dans `models/offer.py`, `models/project.py`). En revanche la fonction existante `app/modules/esg/multi_referential_service.py:512` `compute_referential_score_for_offer(...)` (déjà utilisée par le matching F045, `matching_service.py:277,1356`) **résout déjà** le référentiel pertinent pour une offre (fallback Mefali + bottleneck fonds/intermédiaire). Le gating DOIT **réutiliser** cette fonction pour obtenir le référentiel applicable et ses critères `is_required`, puis comparer à `covered_criteria`/`missing_criteria` de l'évaluation ESG-projet du `project_id`. Aucune nouvelle table ni colonne.

**Rationale** : Q4=A. Évite de produire un dossier non soumissionnable ; relie naturellement les deux problèmes (la mémoire ESG restaurée par D2 alimente ce gating). Réutiliser `compute_referential_score_for_offer` évite de réinventer la logique de mapping et garantit la cohérence avec le matching F045.

---

## D5 — Parité chat/UI + bouton « Candidater » (FR-013, FR-014, FR-015, FR-016, FR-006)

**État actuel** :
- Frontend : `handleApply(offerId)` (`[offer_id].vue:89`) fait `router.push('/financing/offers/${offerId}/apply')` — **route inexistante**, aucun appel API. `activeProjectId` est disponible via `route.query.project_id` (`:34`).
- Backend : `POST /api/applications/` (`router.py:42`) + `create_application(service)` (`service.py:67`) acceptent `fund_id, match_id, intermediary_id` — **pas** `offer_id`/`project_id`, **pas de dédup**. Le tool chat, lui, lie `offer_id`/`project_id` par assignation directe après création (`application_tools.py:204-226`).

**Décision** :
1. **Backend** : étendre `ApplicationCreate` (schemas) avec `offer_id?`/`project_id?` ; `create_application(service)` résout `fund_id`/`intermediary_id` depuis l'offre (comme le tool) et lie `project_id`. Ajouter une **dédup** : si un dossier `draft` existe déjà pour `(user, project, offer)`, le **réutiliser** plutôt que créer un doublon (FR-006). Refactoriser le tool chat pour appeler le même chemin service (parité FR-016).
2. **Frontend** : réécrire `handleApply` pour appeler un composable `useApplications().createApplication({ offerId, projectId })` → `POST /api/applications/`, puis naviguer vers `/applications/{id}` (ou `/documents`) en cas de succès ; afficher un message d'erreur/guidage en cas d'échec ou de contexte incomplet (FR-015).

**Rationale** : un seul chemin de création (service partagé) garantit l'équivalence des dossiers (FR-016) et la dédup centralisée. Supprime le clic mort.

**Alternatives considérées** :
- *Créer la page `/financing/offers/[id]/apply.vue`* : un wizard complet est hors périmètre (le but est de débloquer la création, pas de refondre le tunnel) — rejeté pour le MVP ; navigation vers le dossier existant suffit.

---

## Synthèse des décisions

| # | Sujet | Décision | Fichiers impactés |
|---|-------|----------|-------------------|
| D1 | Disponibilité outil chat | Union nœud(intention)+page, troncature priorisée | `tool_selector.py` |
| D2 | Mémoire ESG | Résumé proactif au démarrage + lecture à la demande | `chat.py`, `ConversationState`, prompts `nodes.py` |
| D3 | Document réel | Câbler `export_application` chat au vrai export + enregistrer doc | `application_tools.py`, `applications/export.py`, `documents` |
| D4 | Gating ESG | Bloquer génération si critères requis manquants + guidage | tool de génération, prompts |
| D5 | Parité + bouton | `offer_id`/`project_id` + dédup côté service ; `handleApply` → API | `schemas.py`, `service.py`, `router.py`, `[offer_id].vue`, `useApplications.ts` |

**Aucune migration Alembic.** Toutes les inconnues sont résolues → prêt pour Phase 1.
