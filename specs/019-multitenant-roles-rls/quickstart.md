# Quickstart — F02 Multi-tenant + Roles + RLS

Guide pas-à-pas pour valider la livraison F02 manuellement. Pour les tests automatisés, voir `tasks.md` et les fichiers de test dans `backend/tests/` et `frontend/tests/`.

---

## Prérequis

- Docker Compose en local (`docker compose up postgres -d`)
- Backend Python venv activé (`source backend/venv/bin/activate`)
- Frontend installé (`cd frontend && npm install`)
- Variables d'env `.env` configurées (au minimum `DATABASE_URL`, `SECRET_KEY`, `OPENROUTER_API_KEY`)

---

## 1. Migration de la base

```bash
cd backend
source venv/bin/activate
alembic upgrade head
```

Vérifier que la migration `019_multitenant_and_roles.py` est appliquée :

```bash
alembic current
# Doit afficher 019_multitenant_and_roles ou équivalent
```

Vérifier la présence des nouvelles tables :

```bash
docker compose exec postgres psql -U postgres -d esg_mefali -c "\dt" | grep -E "(accounts|refresh_tokens|account_invitations)"
```

Vérifier que RLS est activée sur les tables métier :

```bash
docker compose exec postgres psql -U postgres -d esg_mefali -c \
  "SELECT relname, relrowsecurity, relforcerowsecurity
   FROM pg_class
   WHERE relname IN ('company_profiles', 'documents', 'esg_assessments', 'conversations')"
```

Toutes doivent retourner `t` / `t` (rowsecurity et force_rowsecurity activés).

---

## 2. Seed d'un utilisateur Admin

Un Admin ne peut PAS être créé via l'API publique. Utiliser le script de seed :

```bash
cd backend
source venv/bin/activate
python -m app.scripts.seed_admin --email admin@mefali.org --password ChangeMe123 --full-name "Admin Mefali"
```

Ou en SQL direct :

```sql
INSERT INTO users (id, email, hashed_password, full_name, company_name, is_active, role, account_id)
VALUES (gen_random_uuid(), 'admin@mefali.org', '<bcrypt-hash>', 'Admin Mefali', '', true, 'ADMIN', NULL);
```

---

## 3. Démarrer les services

```bash
# Backend
cd backend && source venv/bin/activate && uvicorn app.main:app --port 8000 &

# Frontend
cd frontend && npm run dev &
```

Attendre que les serveurs répondent :
- Backend : http://localhost:8000/docs (Swagger UI accessible)
- Frontend : http://localhost:3000

---

## 4. Test manuel — Isolation entre PME (US1)

### a. Créer 2 PME

```bash
# PME A
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@pmea.com","password":"PassA12345","full_name":"Alice","company_name":"PME A","country":"SN"}'

# PME B
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"bob@pmeb.com","password":"PassB12345","full_name":"Bob","company_name":"PME B","country":"CI"}'
```

### b. Créer des données distinctes pour chaque PME (via le chat ou directement via API)

Connecter chacune et créer une conversation :

```bash
# Login Alice
TOKEN_A=$(curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" \
  -d '{"email":"alice@pmea.com","password":"PassA12345"}' | jq -r .access_token)

# Login Bob
TOKEN_B=$(curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" \
  -d '{"email":"bob@pmeb.com","password":"PassB12345"}' | jq -r .access_token)

# Créer une conversation chacun
curl -X POST http://localhost:8000/api/chat/conversations -H "Authorization: Bearer $TOKEN_A" -d '{"title":"Conv Alice"}'
curl -X POST http://localhost:8000/api/chat/conversations -H "Authorization: Bearer $TOKEN_B" -d '{"title":"Conv Bob"}'
```

### c. Vérifier l'isolation

```bash
# Alice doit voir uniquement sa conversation
curl -H "Authorization: Bearer $TOKEN_A" http://localhost:8000/api/chat/conversations | jq

# Bob doit voir uniquement sa conversation
curl -H "Authorization: Bearer $TOKEN_B" http://localhost:8000/api/chat/conversations | jq
```

