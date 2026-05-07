# Quickstart : F05 RGPD Mes Données + Consentements + Export/Suppression

Date : 2026-05-07
Branche : `feat/F05-rgpd-mes-donnees-consents` (alias SpecKit `027-rgpd-mes-donnees-consents`)

## Objectif

Documenter, pour un développeur attaquant la Phase B de F05, les chemins d'exécution les plus courts pour valider le bon fonctionnement de la feature à partir d'une checkout fraîche. Ce document remplace une lecture exhaustive du plan/specs pour les premières heures de travail.

## Pré-requis

- Le projet ESG Mefali v3 est cloné et la branche `feat/F05-rgpd-mes-donnees-consents` est checkée out.
- Docker + docker-compose installés.
- Python 3.12 + Node 20+ installés (ou conteneurs).
- `backend/venv/` créé et activé : `source backend/venv/bin/activate`.

## Démarrage local

```bash
# 1. Démarrer la DB
docker compose up postgres -d

# 2. Migrations (application des migrations existantes + F05)
cd backend && source venv/bin/activate
alembic upgrade head

# 3. Variables d'environnement supplémentaires F05 (à ajouter dans backend/.env)
echo 'EXPORT_URL_SIGNING_KEY=dev-only-replace-in-prod' >> .env
# SMTP_HOST optionnel : si absent, mailer.py logge dans audit_log (mode stub)

# 4. Backend
uvicorn app.main:app --reload --port 8000

# 5. Frontend (autre terminal)
cd frontend && npm install && npm run dev
```

## Smoke test manuel — happy path

### Étape 1 : Créer un compte avec privacy_policy_accepted=true

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPassword123!",
    "company_name": "Test PME",
    "privacy_policy_accepted": true,
    "privacy_policy_version": "v1.0"
  }'
```

→ Retour 201 avec JWT + audit_log `privacy_policy_accepted` inséré.

### Étape 2 : Voir l'inventaire

```bash
TOKEN=<jwt_de_l_etape_1>
curl http://localhost:8000/api/me/data/inventory \
  -H "Authorization: Bearer $TOKEN"
```

→ Retour 200 avec compteurs (tous à 0 ou 1 sauf consents=3 si on crée les essentials au register).

### Étape 3 : Lister les consentements

```bash
curl http://localhost:8000/api/me/consents \
  -H "Authorization: Bearer $TOKEN"
```

→ Retour 200 avec 7 consents : 3 essentials `granted=true`, 4 optionnels `granted=false`.

### Étape 4 : Accorder Mobile Money

```bash
curl -X POST http://localhost:8000/api/me/consents/mobile_money_analysis/grant \
  -H "Authorization: Bearer $TOKEN"
```

→ Retour 200 `{"granted": true, ...}`.

### Étape 5 : Vérifier que `require_consent` passe

```bash
# Endpoint stub à introduire dans Phase B
curl http://localhost:8000/api/credit/mobile-money/preview \
  -H "Authorization: Bearer $TOKEN"
```

→ Retour 200 (ou 501 stub) — pas de 403.

### Étape 6 : Révoquer Mobile Money

```bash
curl -X POST http://localhost:8000/api/me/consents/mobile_money_analysis/revoke \
  -H "Authorization: Bearer $TOKEN"
```

→ Retour 200 `{"granted": false, "revoked_at": "..."}`.

### Étape 7 : Vérifier que `require_consent` rejette

```bash
curl http://localhost:8000/api/credit/mobile-money/preview \
  -H "Authorization: Bearer $TOKEN"
```

→ Retour 403 avec `{"detail": {"detail": "Consentement Mobile Money requis", "consent_type": "mobile_money_analysis", "settings_url": "/mes-donnees/consentements"}}`.

### Étape 8 : Exporter les données

```bash
curl http://localhost:8000/api/me/data/export?format=json \
  -H "Authorization: Bearer $TOKEN" \
  -o export.zip
unzip -l export.zip
```

→ Listing : `README.md`, `data.json`, `documents/manifest.json`.

```bash
unzip -p export.zip data.json | jq '.account.id'
```

→ UUID du compte créé à l'étape 1.

### Étape 9 : Programmer la suppression

```bash
curl -X POST http://localhost:8000/api/me/account/schedule-deletion \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "password": "TestPassword123!",
    "confirmation_text": "SUPPRIMER"
  }'
```

→ Retour 200 `{"deletion_scheduled_at": "...", "cancel_url": "..."}`.

Vérifier en BDD :
```sql
SELECT id, deletion_scheduled_at FROM accounts WHERE email = 'test@example.com';
```

### Étape 10 : Annuler la suppression

```bash
curl -X POST http://localhost:8000/api/me/account/cancel-deletion \
  -H "Authorization: Bearer $TOKEN"
```

→ Retour 200 `{"cancelled_at": "..."}`. `deletion_scheduled_at` doit être à NULL.

### Étape 11 : Re-programmer + simuler J+30 + exécuter cron

```bash
# Re-programmer
curl -X POST http://localhost:8000/api/me/account/schedule-deletion \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password": "TestPassword123!", "confirmation_text": "SUPPRIMER"}'

# Simuler J+30 (avancer la date en BDD pour le test)
psql -d esg_mefali -c "UPDATE accounts SET deletion_scheduled_at = now() - interval '1 second' WHERE email = 'test@example.com';"

