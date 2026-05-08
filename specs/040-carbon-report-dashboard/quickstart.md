# Quickstart F21 — Dashboard par Offre + Rapport Carbone PDF

## Prérequis

- Branche : `feat/F21-dashboard-par-offre-rapport-carbone`
- Backend démarré : `cd backend && source venv/bin/activate && uvicorn app.main:app --reload`
- Frontend démarré : `cd frontend && npm run dev`
- Compte PME seedé avec : profil entreprise, ≥ 1 bilan carbone finalisé, ≥ 1 candidature liée à une offre F07.
- Aucune migration à appliquer (`alembic upgrade head` reste à `head` actuel).

## Scénario 1 — Voir 3 cards de candidatures par Offre

1. Authentifier un compte PME ayant 3 candidatures actives liées à 3 offres distinctes.
2. Ouvrir `/dashboard`.
3. Vérifier qu'au plus 5 cards `<ApplicationStatusCard>` apparaissent, triées par `last_activity_at` desc.
4. Chaque card affiche : nom du fonds, nom de l'intermédiaire (« Accès direct » si null), statut humain, prochaine échéance au format `DD/MM/YYYY` ou « Aucune échéance ».

## Scénario 2 — Voir la carte UEMOA des intermédiaires

1. Sur `/dashboard`, scroller jusqu'à `<IntermediariesMap>`.
2. Vérifier l'overlay des 8 pays UEMOA et un marqueur par intermédiaire actif.
3. Cliquer sur un marqueur → popup `{name, type, country, accreditations[], applications_count}` + lien « Voir la fiche ».
4. Si aucun intermédiaire actif → message « Vous n'avez pas encore d'intermédiaire actif » + lien `/financing/intermediaries`.

## Scénario 3 — Générer un rapport carbone PDF

1. Aller sur `/carbon/results` (bilan finalisé).
2. Cliquer sur le bouton « Générer rapport carbone PDF ».
3. Toast « Rapport en cours de génération ».
4. Polling automatique → toast « Rapport prêt » sous ~10 s.
5. Cliquer sur « Télécharger » → vérifier le PDF :
   - 9 sections : Cover, Synthèse, Breakdown, Comparaison sectorielle, Évolution multi-années, Plan de réduction, Équivalences, Méthodologie, Annexe Sources.
   - Toutes les dates au format `DD/MM/YYYY`.
   - Tous les chiffres clés référencés `[n]` ou libellés « Recommandation générale (non sourcée) ».
   - Annexe « Sources et références » numérotée avec libellé / éditeur / version / date / URL.

## Scénario 4 — Score ESG cliquable vers sources

1. Sur `/dashboard`, repérer la `<ScoreCard>` ESG.
2. Vérifier l'icône `<SourceLink>` à côté du score.
3. Cliquer → modale `<SourceModal>` avec liste des sources F01 / référentiels F13.

## Scénario 5 — Onglet Carbone sur /reports

1. Aller sur `/reports`.
2. Cliquer sur l'onglet « Carbone ».
3. Liste des rapports carbone de la PME, statut, date.
4. Cliquer « Télécharger » sur un rapport `ready` → fichier ouvert.

## Scénario 6 — Tool conversationnel

1. Ouvrir `/chat`, contexte page `carbon_results`.
2. Demander « Génère le rapport carbone de mon bilan 2024 ».
3. L'assistant invoque `generate_carbon_report(assessment_id=...)`.
4. Indicateur visuel `<ToolCallIndicator>` « Génération du rapport carbone… ».
5. Réponse texte avec `report_id` + statut `pending`. Notification toast quand `ready`.

## Vérifications backend rapides

```bash
# Lister les routes nouvelles
rg -n "active-intermediaries|reports/carbon" backend/app

# Tests F21
cd backend && source venv/bin/activate
pytest tests/unit/modules/reports/carbon -v
pytest tests/integration/test_carbon_report_endpoint.py -v
pytest tests/integration/test_dashboard_summary.py -v
```

## Vérifications frontend rapides

```bash
cd frontend
npm run test -- ApplicationStatusCard IntermediariesMap CarbonReportButton ScoreCard.f21
npx playwright test tests/e2e/F21-dashboard-carbon-report.spec.ts
```

## Audit log

- Vérifier que `POST /api/reports/carbon/{id}/generate` produit une entrée `audit_log(action='create:Report', source_of_change='manual'|'llm')`.
- Le téléchargement n'écrit pas d'entrée additionnelle (politique F03 MVP).

## Multi-tenant / RLS

- Tester avec un second compte (account_id différent) : `GET /api/dashboard/summary` ne renvoie aucune donnée du premier ; `GET /api/dashboard/active-intermediaries` filtre correctement ; `POST /api/reports/carbon/{id}/generate` sur un bilan d'un autre compte renvoie 403.

## Critères de validation

- ✅ 9 sections du PDF présentes
- ✅ Toutes les dates `DD/MM/YYYY`
- ✅ Tous les chiffres sourcés `[n]` ou libellés « Recommandation générale (non sourcée) »
- ✅ ApplicationStatusCard ≤ 5
- ✅ IntermediariesMap rend overlay UEMOA + markers
- ✅ ScoreCard cliquable → SourceModal
- ✅ Tool `generate_carbon_report` exposé dans `MODULE_TOOL_MAPPING['carbon']`
- ✅ RLS F02 isolation respectée
- ✅ Audit F03 trace les générations
- ✅ Couverture tests ≥ 80 %
