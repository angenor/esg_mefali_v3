# Phase 0 — Research : F15 Génération de Dossiers par Offre

**Spec** : 041 | **Branch** : feat/F15-generation-dossiers-par-offre | **Date** : 2026-05-08

Ce document résout les zones grises techniques identifiées dans `plan.md` Technical Context et dans la spec. Aucune zone marquée NEEDS CLARIFICATION ne subsiste après cette recherche.

## R-001 — `down_revision` exact pour la migration 041

**Decision** : `down_revision = '040_carbon_report_dashboard'`. Vérifier en début d'implémentation via `cd backend && alembic heads`. Si un head plus récent existe (par exemple migration ajoutée par une feature inter-temporelle), basculer sur ce head — la spec acte le **principe** : F15 reprend la chaîne principale Alembic à son head courant.

**Rationale** :
- F21 (dernière feature mergée, branche `feat/F21-dashboard-par-offre-rapport-carbone`, `_alembic_or_migration = false`) n'a pas créé de migration.
- F22 et F23 ont mergé `032_add_validation_error_tool_call_logs` et `033_create_skills` — leur down_revision pointent en arrière de la chaîne `02x` et ne forment **pas** un head compatible avec la chaîne `03x` principale.
- La dernière migration `03x` mergée et appliquée en prod est probablement `040_carbon_report_dashboard` (F20 carbon report dashboard). À reconfirmer concrètement.

**Alternatives considered** :
- Pointer sur `033_create_skills` : rejeté — mélange les chaînes `02x→033` et `03x→040`, casse l'historique linéaire.
- Créer un merge migration : rejeté — surchargerait F15 d'une dette de dette d'arbre Alembic non liée. Si nécessaire, le merge migration sera une tâche distincte (pré-F15 ou hotfix).

**Action en Phase 2** : tâche T-mig-001 commence par `alembic heads` et fixe le `down_revision` factuel.

## R-002 — Politique RLS pour `templates_dossier`

**Decision** : `templates_dossier` ajouté à `EXEMPT_MODELS` côté F03 audit (catalogue admin-only sans `account_id`). RLS PostgreSQL `ENABLE+FORCE` avec 2 policies :
- `templates_public_read_published` : `FOR SELECT USING (status = 'published' AND valid_to IS NULL)` — lecture publique du catalogue actif.
- `templates_admin_full_access` : `FOR ALL USING (current_setting('app.current_role', true) = 'ADMIN')`.

**Rationale** : pattern déjà éprouvé sur `skills` (F23), `funds`/`intermediaries` (F07), `referentials` (F13). Catalogue partagé entre tous les comptes ; pas de `account_id` propre au template.

**Alternatives considered** :
- Templates par compte (multi-tenant strict) : rejeté — un template officiel GCF/BOAD est partagé par toutes les PME, pas duplicable. Diminuerait la maintenabilité.
- RLS désactivée : rejeté — incompatible avec le principe V de la constitution.

## R-003 — Pattern snapshot immuable F04 sur F15

**Decision** : Étendre le helper `build_snapshot_data(application)` existant F04 (cf. `app/modules/applications/snapshot.py` côté F04) avec un nouveau bloc `template_snapshot` :

```python
{
  "captured_at": "2026-05-08T14:32:11Z",
  "schema_version": "f15.v1",
  "template_snapshot": {
    "id": "<uuid>",
    "version": "1.2",
    "language": "fr",
    "sections": [...],
    "required_documents": [...],
    "tone": "...",
    "vocabulary_hints": {...},
    "anti_patterns": [...],
    "source_id": "<uuid>",
    "skill_id": "<uuid>",
    "skill_version": "1.0.0"
  },
  "offer_snapshot": {...},     // déjà F04
  "project_snapshot": {...},   // F06 + F04
  "company_profile_snapshot": {...},
  "scores_snapshot": {...},
  "source_ids_cited": [...]
}
```

**Rationale** : minimum d'invention, maximum de réutilisation du pattern F04 (`validate_immutable`, log structuré INFO + warning > 100 KB, `application.snapshot_at` + `application.snapshot_data` JSONB). F15 ne change pas la structure du modèle — il étend uniquement le contenu sérialisé.