# Exécuter le cron
cd backend && source venv/bin/activate
python scripts/purge_scheduled_deletions.py

# Vérifier purge
psql -d esg_mefali -c "SELECT deleted_at, purge_in_progress FROM accounts WHERE id = '<UUID>';"
psql -d esg_mefali -c "SELECT count(*) FROM consents WHERE account_id = '<UUID>';"  # → 0
psql -d esg_mefali -c "SELECT count(*) FROM audit_log WHERE account_id = '<UUID>';"  # → 0 (anonymisé)
psql -d esg_mefali -c "SELECT count(*) FROM audit_log WHERE entity_id = '<UUID>' AND user_id IS NULL AND account_id IS NULL;"  # → > 0 (anonymisé conservé)
```

### Étape 12 : Page publique privacy

Ouvrir http://localhost:3000/legal/privacy dans un navigateur **privé** (sans JWT) → la page se charge sans redirection vers /login.

Vérifier sections :
1. Identité du responsable
2. Finalités et bases légales
3. Catégories de données
4. Durée de conservation
5. Sous-traitants
6. Transferts hors UE/UEMOA
7. Droits utilisateurs
8. Exercice des droits
9. Coordonnées (privacy@esg-mefali.com)
10. Date de mise à jour

### Étape 13 : Page /mes-donnees

```
Naviguer vers http://localhost:3000/mes-donnees (authentifié)
→ Tableau de bord avec 4 cartes (Inventaire, Export, Consentements, Suppression)
→ Cliquer sur Inventaire → tableau des compteurs
→ Cliquer sur Consentements → 7 toggles
→ Cliquer sur Supprimer → modale triple confirmation
→ Cliquer sur Exporter → download du ZIP
```

## Tests automatisés

```bash
# Backend (depuis backend/ avec venv activé)
pytest tests/ -v -k "f05 or consent or me_data or me_account or me_consents or purge or require_consent"

# Backend coverage
pytest tests/ -v --cov=app.modules.me --cov=app.core.consent --cov=app.core.url_signer --cov=app.core.mailer --cov-report=term-missing

# Frontend unit (depuis frontend/)
npm run test -- --run --coverage tests/unit/ConsentToggle.spec.ts tests/unit/DeletionConfirmModal.spec.ts tests/unit/DataInventoryTable.spec.ts tests/unit/useDataPrivacy.spec.ts

# E2E
npm run dev   # backend + frontend doivent tourner
npx playwright test tests/e2e/F05-rgpd-mes-donnees-consents.spec.ts --reporter=html
```

## Test CI security `require_consent` coverage

```bash
cd backend && source venv/bin/activate
pytest tests/security/test_require_consent_coverage.py -v
```

→ Doit passer en l'état (la liste d'exclusions documente les fonctions actuellement sans `require_consent`). Ajouter de nouveaux services `analyze_*` sans appel `require_consent` → le test échoue.

## Checklist Phase B avant `gh pr create`

- [ ] Tous les tests backend verts (pytest)
- [ ] Couverture backend ≥ 80 % sur `app/modules/me/` + `app/core/consent.py` + `app/core/url_signer.py` + `app/core/mailer.py`
- [ ] Tous les tests frontend verts (vitest)
- [ ] Couverture frontend ≥ 80 % sur les composants F05
- [ ] Migration Alembic up → down → up valide (`alembic upgrade head && alembic downgrade -1 && alembic upgrade head`)
- [ ] Test E2E Playwright vert (4 scénarios)
- [ ] Test CI security `test_require_consent_coverage.py` vert
- [ ] Pas de secret hardcodé : `grep -rE '(api_key|secret|password|token|signing_key)\s*=\s*["\047][A-Za-z0-9]' backend/ frontend/` ne renvoie que les fixtures de test.
- [ ] Dark mode validé sur les nouveaux composants Vue (visual diff)
- [ ] Documentation `docs/rgpd-conformite.md` + `docs/hosting-and-data-residency.md` rédigées et complètes
- [ ] Lien footer `/legal/privacy` présent sur toutes les pages
- [ ] Checkbox privacy à `/register` bloque la soumission frontend ET backend
- [ ] CLAUDE.md mis à jour via `update-agent-context.sh claude`

## Troubleshooting

### Migration échoue sur `down_revision`

Le numéro pressenti est `027` mais peut être ajusté en Phase B selon l'ordre de merge effectif. Vérifier avant de finaliser :

```bash
ls backend/alembic/versions/ | sort
alembic heads  # doit montrer une seule head
```

Si une autre feature a mergé entre-temps, ajuster `down_revision` dans le fichier `0XX_consents_and_account_deletion.py`.

### Test E2E « purge J+30 » échoue

Le test simule J+30 en avançant `deletion_scheduled_at`. Vérifier que :
1. Le user de test a bien le rôle `owner`.
2. La fixture restaure la date après le test (sinon le compte reste programmé pour purge).
3. Le cron est appelé via `subprocess.run(['python', 'scripts/purge_scheduled_deletions.py'])` et son exit code == 0.

### Stub mailer ne logge pas dans audit_log

Vérifier que `SMTP_HOST` n'est PAS configuré dans `.env` lors des tests. Si SMTP est configuré, le mailer essaiera l'envoi réel et peut échouer.

### `require_consent` retourne 401 au lieu de 403

Le 401 indique un problème de JWT (pas authentifié). 403 = authentifié mais consent manquant. Vérifier que le test envoie bien le bon token.
