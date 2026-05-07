# Contract: `/api/me/account/*` — Suppression de compte

Date : 2026-05-07
Branche : `feat/F05-rgpd-mes-donnees-consents`

## `POST /api/me/account/verify-password`

### Description

Vérifie le mot de passe de l'utilisateur courant **sans** générer de nouveau token de session. Utilisé par le frontend pour valider l'étape 2 de la modale de suppression avant l'action critique.

### Auth

JWT requis (utilisateur courant).

### Request

```json
{
  "password": "current_user_password"
}
```

### Response 200

```json
{
  "verified": true
}
```

### Response 401

```json
{
  "detail": "Mot de passe incorrect"
}
```

### Audit log

À chaque appel échoué :

```json
{
  "entity_type": "user",
  "entity_id": "{user_id}",
  "action": "password_verification_failed",
  "metadata": {
    "ip": "...",
    "user_agent": "...",
    "context": "account_deletion_modal"
  }
}
```

À chaque appel réussi : pas de log spécifique (l'action déclenchante sera logguée séparément).

### Rate limiting

5 tentatives par compte / 5 minutes. Au-delà : 429 + audit log `password_verification_locked`.

---

## `POST /api/me/account/schedule-deletion`

### Description

Programme la suppression du compte à `now() + 30 days`. Vérifie le mot de passe **et** le `confirmation_text` côté backend (double validation indépendamment du verify-password précédent). Envoie un email de confirmation avec lien d'annulation.

### Auth

JWT requis. Doit être un user avec `role='owner'` sur l'account (pas un collaborator).

### Request

```json
{
  "password": "current_user_password",
  "confirmation_text": "SUPPRIMER"
}
```

Validation :
- `password` : non-vide, ≤ 200 chars.
- `confirmation_text` : exactement `"SUPPRIMER"` (case-sensitive). Toute autre valeur → 422.

### Response 200

```json
{
  "deletion_scheduled_at": "2026-06-06T10:00:00Z",
  "cancel_url": "https://app.../api/me/account/cancel-deletion?token=signed_xxx",
  "message": "Suppression programmée. Vous pouvez annuler jusqu'au 6 juin 2026."
}
```

### Side effects

1. `UPDATE accounts SET deletion_scheduled_at = now() + interval '30 days' WHERE id = :account_id`.
2. Insertion audit log `account_deletion_scheduled`.
3. Envoi email transactionnel à toutes les adresses des `users` du compte (via `app/core/mailer.py`) :
   - Sujet : « Confirmation de suppression de votre compte ESG Mefali »
   - Corps : explique le délai 30 jours, fournit le lien d'annulation signé 30j (le lien expire avec la purge de toute façon).
4. Insertion audit log `account_deletion_email_sent`.

### Response 401 — mot de passe incorrect

```json
{
  "detail": "Mot de passe incorrect"
}
```

Audit log `account_deletion_attempt_failed`.

### Response 403 — non-owner

```json
{
  "detail": "Seul le propriétaire du compte peut programmer sa suppression",
  "current_role": "collaborator"
}
```

### Response 409 — déjà programmée

```json
{
  "detail": "Une suppression est déjà programmée",
  "deletion_scheduled_at": "..."
}
```

### Response 422 — confirmation_text invalide

```json
{
  "detail": [
    {
      "loc": ["body", "confirmation_text"],
      "msg": "Doit être exactement 'SUPPRIMER'"
    }
  ]
}
```

---

## `POST /api/me/account/cancel-deletion`

### Description

Annule une suppression programmée. Deux modes d'authentification :
1. **Authentifié** : appel JWT. Vérifie que `user.account_id == account_id` et `user.role == 'owner'`.
2. **Token signé** (lien email) : query param `?token=signed_xxx`, pas de JWT requis. Le token signe `{account_id, action='cancel_deletion'}` et expire à `deletion_scheduled_at`.

### Auth

JWT optionnel si `token` fourni en query.

### Request

Mode authentifié : body vide.

Mode token : `POST /api/me/account/cancel-deletion?token=xxx`, body vide.

### Response 200

```json
{
  "cancelled_at": "2026-05-15T14:30:00Z",
  "message": "Suppression annulée. Votre compte reste actif."
}
```

### Side effects

1. `UPDATE accounts SET deletion_scheduled_at = NULL WHERE id = :account_id`.
2. Audit log `account_deletion_cancelled`.
3. Envoi email de confirmation d'annulation aux users du compte.

### Response 401 — token invalide

```json
{ "detail": "Token invalide ou expiré" }
```

### Response 404 — pas de suppression programmée

```json
{ "detail": "Aucune suppression programmée pour ce compte" }
```

### Response 410 — déjà purgé

```json
{ "detail": "Compte déjà supprimé, annulation impossible" }
```

---

## Cron job `scripts/purge_scheduled_deletions.py`

### Description

Job batch quotidien (lancé manuellement en MVP, intégré au scheduler F19 plus tard). Sélectionne les comptes dont `deletion_scheduled_at < now() AND deleted_at IS NULL`, puis pour chacun exécute la cascade de purge.

### Pseudocode

```python
async def main():
    async for account in fetch_accounts_to_purge():
        try:
            await purge_account_data(account.id)
            logger.info(f"Purged account {account.id}")
        except Exception as e:
            logger.error(f"Failed to purge {account.id}: {e}")
            # Le flag purge_in_progress reste à true ; reprise au prochain run
            continue


async def purge_account_data(account_id: UUID) -> PurgeResult:
    # 1. Lock idempotent : flag purge_in_progress=true (UPDATE conditional)
    locked = await db.execute(
        update(Account)
        .where(Account.id == account_id)
        .where(or_(Account.purge_in_progress.is_(False), Account.purge_in_progress.is_(None)))
        .values(purge_in_progress=True)
    )
    # Si déjà locked et toujours pas deleted_at → reprise

    # 2. Révoquer attestation crédit éventuelle
    await db.execute(
        update(Attestation)
        .where(Attestation.account_id == account_id, Attestation.status == 'active')
        .values(status='revoked', revoked_at=now(), revoked_reason='account_deleted')
    )

    # 3. Suppression cascade des données métier (FK ON DELETE CASCADE depuis accounts)
    # En pratique : DELETE FROM accounts WHERE id = X déclenche les cascades.
    # Mais on veut récupérer les paths fichiers avant : SELECT documents.path WHERE account_id = X.

    # 4. Lister les fichiers à supprimer
    document_paths = await fetch_document_paths(account_id)

    # 5. DELETE FROM accounts (déclenche cascade sur toutes les tables avec FK ON DELETE CASCADE)
    # SAUF : audit_log (FK ON DELETE SET NULL ou pas de FK)
    await db.execute(delete(Account).where(Account.id == account_id))

    # 6. Suppression des fichiers physiques
    for path in document_paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass  # idempotent
    shutil.rmtree(f"/uploads/{account_id}/", ignore_errors=True)

    # 7. Anonymisation audit_log : UPDATE en place
    pii_fields = {"email", "phone", "ip", "user_agent", "name", "address", ...}
    await db.execute(text(
        """
        UPDATE audit_log
        SET user_id = NULL,
            account_id = NULL,
            payload = jsonb_strip_pii(payload, :fields)
        WHERE account_id = :acc_id
        """
    ), {"acc_id": account_id, "fields": list(pii_fields)})

    # 8. Révocation refresh tokens
    await db.execute(
        delete(RefreshToken).where(RefreshToken.account_id == account_id)
    )

    # 9. Mise à deleted_at (ATTENTION : cascade a déjà supprimé l'account ; on doit insérer
    # une row "tombstone" minimal pour conserver l'historique, OU pas selon la stratégie.
    # Décision : on conserve la row accounts, on remet juste deleted_at.)
    # Donc on adapte : ne pas DELETE FROM accounts, mais UPDATE deleted_at.
    await db.execute(
        update(Account)
        .where(Account.id == account_id)
        .values(deleted_at=now(), purge_in_progress=False)
    )

    # 10. Email final
    await mailer.send_email(
        to=former_owner_email,  # capturé avant la cascade
        subject="Votre compte ESG Mefali a été supprimé",
        body_html="...",
    )

    # 11. Audit log final (SANS user_id ni account_id, conservé brut)
    await audit.log(
        entity_type="account",
        entity_id=str(account_id),
        action="account_purged",
        user_id=None,
        account_id=None,
        metadata={"purged_at": now().isoformat()}
    )
```

> **Note d'implémentation** : la décision sur DELETE vs UPDATE de la row `accounts` sera arbitrée en Phase B selon les contraintes de FK exact. La version actuelle privilégie UPDATE+`deleted_at` pour conserver l'historique d'existence du compte tout en libérant le PII (anonymisable séparément).

### Idempotence

- Si le job est interrompu après l'étape 5 mais avant l'étape 9 : le flag `purge_in_progress=true` reste, `deleted_at IS NULL`. La prochaine exécution voit cet état et reprend à partir de l'étape 6 (les étapes 5/6 sont elles-mêmes idempotentes : DELETE de rien = no-op, suppression fichier inexistant = no-op).
- Le job peut être lancé plusieurs fois par jour sans effet secondaire indésirable.

### Tests

#### Tests d'intégration (pytest)

1. `test_purge_cascades_all_account_data` : créer un account avec données complètes, déclencher purge, vérifier que toutes les tables `account_id` sont vides.
2. `test_purge_anonymizes_audit_log` : vérifier que post-purge, `audit_log.user_id IS NULL AND audit_log.account_id IS NULL` pour toutes les rows liées, et que `payload` ne contient plus de PII whitelistées.
3. `test_purge_removes_uploads_directory` : créer fichiers fictifs sous `/uploads/{account_id}/`, déclencher purge, vérifier suppression.
4. `test_purge_revokes_attestations_first` : créer une attestation active, déclencher purge, vérifier `status='revoked', reason='account_deleted'` AVANT la cascade.
5. `test_purge_revokes_refresh_tokens` : créer refresh tokens, purge, vérifier suppression.
6. `test_purge_idempotent_after_interruption` : démarrer purge, simuler exception après step 5, vérifier `purge_in_progress=true` ; relancer, vérifier complétion.
7. `test_purge_skips_if_already_deleted` : `deleted_at NOT NULL`, le cron ignore.
8. `test_purge_skips_if_scheduled_in_future` : `deletion_scheduled_at > now()`, le cron ignore.
9. `test_purge_sends_final_email` : vérifier envoi email post-purge.
10. `test_schedule_deletion_creates_audit_log` : programmer suppression, vérifier audit_log.
11. `test_cancel_deletion_via_token_signed` : générer token signé, appeler cancel-deletion sans JWT, vérifier annulation.
12. `test_cancel_deletion_token_expired_returns_401` : token > 30j, vérifier 401.

#### Tests E2E (Playwright)

Voir tasks.md → spec E2E `F05-rgpd-mes-donnees-consents.spec.ts`.

---

## Modifications de l'endpoint `POST /api/auth/register`

### Modification

Ajouter un champ obligatoire `privacy_policy_accepted: bool` dans le body. Si `false` ou absent, retour 422.

### Side effects post-creation

À la création réussie d'un compte (avant retour 201) :

1. Insertion audit log `privacy_policy_accepted` avec `metadata = {version: 'v1.0', ip, user_agent}`.
2. Création des 7 consents avec valeurs par défaut documentées (3 essentials granted=true, 4 optionnels granted=false / non créés selon stratégie). Décision Phase B : créer les 7 consents au registration ou créer à la première demande ? **Décision** : créer les 3 essentials avec `granted=true` au registration ; les 4 optionnels restent absents (l'absence = état non-accordé, comportement identique à `granted=false` pour `require_consent`).

### Tests

1. `test_register_without_privacy_policy_accepted_returns_422`.
2. `test_register_with_privacy_policy_accepted_creates_audit_log`.
3. `test_register_creates_3_essential_consents_with_granted_true`.
