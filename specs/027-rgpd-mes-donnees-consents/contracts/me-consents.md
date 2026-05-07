# Contract: `/api/me/consents/*` — Consentements granulaires

Date : 2026-05-07
Branche : `feat/F05-rgpd-mes-donnees-consents`

## `GET /api/me/consents`

### Description

Retourne la liste des 7 consentements pour le compte courant. Si un consentement n'a jamais été ni accordé ni révoqué, il apparaît avec `granted=false` et `granted_at=null` (état par défaut documenté).

### Auth

JWT requis.

### Request

Pas de query, pas de body.

### Response 200

```json
[
  {
    "type": "profile_analysis",
    "granted": true,
    "granted_at": "2026-04-01T12:00:00Z",
    "revoked_at": null,
    "legal_basis": "contract",
    "version": "v1.0",
    "label": "Analyse de mon profil entreprise pour matching financements",
    "description": "Permet à la plateforme d'analyser votre profil pour vous proposer des fonds adaptés."
  },
  {
    "type": "document_analysis_ai",
    "granted": true,
    "granted_at": "2026-04-01T12:00:00Z",
    "revoked_at": null,
    "legal_basis": "contract",
    "version": "v1.0",
    "label": "Analyse IA des documents que je téléverse",
    "description": "Permet à l'IA d'extraire automatiquement les informations ESG de vos documents."
  },
  {
    "type": "mobile_money_analysis",
    "granted": false,
    "granted_at": null,
    "revoked_at": null,
    "legal_basis": "consent",
    "version": "v1.0",
    "label": "Analyse de mes flux Mobile Money pour scoring crédit",
    "description": "Permet d'inclure vos données Mobile Money dans le calcul de votre score crédit alternatif."
  },
  {
    "type": "photos_ia_analysis",
    "granted": false,
    "granted_at": null,
    "revoked_at": null,
    "legal_basis": "consent",
    "version": "v1.0",
    "label": "Analyse IA de mes photos d'exploitation",
    "description": "Permet à l'IA d'analyser des photos de votre activité pour enrichir le scoring."
  },
  {
    "type": "public_data_analysis",
    "granted": false,
    "granted_at": null,
    "revoked_at": null,
    "legal_basis": "consent",
    "version": "v1.0",
    "label": "Analyse de données publiques me concernant",
    "description": "Permet d'inclure des données publiques (réseaux sociaux, avis) dans l'analyse."
  },
  {
    "type": "credit_certificate_generation",
    "granted": true,
    "granted_at": "2026-04-01T12:00:00Z",
    "revoked_at": null,
    "legal_basis": "contract",
    "version": "v1.0",
    "label": "Génération automatique d'attestation crédit transmissible",
    "description": "Autorise la génération de votre attestation crédit signée Ed25519 pour transmission aux financeurs."
  },
  {
    "type": "product_communications",
    "granted": false,
    "granted_at": null,
    "revoked_at": null,
    "legal_basis": "consent",
    "version": "v1.0",
    "label": "Communications produit et newsletter",
    "description": "Recevoir des informations sur les nouveautés ESG Mefali (au plus 1 email/mois)."
  }
]
```

### Performance

- 1 requête SQL avec `LEFT JOIN` ou plusieurs requêtes parallélisées via `asyncio.gather`.
- p95 < 200 ms.

---

## `POST /api/me/consents/{type}/grant`

### Description

Accorde un consentement. Si un consentement actif existe déjà, no-op (idempotent). Sinon insère une nouvelle ligne `consents` avec `granted=true, granted_at=now(), revoked_at=NULL`.

### Auth

JWT requis.

### Path params

- `type` : un des 7 `consent_type` valides. Si invalide → 422.

### Request

Body vide (les métadonnées ip/user_agent sont dérivées du request).

### Response 200

```json
{
  "type": "mobile_money_analysis",
  "granted": true,
  "granted_at": "2026-05-07T10:30:00Z",
  "version": "v1.0"
}
```

### Audit log

```json
{
  "entity_type": "consent",
  "entity_id": "{consent_uuid}",
  "action": "consent_granted",
  "metadata": {
    "consent_type": "mobile_money_analysis",
    "version": "v1.0",
    "ip": "...",
    "user_agent": "..."
  }
}
```

### Response 422 — type invalide

```json
{ "detail": "Type de consentement invalide", "valid_types": [...] }
```

---