**Alternatives considered** :
- Snapshot séparé `template_snapshots` : rejeté — duplique le pattern F04, casse l'atomicité de la garde anti-mutation.
- Snapshot non versionné (références par `template_id` seul) : rejeté — viole FR-026 et le principe de versioning F04.

## R-004 — Skills F23 référencées par défaut

**Decision** : Le seed F15 référence ces Skills (déjà créées par F23 seed) :

| Template seed | Skill F23 référencée |
|---------------|----------------------|
| Subvention GCF via BOAD — Mitigation FR | `skill_dossier_gcf_via_boad` |
| Subvention GCF via BOAD — Mitigation EN | `skill_dossier_gcf_via_boad` (prompt EN dans la Skill) |
| Prêt concessionnel SUNREF/AFD FR | `skill_score_gcf` (fallback bancaire) |
| Equity SDG Impact Fund FR | `skill_esg_diagnostic` |
| Blending FEM/UNDP FR | `skill_score_gcf` |
| Subvention génériquue (fallback subvention) | `skill_esg_diagnostic` |
| Prêt génériquue (fallback prêt) | `skill_esg_diagnostic` |
| Equity génériquue (fallback equity) | `skill_esg_diagnostic` |
| Blending génériquue (fallback blending) | `skill_esg_diagnostic` |

**Rationale** : F23 seed a publié 3 Skills MVP. F15 ne crée pas de Skill — uniquement des références. Si un admin veut un template plus spécialisé (ex. skill GCF Carbone), il crée la Skill via F09, puis publie le template.

**Alternatives considered** :
- Skill par défaut `skill_default_application_drafter` : rejeté — viole le principe F23 « 1 Skill = 1 playbook métier précis ». Le seed initial mappe sur les Skills existantes.

## R-005 — Fusion tool LangChain `create_fund_application` (BUG-003)

**Decision** : Conserver `app/graph/tools/application_tools.py::create_fund_application` (signature plus complète, accepte `project_id` et `language`). Retirer la version dupliquée de `app/graph/tools/financing_tools.py`. Test de garde-fou `tests/graph/tools/test_no_duplicate_create_fund_application.py` :

```python
def test_only_one_create_fund_application_tool():
    from app.graph.tools import application_tools, financing_tools
    names = [t.name for t in (*application_tools.APPLICATION_TOOLS, *financing_tools.FINANCING_TOOLS)]
    assert names.count("create_fund_application") == 1, (
        f"Tool 'create_fund_application' duplicated: {names}"
    )
```

**Rationale** : SC-003 exige une assertion automatisée. Le test échoue si quiconque réintroduit le doublon — protection en CI permanente.

**Alternatives considered** :
- Conserver les deux et désambiguïser par préfixe : rejeté — viole F23 anti-confusion (LangGraph ne distingue pas les tools de même nom dans le même bind).
- Garder `financing_tools.create_fund_application` : rejeté — moins complet, ne porte pas `language`.

## R-006 — Bug `fund.max_amount` (BUG-002)

**Decision** : Refactor `app/graph/tools/application_tools.py::_simulate_financing` pour lire les properties Money typed F04 :
```python
max_amt = (fund.max_amount_money or Money.from_columns(fund.max_amount_xof, "XOF")).amount
min_amt = (fund.min_amount_money or Money.from_columns(fund.min_amount_xof, "XOF")).amount
```

avec fallback explicite si Money non hydraté (legacy). Test `tests/graph/tools/test_application_tools_money_fix.py` parametré sur 12 fonds seed F07.

**Rationale** : F04 a déjà introduit la convention `<field>_money` property. F15 n'invente rien — applique simplement la convention existante.

**Alternatives considered** :
- Lire directement `fund.max_amount_xof` : rejeté — dette technique car les colonnes legacy `*_xof` sont marquées dépréciées depuis F04 (drop reporté ≥ 2 sprints).
- Renommer en `simulate_financing_v2` : rejeté — casse la rétro-compatibilité pour rien.

