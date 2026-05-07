# Quickstart — F09 Back-Office Admin

**Date** : 2026-05-07

## Pour les Admins (utilisation)

### 1. Saisir une nouvelle Source officielle (workflow 4-yeux)

**Étape 1 — Admin A : saisie initiale**

1. Connectez-vous à `/admin` avec votre compte admin.
2. Naviguez vers **Sources** dans la sidebar.
3. Cliquez **"Nouvelle source"**.
4. Remplissez le formulaire :
   - **URL** : lien direct vers le document officiel (ex `https://www.greenclimate.fund/documents/...`)
   - **Title** : titre exact du document
   - **Publisher** : ex "Green Climate Fund", "ADEME", "BCEAO"
   - **Version** : version du document (ex "v3.2", "2024 edition")
   - **Date de publication** : date inscrite sur le document
   - **Page** : page du PDF (si applicable)
   - **Section** : section pertinente du document (si applicable)
5. Cliquez **"Enregistrer"**. La source est créée en `pending`.

> ⚠ **IMPORTANT** : vous ne pouvez **PAS** valider votre propre source. Un autre admin doit le faire (workflow 4-yeux).

**Étape 2 — Admin B : validation**

1. Connectez-vous avec un compte admin **différent** de celui qui a saisi la source.
2. Naviguez vers **Sources** → onglet **Pending**.
3. Cliquez sur la source à valider.
4. **Vérifiez** que le document est bien accessible via le bouton "Ouvrir le document officiel".
5. **Lisez** le contenu pour confirmer que les méta-données (title, publisher, page) sont exactes.
6. Cliquez **"Marquer comme vérifiée"**. La source passe en `verified` et devient utilisable par le LLM.

### 2. Créer un nouveau Fonds (workflow draft → published)

1. Naviguez vers **Catalogue → Funds** dans la sidebar.
2. Cliquez **"Nouveau fonds"**.
3. Remplissez :
   - Identité : name, fund_type (GCF, BAD, BOAD, etc.), theme, description
   - Montants : min/max amounts en EUR ou USD (avec versioning F04)
   - Critères : sectors éligibles, country eligibility
   - Sources liées : utilisez `<SourcePicker>` pour sélectionner 1+ source **verified** dans le catalogue.
4. Cliquez **"Enregistrer"**. Le fonds est en `draft`.
5. Pour publier :
   - Cliquez **"Publier"**.
   - Si toutes les sources liées sont `verified` → **publication réussie**, le fonds devient visible côté PME.
   - Si une source est `pending` ou `outdated` → **erreur 400** avec liste des sources bloquantes. Faites valider les sources par un autre admin (cf. Étape 1) avant de re-publier.

### 3. Gérer un incident PME (consultation + reset password + révocation)

**Cas : un PME a oublié son mot de passe et n'a pas accès à son email**

1. Naviguez vers **Comptes → Companies**.
2. Recherchez le compte par email ou nom d'entreprise.
3. Cliquez sur le compte. La page affiche **profil + projets + scores + attestations + audit_log** en lecture seule.
   > ⚠ Cette consultation est tracée dans l'audit_log F03 et **visible côté PME** (badge "Consulté par administrateur" sur leur page audit).
4. Pour reset le password :
   - Cliquez **"Reset password"**.
   - Confirmez l'action.
   - Un token est généré et envoyé par email au PME (en dev : log dans la console).
   - Le PME clique sur le lien (valide 1h), définit un nouveau mot de passe, peut se reconnecter.

**Cas : fraude détectée sur un compte**

1. Naviguez vers le compte.
2. Cliquez **"Désactiver le compte"**.
3. Indiquez la raison (obligatoire, ex "fraude détectée").
4. Le compte est désactivé. Ses prochaines requêtes API renvoient 403.

**Cas : attestation émise par erreur**

1. Naviguez vers **Attestations**.
2. Recherchez l'attestation à révoquer.
3. Cliquez **"Révoquer"**.
4. Indiquez la raison (≥ 10 caractères, ex "Données client incorrectes").
5. L'attestation est marquée révoquée. La signature ed25519 reste valide cryptographiquement, mais l'endpoint public de vérification renvoie `{valid: false, revoked: true, reason}`.

### 4. Interpréter les Métriques admin

1. Naviguez vers **Métriques** dans la sidebar.
2. Le dashboard affiche 5 cartes :
   - **Sources** : total / pending / verified / outdated avec trend 30j. Si pending > 10 → action requise (relancer les admins pour validation).
   - **Comptes** : total active / inactive / new 30j. Indicateur de croissance.
   - **Candidatures** (post-MVP) : placeholder pour l'instant.
   - **Attestations** : émises / révoquées / actives. Si revoked >> émises → revoir les processus de qualité.
   - **Coûts LLM** (post-MVP) : placeholder pour l'instant.

### 5. Gérer une suppression destructive (impact analysis)

