# Phase 0 — Research : F21 Dashboard par Offre + Rapport Carbone PDF

**Date** : 2026-05-08
**Spec** : [spec.md](./spec.md)

Aucune entrée NEEDS CLARIFICATION dans le Technical Context. Cette section consolide les choix techniques, les patterns réutilisés depuis les features mergées et les rationales pour les nouveaux artefacts.

## R1 — Architecture du rapport carbone PDF

**Décision** : Reproduire à l'identique le pipeline du rapport ESG F06 :
- WeasyPrint (HTML→PDF) pour le rendu final.
- Jinja2 pour les templates.
- matplotlib pour la production de graphiques SVG (pie chart breakdown, bar chart comparaison sectorielle, line chart évolution multi-années).
- FastAPI BackgroundTasks pour l'asynchrone.
- Stockage local sous `/uploads/reports/` (existe).

**Rationale** : pile déjà en production depuis F06, dépendances installées, équipe rodée, complexité minimale. Évite l'introduction de Celery (interdit par principe constitutionnel VII Simplicité tant qu'aucun besoin réel ne le justifie).

**Alternatives considérées** :
- ReportLab (rejeté : moins flexible pour le styling FR riche).
- Puppeteer/Chromium headless (rejeté : empreinte mémoire et complexité d'install).
- Génération synchrone (rejeté : la cible p95 < 10 s autorise l'asynchrone et améliore l'UX en chat).

## R2 — Granularité « par Offre » du dashboard

**Décision** : Refactor `_get_financing_summary` (`backend/app/modules/dashboard/service.py`) pour retourner, en plus des compteurs existants nécessaires aux autres consommateurs, un nouveau champ `applications_by_offer: list[ApplicationCard]` borné à 5 entrées triées par `last_activity_at` desc. Conservation de `application_statuses` historique le temps d'une transition en lecture seule.

**Mapping étape humaine** (FR-003) — extrait :

| status BDD | libellé étape FR |
|---|---|
| `draft` | Préparation dossier |
| `submitted_to_intermediary` | Instruction par {intermediaire} |
| `submitted_to_fund` | Dossier déposé au fonds |
| `under_review` | Évaluation en cours |
| `accepted` | Accepté |
| `rejected` | Rejeté |
| `withdrawn` | Retiré |
| `funded` | Financé |

**Rationale** : la table `fund_applications` possède déjà `offer_id` (F07) ; on rejoint Offer/Fund/Intermediary en une seule requête. Le tri `last_activity_at` réutilise `updated_at` ou un calcul max(updated_at, created_at, snapshot_at).

**Alternatives** :
- Endpoint séparé `/api/dashboard/applications` (rejeté : 1 round-trip de plus, complexifie le rendu initial).
- Calcul côté frontend depuis liste paginée (rejeté : viole SC-001 latence).

## R3 — Carte UEMOA des intermédiaires actifs

**Décision** : Endpoint `GET /api/dashboard/active-intermediaries` retournant `list[ActiveIntermediary]`. Frontend consomme via `<IntermediariesMap>` qui injecte les coordonnées dans `<MapBlock>` (F11) avec `markers[].type = "intermediary"`.

**Définition d'« actif »** : intermédiaire lié à au moins une candidature `status NOT IN ('rejected', 'withdrawn', 'funded', 'closed')` OU à un projet ouvert (`status NOT IN ('cancelled', 'closed')`) appartenant au compte courant.

**Fallback géographique** : nouveau module `backend/app/core/uemoa_capitals.py` qui exporte `UEMOA_CAPITAL_COORDINATES: dict[str, tuple[float, float]]` (8 entrées BEN/BFA/CIV/GNB/MLI/NER/SEN/TGO). Les coordonnées proviennent de Public Domain Natural Earth + cohérence avec `UEMOA_COUNTRY_CENTROIDS` de F11. Le payload signale `is_fallback_capital=true` quand la résolution passe par ce dictionnaire.

**Rationale** : F11 fournit le composant de carte ; on n'introduit aucun nouveau service de géocodage. Le fallback applicatif évite les markers fantômes pour les intermédiaires sans lat/lon (saisis par F09 en flux progressif).

**Alternatives** :
- API externe Nominatim (rejeté : dépendance réseau, latence, conformité RGPD).
- Skipper les intermédiaires sans coordonnées (rejeté : viole FR-006 et SC-004).

## R4 — Sourçage F01 dans le PDF carbone

**Décision** : Réutiliser le module `app/modules/sources/` (F01) et le validator `source_required.py` pour collecter les sources et générer l'annexe.

Pipeline du `sources_collector.py` :
1. Charger les `CarbonEmissionEntry.factor_id` du bilan → résoudre vers `Source` via `EmissionFactor.source_id` (F17).
2. Charger les `tool_call_logs` du bilan filtrés sur `tool_name='cite_source'` pour les chiffres injectés par le LLM dans le résumé.
3. Numéroter les sources uniques `[1], [2], …` dans l'ordre d'apparition.
4. Pour les équivalences pédagogiques (km voiture / vols / foyers / FCFA), définir une whitelist de facteurs sourcés (ADEME Base Carbone v23) ; à défaut, libellé « Recommandation générale (non sourcée) ».
5. Le validator `source_required.py` est invoqué après rendu Jinja2 sur le HTML pour vérifier qu'aucun chiffre nu n'apparaît hors annexe.

**Annexe** : template Jinja2 partial `_carbon_appendix_sources.html` (calqué sur `_appendix_sources.html` F06/F13).

**Rationale** : conformité totale F01, traçabilité auditable, expérience cohérente avec le rapport ESG.

**Alternatives** :
- Sources hardcodées dans le template (rejeté : viole F01).
- Sourçage manuel en post-traitement (rejeté : pas testable).

## R5 — Génération asynchrone et anti-concurrence

**Décision** : `POST /api/reports/carbon/{assessment_id}/generate` :
1. Vérifie ownership via `account_id` (RLS F02).
2. Vérifie `assessment.is_finalized` → 422 si false (FR-017).
3. Vérifie qu'aucun `Report(report_type='carbon', assessment_id=X, status IN ('pending','generating'))` n'existe → 409 sinon (FR-018).
4. INSERT `Report(status='pending')`.
5. `BackgroundTasks.add_task(_render_carbon_pdf, report_id)` qui :
   - SET `status='generating'` ;
   - rend HTML Jinja2 + WeasyPrint → fichier ;
   - SET `status='ready'` + `file_path` ou `status='failed'` + `error_message`.
6. Retourne 202 Accepted avec `report_id` et `status='pending'`.

**Anti-concurrence** : index existant ou contrainte applicative — un SELECT FOR UPDATE/check explicite avant INSERT suffit puisque la table Report a déjà `assessment_id`. Si nécessaire, ajouter un index partiel applicatif via SQLAlchemy filter (pas de migration). Aucune nouvelle contrainte SQL.

**Notification frontend** : polling `/api/reports/{id}` (existe F06) toutes les 2 s avec timeout 30 s, puis toast « Rapport prêt » + bouton télécharger.

**Rationale** : pattern F06 réplicable, latence p95 confortable.

**Alternatives** :
- WebSocket SSE (rejeté : surdimensionné — F06 utilise déjà polling).
- Verrou Redis (rejeté : interdit par principe VII tant que pas justifié).

## R6 — Tool LangChain `generate_carbon_report`

**Décision** : Ajouter dans `app/graph/tools/carbon_tools.py` :

```python
class GenerateCarbonReportArgs(BaseModel):
    """Args du tool generate_carbon_report (Pydantic v2 strict)."""

    assessment_id: UUID = Field(..., description="Identifiant du bilan carbone à exporter en PDF")
```

Retour structuré : `{ok: bool, report_id: UUID, status: Literal['pending','generating','ready','failed'], message: str}`.

**Activation** :
- Exposé dans `MODULE_TOOL_MAPPING['carbon']`.
- Exposé dans `PAGE_TOOL_MAPPING['carbon_results']` (préc. existante).
- Garde ownership via account_id et user_id depuis `RunnableConfig`.

**Rationale** : Module 7.2 explicite que la PME peut demander le rapport en chat. Tool calling pattern F12 utilisé.

**Alternatives** :
- Injection en GLOBAL_WHITELIST (rejeté : tool très spécifique au module Carbone).

## R7 — ScoreCard cliquable vers sources

**Décision** : Étendre `frontend/app/components/dashboard/ScoreCard.vue` avec :
- Slot ou prop `sources?: Source[]` (composant `<SourceLink>` F01 existant).
- Si `sources && sources.length > 0` → icône `<SourceLink>` cliquable qui ouvre `<SourceModal>`.
- Sinon → badge `<Badge variant="muted">Non sourcé</Badge>`.

Côté backend, ajouter dans le payload `dashboard.summary` les champs `esg.sources`, `carbon.sources`, `credit.sources` (typés `list[SourceRef]`). Source de vérité = `SourceService.list_for_score(account_id, score_type, score_id)` qui agrège depuis `tool_call_logs` (cite_source) et `referential_indicators` (F13).

**Rationale** : composant existant F01 + F13. Pas de nouveau composant.

**Alternatives** :
- Modal ad-hoc carbone (rejeté : duplication).

## R8 — Audit log F03

**Décision** : Hooks F03 déjà actifs sur :
- `Report.create / update` (entité Auditable).
- `GET /api/admin/*` (middleware admin).

Ajouts :
- Le router `POST /api/reports/carbon/{id}/generate` est sous `Depends(get_current_user)` ; le service exécute dans un `source_of_change_scope('manual')` (PME directe) ou `source_of_change_scope('llm')` quand invoqué via le tool (le décorateur `@_with_llm_source` du carbon_node propage déjà le contexte).
- Pas d'écriture explicite supplémentaire ; les events `create:Report` + transitions de statut suffisent.
- Téléchargement PDF : ajouter une trace explicite via `AuditService.record_admin_view`-équivalent côté PME ? Décision : non, F03 ne loggue les `view_*` que pour l'admin. Le download est suffisamment tracé par `view_self` implicite. À reconsidérer post-MVP.

**Rationale** : le mécanisme F03 est conçu pour être transparent ; aucune ligne de code supplémentaire requise pour le nominal.

## R9 — Format des dates et i18n

**Décision** : Filtre Jinja2 `format_date_fr(value)` qui renvoie `DD/MM/YYYY` (réutilise helper F06 si déjà présent, sinon nouveau dans `app/lib/date_fr.py`).

Frontend : composable `useDateFormat()` ou helper inline `Intl.DateTimeFormat('fr-FR', {dateStyle: 'short'})`.

**Rationale** : conformité FR-015 sans dépendance lourde (pas de moment.js).

## R10 — Tests et couverture

**Décision** :
- Backend : tests unitaires sur `service.py`, `pdf_renderer.py`, `chart_builder.py`, `sources_collector.py`, `equivalences.py`, `schemas.py`, `uemoa_capitals.py`, refactor `dashboard.service`. Tests intégration sur les 2 nouveaux endpoints + endpoint dashboard summary refactoré + isolation RLS F02.
- Frontend : Vitest sur `ApplicationStatusCard.vue`, `IntermediariesMap.vue`, `CarbonReportButton.vue`, `ScoreCard.vue` (extension F21), `useCarbonReports.ts`, `useDashboard.ts` (extension).
- E2E Playwright : 1 fichier `F21-dashboard-carbon-report.spec.ts` avec 4 scénarios : (i) 3 cards par offre ; (ii) carte intermédiaires + popup ; (iii) génération PDF + téléchargement ; (iv) score cliquable → SourceModal.
- Cible globale ≥ 80 % sur le périmètre F21 (mesure backend par `pytest-cov` sur les chemins F21 ; frontend par `vitest --coverage`).

**Rationale** : conformité Test-First (NON-NEGOTIABLE).

## R11 — Performance et cache

**Décision** :
- Dashboard : éviter N+1 via `selectinload(FundApplication.offer).selectinload(Offer.fund)` et idem `Offer.intermediary`. Aucune mise en cache (les valeurs changent fréquemment).
- Génération PDF : seuil < 10 s couvert par matplotlib + WeasyPrint sur ~30 entrées. Mesure post-impl + flag `slow` si dépassement.

**Rationale** : conformité FR-028 / FR-029.

## R12 — Hors-scope confirmé

Confirmation des exclusions de la spec :
- Dashboard customisable drag&drop : rejeté.
- Comparaison période M-1 / cohort comparison : rejeté.
- Notifications push browser : rejeté (toast in-app suffit).
- Export PDF du dashboard : rejeté (le rapport carbone et le rapport ESG suffisent).
- Partage public anonymisé : rejeté.

## Synthèse

Aucune ambiguïté résiduelle. Toutes les dépendances sont déjà mergées et stables. Les 9 sections du PDF, les 2 nouveaux endpoints REST, le tool LangChain, les composants Vue, les tests sont prêts à être traduits en data-model + contracts (Phase 1) puis tasks (Phase 2).