## R-007 — Idempotence `(project_id, offer_id)` (FR-023)

**Decision** :
1. Migration : ajout d'un index unique partiel `idx_fund_applications_project_offer_unique ON fund_applications(project_id, offer_id) WHERE status != 'cancelled'` (PostgreSQL).
2. Service `create_application(project_id, offer_id, ...)` :
```python
try:
    application = ...
    db.add(application)
    await db.flush()
except IntegrityError:
    await db.rollback()
    existing = await db.scalar(select(FundApplication).where(
        FundApplication.project_id == project_id,
        FundApplication.offer_id == offer_id,
        FundApplication.status != 'cancelled'
    ))
    return existing, True  # tuple (resource, replayed)
return application, False
```
3. Router : si `replayed=True`, retourner HTTP 200 avec header `X-Mefali-Idempotent: replay` et le body de la ressource existante. Sinon HTTP 201.

**Rationale** : conforme à la décision Clarifications 2026-05-08 ; pattern idempotent standard REST.

**Alternatives considered** :
- HTTP 409 Conflict : rejeté en clarification — UX dégradée.
- Lock applicatif via Redis : rejeté — YAGNI (PR très faibles, contention quasi nulle).

## R-008 — Calcul checklist union (FR-015 → FR-019)

**Decision** : nouveau service `app/modules/applications/checklist_service.py::compute_union_checklist(offer_id) -> list[ChecklistItem]`. Logique :

1. Charger `effective_offer = compute_effective_offer(offer_id)` (helper F07 existant).
2. Itérer `fund.required_documents + intermediary.required_documents`.
3. Normaliser chaque titre : `unicodedata.normalize('NFKD', title.lower()).encode('ascii', 'ignore').decode().strip()`. Cache mémoire local par cohérence (jamais persisté).
4. Grouper par titre normalisé. Pour chaque groupe :
   - `mandatory = any(d['mandatory'] for d in group)` (le plus restrictif gagne — FR-016).
   - `source_ids = list(unique({d['source_id'] for d in group}))` (deux sources gardées — FR-017).
   - `origin = 'both' if len({d._origin for d in group}) > 1 else d._origin` (`'fund'` ou `'intermediary'`) — FR-018.
5. Retourner liste triée par `(mandatory desc, title)`.

**Rationale** : algorithme prévisible, pas de LLM (déduplication sémantique = post-MVP). Cache mémoire évite les recomputations à chaque appel REST.

**Alternatives considered** :
- Persister la checklist en base pour l'application : rejeté — dérive avec le template (qui peut évoluer). Snapshot F04 capture l'état au moment de soumission ; entre-temps la checklist est un calcul à la volée.
- Déduplication sémantique LLM : explicitement hors scope MVP (Assumptions).

## R-009 — Intégration attestation F08 dans le PDF (FR-021)

**Decision** : Pipeline export PDF dans `app/modules/applications/export.py::export_to_pdf(application_id, with_attestation=False)` :

1. Render le HTML du dossier via Jinja2 (template `application_pdf.html` + partials).
2. Render le PDF via WeasyPrint.
3. Si `application.attestation_id` est lié et l'attestation est `active`, charger l'attestation F08 (URL PDF interne `/api/attestations/{id}/pdf`), puis :
   - Option A (retenue) : générer un partial Jinja2 `_attestation_appendix.html` qui inline le QR code (data URI base64) + ID public + signature lisible. WeasyPrint produit le PDF en un seul rendu (pas de merge externe).
4. Si attestation expirée/révoquée au moment du render, exclure + ajouter un bloc « Attestation indisponible » + log structuré WARNING (FR-022).

**Rationale** : un seul rendu WeasyPrint = simplicité, traçabilité unifiée, pas de dépendance pypdf/PyMuPDF supplémentaire pour merger des PDFs.

**Alternatives considered** :
- Merge externe avec PyMuPDF : rejeté — complexité supplémentaire, dépendance déjà présente uniquement pour OCR (F04 documents). Pas de besoin de mux PDF distincts en MVP.
- Générer un PDF séparé et le joindre comme pièce attachée du dossier : rejeté — viole FR-021 (« annexée en dernière page »).