**Cas : supprimer une Source devenue obsolète**

1. Naviguez vers la source.
2. Cliquez **"Supprimer"**.
3. Le `<ImpactAnalysisModal>` s'affiche listant **toutes les entités dépendantes** (indicators, criteria, formulas, emission_factors, simulation_factors, skills).
4. Si dépendants existent :
   - **Annuler** : revenir en arrière, ne rien faire.
   - **Forcer la suppression** : cascade soft delete (`valid_to=today()`) sur tous les dépendants. Action irréversible.
5. Si aucun dépendant : suppression directe en soft delete.

> ⚠ Pour modifier l'URL d'une source (ex après mise à jour du document officiel), préférez **éditer** la source plutôt que supprimer/recréer (les FK sont conservées).

## Pour les Devs (intégration)

### 1. Appliquer la migration 035 sur DB existante

```bash
cd backend
source venv/bin/activate
alembic upgrade head
```

> ⚠ Après migration, **toutes les entités catalogue existantes deviennent draft** (default `'draft'`). Le frontend PME ne voit plus rien jusqu'à ce que :
> 1. Vous validez les sources existantes (4-yeux).
> 2. Vous exécutez le script de rollout pour passer les entités catalogue déjà fiables en `published`.

```bash
python scripts/seed_publish_existing_catalog.py --dry-run  # voir ce qui serait publié
python scripts/seed_publish_existing_catalog.py --confirm   # exécuter
```

### 2. Ajouter un nouveau sous-router admin

```python
# backend/app/modules/admin/my_new_router.py
from fastapi import APIRouter, Depends
from app.modules.auth.dependencies import get_current_admin

router = APIRouter()

@router.get("/")
async def list_things(admin=Depends(get_current_admin)):
    return {"data": [], "meta": {}}

# backend/app/modules/admin/router.py
from .my_new_router import router as my_new_router
admin_router.include_router(my_new_router, prefix="/my-new", tags=["admin-my-new"])
```

### 3. Tester le workflow 4-yeux trigger

```python
# backend/tests/integration/triggers/test_trigger_4_eyes_source.py
@pytest.mark.requires_postgres
async def test_4_eyes_violation(db, admin_a, admin_b):
    source = Source(captured_by_user_id=admin_a.id, verification_status="pending", ...)
    db.add(source); await db.commit()

    # Admin A tente verify sa propre source → IntegrityError
    with pytest.raises(IntegrityError) as exc:
        source.verification_status = "verified"
        source.verified_by_user_id = admin_a.id
        await db.commit()
    assert "4-eyes principle violated" in str(exc.value.orig)
```

### 4. Tester l'isolation user PME

```python
# backend/tests/e2e/test_admin_isolation_pme.py
@pytest.mark.e2e
async def test_pme_cannot_access_admin(client, pme_user_token):
    response = await client.get(
        "/api/admin/funds",
        headers={"Authorization": f"Bearer {pme_user_token}"}
    )
    assert response.status_code == 403
```

### 5. Configurer EmailService en dev

```bash
export EMAIL_BACKEND=console  # log dans stdout
# OU
export EMAIL_BACKEND=noop  # pour les tests E2E sans capture
```

En dev, `POST /api/admin/users/{id}/reset-password` log le lien complet dans la console :
```
[EMAIL DEV] To: pme@example.com
Reset link: https://app.esg-mefali.com/auth/reset?token=abc123...
```

Copiez le token et utilisez-le pour tester `/auth/reset` côté frontend.

## Dépannage

### Migration 035 échoue avec "trigger already exists"
La migration utilise `DROP TRIGGER IF EXISTS` puis `CREATE TRIGGER`. Si l'erreur persiste, la table parent n'existe peut-être pas. Vérifiez que F01-F23 sont bien mergés.

### Trigger 4-yeux ne s'active pas
Vérifiez que vous utilisez **PostgreSQL** (pas SQLite). Les triggers PL/pgSQL ne sont pas portables.

### `<EntityCRUDTable>` ne charge pas les données
Vérifiez que le composable `useAdminCatalog<T>(entityType)` est correctement instancié et que la prop `dataLoader` est connectée à `store.list()`.

### Test conformity `admin_emails` échoue
Quelqu'un a réintroduit la whitelist email. Cherchez :
```bash
grep -r "admin_emails" backend/app/
```
Et migrez vers `Depends(get_current_admin)` (F02).

### Performance metrics > 500ms
Vérifiez que les indexes existent :
```sql
\d sources       -- doit avoir verification_status index
\d users         -- doit avoir is_active index
\d attestations  -- doit avoir revoked_at index
```

## Monitoring (post-MVP)

- Audit log volume : surveiller la croissance de `audit_log` (estimation 100k entries/mois en prod).
- Alertes : pattern admin consulte 100+ PME/h → investigation.
- Métriques Prometheus : exposer counts admin actions sur `/metrics`.