**Résultat attendu** : Alice ne voit pas la conversation de Bob et inversement.

### d. Test fail-closed via SQL direct

Sans variable de session :

```bash
docker compose exec postgres psql -U postgres -d esg_mefali -c "SELECT count(*) FROM conversations"
```

Avec variable de session simulant Alice :

```bash
docker compose exec postgres psql -U postgres -d esg_mefali -c \
  "SET LOCAL app.current_account_id = '<alice_account_id>';
   SET LOCAL app.current_role = 'PME';
   SELECT count(*) FROM conversations"
```

**Résultat attendu** : sans variable de session SET, le count est 0 (RLS fail-closed). Avec la variable, le count correspond aux conversations d'Alice uniquement.

---

## 5. Test manuel — Accès Admin (US2)

### a. Login Admin

```bash
TOKEN_ADMIN=$(curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" \
  -d '{"email":"admin@mefali.org","password":"ChangeMe123"}' | jq -r .access_token)
```

### b. Accès `/api/admin/health`

```bash
# Admin → 200
curl -H "Authorization: Bearer $TOKEN_ADMIN" http://localhost:8000/api/admin/health
# Résultat attendu : {"status":"ok","role":"ADMIN","service":"admin"}

# PME → 403
curl -H "Authorization: Bearer $TOKEN_A" http://localhost:8000/api/admin/health
# Résultat attendu : {"detail":"Accès réservé aux administrateurs"}
```

### c. Frontend — `/admin/health`

- Login en tant qu'Admin sur `http://localhost:3000/login`
- Naviguer vers `http://localhost:3000/admin/health`
- **Résultat attendu** : page chargée avec layout admin (sidebar rouge, badge « Mode Admin »)

- Login en tant que PME (Alice)
- Naviguer vers `http://localhost:3000/admin/health`
- **Résultat attendu** : redirection vers `/dashboard` (middleware admin)

### d. Suppression de la whitelist email

```bash
# Tentative de création d'un fonds par Alice (PME) → 403
curl -X POST http://localhost:8000/api/financing/funds \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Fund","fund_type":"public",...}'
# Résultat attendu : 403 Forbidden

# Vérifier que la whitelist a été supprimée du code
grep -r "admin@esg-mefali.com\|admin@mefali.org" backend/app/modules/
# Résultat attendu : aucune occurrence
```

---

## 6. Test manuel — Invitation d'équipe (US3)

### a. Alice invite Carole

```bash
INVITE=$(curl -X POST http://localhost:8000/api/account/invite \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"email":"carole@pmea.com"}')
echo $INVITE | jq
```

### b. Récupérer le token d'invitation depuis les logs

L'`EmailDeliveryService` est `LoggingEmailDelivery` en F02 : le contenu est loggé en INFO. Récupérer le token depuis les logs :

```bash
# Les logs uvicorn contiennent une ligne :
# [EMAIL DELIVERY STUB] to=carole@pmea.com subject=... body=... https://localhost:3000/register?invite=<TOKEN>
TOKEN_INVITE=$(grep "EMAIL DELIVERY STUB" backend.log | tail -1 | grep -oE 'invite=[a-zA-Z0-9_-]+' | cut -d= -f2)
```

