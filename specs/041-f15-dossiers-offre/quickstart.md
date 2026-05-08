# Quickstart — F15 Génération de Dossiers par Offre

**Spec** : 041 | **Branch** : feat/F15-generation-dossiers-par-offre

## 1. Pré-requis

- Branche `feat/F15-generation-dossiers-par-offre` checkout.
- venv backend activé : `source backend/venv/bin/activate`.
- BDD Postgres locale opérationnelle (compose ou docker-compose), ou SQLite en CI.
- Variables d'env : `OPENROUTER_API_KEY` (obligatoire pour tester la génération réelle), `DATABASE_URL`.
- Features prerequises mergées : F01, F02, F03, F04, F06, F07, F08, F09, F10, F23.

## 2. Migration Alembic

```bash
cd backend
source venv/bin/activate

# Vérifier le head courant
alembic heads
# attendu : 040_carbon_report_dashboard (à confirmer)

# Appliquer la migration F15
alembic upgrade head

# Round-trip de validation
alembic downgrade -1
alembic upgrade head
```

Le seed des templates fallback + 10 templates publiés est exécuté automatiquement par la migration.

## 3. Parcours développeur — Créer un template via API admin

```bash
# 1. Login admin (récupérer access_token)
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@esg-mefali.com","password":"<pwd>"}'

ADMIN_TOKEN="..."

# 2. Lister les Skills F23 disponibles
curl http://localhost:8000/api/admin/skills?status=published \
  -H "Authorization: Bearer $ADMIN_TOKEN"

SKILL_ID="..."   # par exemple skill_dossier_gcf_via_boad

# 3. Lister les sources F01 vérifiées
curl 'http://localhost:8000/api/sources?status=verified&q=GCF' \
  -H "Authorization: Bearer $ADMIN_TOKEN"

SOURCE_ID="..."

# 4. Créer le template (statut draft)
curl -X POST http://localhost:8000/api/admin/templates/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Dossier GCF via BOAD — Mitigation v1.0",
    "instrument_type": "subvention",
    "language": "fr",
    "offer_id": null,
    "sections": [
      {"key": "executive_summary", "title": "Résumé exécutif", "instructions": "Synthèse 1 page du projet, des objectifs ESG et du financement requis.", "target_length": 500, "required": true},
      {"key": "project_description", "title": "Description du projet", "instructions": "Contexte, technologie, localisation, partenaires. Cite au moins une source F01.", "target_length": 1500, "required": true},
      {"key": "esg_impacts", "title": "Impacts E-S-G", "instructions": "Quantifier les impacts environnementaux (tCO2e), sociaux, gouvernance.", "target_length": 1200, "required": true},
      {"key": "financial_plan", "title": "Plan financier", "instructions": "Montant demandé, contrepartie, échéancier décaissement.", "target_length": 1000, "required": true},
      {"key": "team", "title": "Équipe et gouvernance", "instructions": "Compétences clés, organigramme, conformité 4-yeux.", "target_length": 800, "required": true}
    ],
    "required_documents": [
      {"title": "Étude de faisabilité", "mandatory": true, "source_id": "<source_id_etude_gcf>", "origin": "fund"},
      {"title": "Plan d'\''affaires 5 ans", "mandatory": true, "source_id": "<source_id_business_plan>", "origin": "fund"}
    ],
    "tone": "formel IFI",
    "vocabulary_hints": {"emissions": ["GES", "tCO2éq"], "PME": ["entreprise"]},
    "anti_patterns": ["promesses non quantifiées", "absence de source pour les chiffres"],
    "skill_id": "'"$SKILL_ID"'",
    "source_id": "'"$SOURCE_ID"'"
  }'

TEMPLATE_ID="..."

# 5. (Avec un autre admin) publier le template (4-yeux)
curl -X POST http://localhost:8000/api/admin/templates/$TEMPLATE_ID/publish \
  -H "Authorization: Bearer $ADMIN_TOKEN_VERIFIER"
```

## 4. Parcours PME — Créer un dossier et le générer