## `POST /api/me/consents/{type}/revoke`

### Description

Révoque un consentement actif. Si aucun consentement actif n'existe, retourne 200 idempotent (no-op explicit).

### Auth

JWT requis.

### Path params

- `type` : un des 7 `consent_type` valides.

### Request

Body vide.

### Response 200

```json
{
  "type": "mobile_money_analysis",
  "granted": false,
  "revoked_at": "2026-05-07T10:35:00Z"
}
```

### Audit log

```json
{
  "entity_type": "consent",
  "entity_id": "{consent_uuid}",
  "action": "consent_revoked",
  "metadata": {
    "consent_type": "mobile_money_analysis",
    "previously_granted_at": "2026-05-07T10:30:00Z",
    "ip": "...",
    "user_agent": "..."
  }
}
```

### Response 422 — type invalide

```json
{ "detail": "Type de consentement invalide", "valid_types": [...] }
```

---

## Helper backend `require_consent` — contrat

### Signature

```python
async def require_consent(
    db: AsyncSession,
    account_id: UUID,
    consent_type: str,
) -> None:
    """
    Lève HTTPException(403, ...) si aucun consentement actif n'existe pour le couple
    (account_id, consent_type). Retourne sans erreur sinon.
    """
```

### Comportement attendu

- **Lookup** : SELECT 1 row sur `consents` où `account_id` matche, `consent_type` matche, `revoked_at IS NULL`, `granted=true`.
- **Si trouvé** : retour None.
- **Si non trouvé** : raise `HTTPException(403, detail={"detail": "Consentement {label} requis", "consent_type": consent_type, "settings_url": "/mes-donnees/consentements"})`.

### Forme `Depends`

```python
def consent_dependency(consent_type: str) -> Callable:
    async def _dep(
        db: AsyncSession = Depends(get_db),
        user = Depends(get_current_user),
    ):
        await require_consent(db, user.account_id, consent_type)
    return _dep
```

Usage dans un router :

```python
@router.post(
    "/credit/mobile-money/preview",
    dependencies=[Depends(consent_dependency("mobile_money_analysis"))],
)
async def preview_mobile_money(...):
    ...
```

---

## Tests de contrat

### Backend (pytest)

1. `test_list_consents_returns_7_default_states_for_new_account` : nouveau account, `GET /api/me/consents`, vérifie 7 entrées avec valeurs default documentées.
2. `test_grant_consent_creates_active_row` : `POST /api/me/consents/mobile_money_analysis/grant`, vérifie row inséré avec `granted=true, revoked_at=NULL`.
3. `test_grant_consent_idempotent_when_already_granted` : 2 calls successifs `grant`, vérifie qu'on n'insère pas de doublon (1 seule row active).
4. `test_revoke_consent_marks_revoked_at` : `grant` puis `revoke`, vérifie `revoked_at` est positionné.
5. `test_revoke_idempotent_when_no_active_consent` : `revoke` sur un type jamais granted, vérifie 200 sans erreur.
6. `test_grant_audit_log_logged` : après grant, vérifie événement audit_log inséré.
7. `test_revoke_audit_log_logged` : après revoke, vérifie événement audit_log inséré.
8. `test_consent_metadata_captures_ip_and_user_agent` : appel avec headers, vérifie metadata du row inséré.
9. `test_consents_isolated_by_account_id` : 2 accounts, vérifie isolation stricte.
10. `test_consent_invalid_type_returns_422` : `POST /api/me/consents/invalid_type/grant`, vérifie 422.
11. `test_require_consent_raises_403_when_no_active_consent` : appel `require_consent(db, account_id, 'mobile_money_analysis')` sans grant préalable, vérifie HTTPException 403 avec `consent_type` en metadata.
12. `test_require_consent_raises_403_when_revoked` : grant puis revoke, vérifie 403.
13. `test_require_consent_passes_when_active` : grant, vérifie no-op.
14. `test_consent_dependency_blocks_endpoint` : endpoint stub avec `Depends(consent_dependency('mobile_money_analysis'))`, sans grant → 403, avec grant → 200.

### Frontend (Vitest)

1. `useConsentsStore` charge les 7 consents au mount de la page Consentements.
2. `<ConsentToggle>` émet `@toggle` avec le bon type lors du clic.
3. Après `toggle`, l'état du store est mis à jour optimistiquement.
4. Si l'API retourne erreur, le store rollback l'état.