## R-010 — Performance génération première section (SC-007)

**Decision** : Cible ≤ 15 s p95. Stratégie :
- Stream tokens via SSE (déjà en place côté chat F12) — la PME voit les premiers mots en < 2 s.
- Charger le contexte (profil + project + offer + template + skill) en parallèle via `asyncio.gather` plutôt que séquentiellement.
- Cache mémoire short-TTL (60 s) sur `compute_effective_offer(offer_id)` (cohérent F07).
- Limiter le `prompt_expert` injecté à 5000 tokens (cohérent F23 cap tiktoken).

**Rationale** : les bottlenecks identifiés sont (a) le call OpenRouter (~3-8 s pour Claude Sonnet) et (b) le chargement séquentiel des entités. Le parallélisme + le streaming ramènent le ressenti utilisateur < 15 s.

**Alternatives considered** :
- Pré-calcul de la première section en background : rejeté — overhead opérationnel (Celery), YAGNI.

## R-011 — Format de stockage des fichiers exportés (FR-030)

**Decision** : Stockage local sous `/uploads/applications/<account_id>/<application_id>/dossier-<offer_code>-<YYYY-MM-DD>.pdf`. Cohérent F06.
- `<offer_code>` : slug normalisé `${fund.code}-${intermediary.code}` (ex. `gcf-boad`, `sunref-afd`).
- Date au format ISO dans le nom de fichier (tri alphabétique = chronologique). Format français (jj/mm/aaaa) **dans** le contenu PDF.
- Permissions fichier 0640, propriétaire backend uvicorn.
- Path stocké dans `fund_applications.export_path` (colonne ajoutée par migration 041).

**Rationale** : continuité F06. Pas de migration MinIO/S3 en F15 (Assumptions).

**Alternatives considered** :
- Stockage en BLOB BDD : rejeté — viole VII (simplicité), volumétrie incompatible.
- MinIO direct : rejeté — Assumptions hors scope.

## R-012 — Détection de langue automatique côté tests (SC-006)

**Decision** : Pour les tests EN-only, utiliser `langdetect` ou regex heuristique simple (`re.search(r'\b(the|and|with|to|of)\b', text)` + ratio mots EN ≥ 60 %). En MVP, regex heuristique suffit (pas de nouvelle dépendance).

**Rationale** : SC-006 demande une assertion langue mais ne mandate pas de détection ML précise. Heuristique simple = 0 dépendance.

**Alternatives considered** :
- `langdetect` : rejeté — dépendance supplémentaire pour un test ; YAGNI.

---

## Synthèse des décisions

| Sujet | Décision finalisée |
|-------|---------------------|
| Migration | `down_revision = '040_carbon_report_dashboard'`, à reconfirmer à `alembic heads` |
| RLS templates | `EXEMPT_MODELS` + 2 policies (lecture published publique, admin full) |
| Snapshot | Extension du pattern F04 avec `template_snapshot` |
| Skills par défaut | Référencement des 3 Skills F23 existantes par instrument |
| Fusion tool BUG-003 | Conserver `application_tools.create_fund_application`, retirer celui de financing_tools, test garde-fou |
| Bug Money BUG-002 | Lecture properties `<field>_money` Money typed F04 + fallback legacy `*_xof` |
| Idempotence (project_id, offer_id) | Index UNIQUE partiel + service catch IntegrityError + header `X-Mefali-Idempotent: replay` |
| Checklist union | Service dédié, normalisation NFKD, mandatory most-restrictive, sources préservées |
| Attestation PDF | Inline via partial Jinja2 + WeasyPrint mono-rendu |
| Performance | asyncio.gather context + SSE streaming + cap 5000 tokens prompt expert |
| Stockage | Local `/uploads/applications/<account_id>/<application_id>/`, format date FR dans contenu, ISO dans nom |
| Détection langue tests | Regex heuristique simple, pas de nouvelle dep |

**Aucune zone NEEDS CLARIFICATION ne subsiste.**