```bash
# 1. Login PME
PME_TOKEN="..."

# 2. Lister projets F06
curl http://localhost:8000/api/projects -H "Authorization: Bearer $PME_TOKEN"
PROJECT_ID="..."

# 3. Lister offres F07 éligibles
curl http://localhost:8000/api/offers?project_id=$PROJECT_ID \
  -H "Authorization: Bearer $PME_TOKEN"
OFFER_ID="..."

# 4. Créer la candidature (idempotent)
curl -X POST http://localhost:8000/api/applications/batch \
  -H "Authorization: Bearer $PME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "'"$PROJECT_ID"'",
    "offer_ids": ["'"$OFFER_ID"'"],
    "language": "fr"
  }'

APPLICATION_ID="..."

# 5. Générer la première section
curl -X POST http://localhost:8000/api/applications/$APPLICATION_ID/section/generate \
  -H "Authorization: Bearer $PME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"section_key": "executive_summary"}'

# Le streaming SSE arrive sur /api/chat/stream avec event_type="generation_progress"

# 6. Attacher l'attestation F08 (si la PME en a une)
curl -X PUT http://localhost:8000/api/applications/$APPLICATION_ID/attestation \
  -H "Authorization: Bearer $PME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"attestation_id": "<attestation_id_F08>"}'

# 7. Exporter en PDF (avec attestation jointe)
curl -X POST http://localhost:8000/api/applications/$APPLICATION_ID/export \
  -H "Authorization: Bearer $PME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"with_attestation": true}' \
  -o dossier-test.pdf

# 8. Soumettre (déclenche le snapshot immuable F04)
curl -X PATCH http://localhost:8000/api/applications/$APPLICATION_ID/status \
  -H "Authorization: Bearer $PME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "submitted_to_intermediary"}'

# 9. Rejouer le scoring contre snapshot
curl -X POST http://localhost:8000/api/applications/$APPLICATION_ID/recompute-against-snapshot \
  -H "Authorization: Bearer $PME_TOKEN"
```

## 5. Parcours dev — Tests TDD locaux

```bash
cd backend && source venv/bin/activate

# Tests unitaires F15 uniquement
pytest tests/models/test_template_dossier.py \
       tests/modules/applications/test_template_service.py \
       tests/modules/applications/test_checklist_service.py \
       tests/modules/applications/test_snapshot_service_f15.py \
       tests/modules/applications/test_service_company_context_fix.py \
       tests/modules/applications/test_export_with_attestation.py \
       tests/modules/applications/test_router_idempotency.py \
       tests/graph/tools/test_application_tools_money_fix.py \
       tests/graph/tools/test_no_duplicate_create_fund_application.py \
       tests/graph/tools/test_template_tools.py \
       tests/alembic/test_migration_041.py \
       -v

# Couverture F15
pytest --cov=app.modules.applications --cov=app.models.template_dossier \
       --cov=app.graph.tools.template_tools --cov-report=term-missing \
       tests/modules/applications/ tests/graph/tools/test_template_tools.py
# Cible : ≥ 80 %

# Frontend
cd ../frontend
npm run test:unit -- src/composables/useApplications useChecklistUnion useAdminTemplates
npm run test:unit -- src/components/applications

# E2E Playwright
npx playwright test tests/e2e/F15-generation-dossiers-par-offre.spec.ts
```

## 6. Validation finale

| Critère | Commande / vérification |
|---------|--------------------------|
| Round-trip Alembic | `alembic upgrade head && alembic downgrade base && alembic upgrade head` |
| Couverture ≥ 80 % | `pytest --cov` sur le périmètre F15 |
| Bug-001 (company_context) | `pytest tests/modules/applications/test_service_company_context_fix.py -v` |
| Bug-002 (Money) | `pytest tests/graph/tools/test_application_tools_money_fix.py -v` |
| Bug-003 (doublon) | `pytest tests/graph/tools/test_no_duplicate_create_fund_application.py -v` |
| Snapshot immuable | `pytest tests/modules/applications/test_snapshot_service_f15.py::test_snapshot_immutable_post_submission -v` |
| Idempotence | `pytest tests/modules/applications/test_router_idempotency.py -v` |
| Multilingue EN | `pytest tests/modules/applications/test_template_service.py::test_generate_section_en -v` |
| Checklist union | `pytest tests/modules/applications/test_checklist_service.py -v` |
| RLS templates | `pytest tests/modules/admin/test_templates_router.py::test_pme_cannot_write_template -v` |
| 4-yeux publish | `pytest tests/modules/admin/test_templates_router.py::test_publish_requires_different_verifier -v` |

## 7. Troubleshooting

- **`alembic heads` retourne plusieurs heads** : un merge migration est nécessaire avant de descendre F15. Voir `docs/alembic-troubleshooting.md`.
- **Templates seed créés mais sans `source_id`** : la source `system://mefali/catalogue-templates` est créée par la migration 041 ; vérifier qu'elle est bien `verified`.
- **`AttributeError: fund.max_amount`** : régression du bug-002. Vérifier que le tool importé est `application_tools.simulate_financing` à jour, pas une version cachée.
- **Snapshot vide** : la candidature n'est pas en `submitted_*`. Le snapshot n'est créé qu'à la transition.