### c. Carole accepte via `/register`

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"carole@pmea.com\",\"password\":\"PassCarole12345\",\"full_name\":\"Carole\",\"company_name\":\"\",\"invite_token\":\"$TOKEN_INVITE\"}"
```

### d. Vérifier l'accès partagé

```bash
TOKEN_C=$(curl -X POST http://localhost:8000/auth/login -d '{"email":"carole@pmea.com","password":"PassCarole12345"}' | jq -r .access_token)

# Carole doit voir la conversation d'Alice (même Account)
curl -H "Authorization: Bearer $TOKEN_C" http://localhost:8000/api/chat/conversations | jq
# Résultat attendu : la conversation d'Alice apparaît
```

### e. Lister les membres et invitations

```bash
curl -H "Authorization: Bearer $TOKEN_A" http://localhost:8000/api/account/users | jq
# Résultat attendu : 2 membres (Alice, Carole), 0 invitation pending
```

### f. Retirer Carole

```bash
curl -X DELETE -H "Authorization: Bearer $TOKEN_A" http://localhost:8000/api/account/users/<carole_id>
# Résultat attendu : 204
# Tentative de Carole de se reconnecter → access_token toujours valide (24h) mais sa session future est invalidée
```

---

## 7. Test manuel — Refresh token rotation (US4)

### a. Login et capturer RT1

```bash
LOGIN=$(curl -X POST http://localhost:8000/auth/login -d '{"email":"alice@pmea.com","password":"PassA12345"}')
RT1=$(echo $LOGIN | jq -r .refresh_token)
```

### b. Refresh → RT2

```bash
REFRESH1=$(curl -X POST http://localhost:8000/auth/refresh -d "{\"refresh_token\":\"$RT1\"}")
RT2=$(echo $REFRESH1 | jq -r .refresh_token)

# Vérifier que RT1 != RT2
[ "$RT1" != "$RT2" ] && echo "OK : rotation effective"
```

### c. Replay RT1 immédiatement → fenêtre de grâce 5 s

```bash
sleep 1
REFRESH2=$(curl -X POST http://localhost:8000/auth/refresh -d "{\"refresh_token\":\"$RT1\"}")
echo $REFRESH2
# Résultat attendu : 200 avec le même RT2 retourné (pas un nouveau)
# Logs : événement "grace_window_reuse"
```

### d. Replay RT1 après 6 s → 401

```bash
sleep 6
REFRESH3=$(curl -X POST http://localhost:8000/auth/refresh -d "{\"refresh_token\":\"$RT1\"}")
echo $REFRESH3
# Résultat attendu : {"detail":"Refresh token déjà utilisé"}
# Logs : événement "refresh_token_replay"
```

### e. Logout → tous les RT révoqués

```bash
curl -X POST -H "Authorization: Bearer <access_token>" http://localhost:8000/auth/logout
# Résultat attendu : 204

# Tentative refresh avec RT2 → 401
curl -X POST http://localhost:8000/auth/refresh -d "{\"refresh_token\":\"$RT2\"}"
# Résultat attendu : 401
```

### f. Vérifier durée access token

```bash
LOGIN=$(curl -X POST http://localhost:8000/auth/login -d '{"email":"alice@pmea.com","password":"PassA12345"}')
ACCESS=$(echo $LOGIN | jq -r .access_token)

# Décoder le JWT (pas signé, juste pour lire la payload)
echo $ACCESS | cut -d. -f2 | base64 -d 2>/dev/null | jq
# Vérifier que (exp - iat) == 86400 secondes (24h)
```

---

## 8. Smoke tests automatisés

Backend :

```bash
cd backend && source venv/bin/activate
pytest tests/integration/test_rls_isolation.py -v
pytest tests/integration/test_admin_route_protection.py -v
pytest tests/integration/test_refresh_token_rotation.py -v
pytest tests/integration/test_account_invitation_flow.py -v
```

Frontend :

```bash
cd frontend
npm run test -- --coverage
npx playwright test tests/e2e/F02-multitenant-roles-rls.spec.ts
```

---

## Troubleshooting

| Problème | Cause probable | Résolution |
|---|---|---|
| Toutes les requêtes retournent 0 ligne | RLS active mais variables de session non SET | Vérifier que `get_current_user` appelle `set_rls_context` AVANT toute query métier |
| Migration échoue sur backfill | `users.company_name` NULL pour certains users | Appliquer la stratégie `Account` `default` (FR-006) |
| Refresh token replay accepté en boucle | Fenêtre de grâce mal implémentée (toujours acceptée) | Vérifier la condition `now() - revoked_at <= 5s` |
| Admin ne voit pas sa propre ligne `users` | RLS sur `users` n'inclut pas `app.current_user_id` | Ajouter cette clause dans la policy `pme_access_own_account_users` |
| Whitelist toujours présente | Suppression incomplète | Re-grep `admin@esg-mefali.com` et corriger |
