# Contract — F08 Attestations API REST (authentifiée)

**Spec** : [../spec.md](../spec.md)
**Plan** : [../plan.md](../plan.md)
**Date** : 2026-05-07

## Endpoints PME (authentification requise)

### POST /api/attestations

**Description** : génère une nouvelle attestation pour la PME courante.

**Request body** :
```json
{
  "attestation_type": "combined"
}
```

**Validation Pydantic** :
- `attestation_type` : enum `credit_score | esg_assessment | combined`

**Pré-conditions** :
- `attestation_type=credit_score` → un `CreditScore` doit exister pour le compte courant
- `attestation_type=esg_assessment` → au moins une `EsgAssessment` finalisée doit exister
- `attestation_type=combined` → les 2 ci-dessus

**Response 201 Created** :
```json
{
  "attestation_id": "abc-1234-def-5678",
  "display_id": "ATT-2026-00042",
  "verification_url": "https://esg-mefali.com/verify/abc-1234-def-5678",
  "pdf_path": "/uploads/attestations/pdfs/abc-1234-def-5678.pdf",
  "qr_code_path": "/uploads/attestations/qr/abc-1234-def-5678.png",
  "valid_from": "2026-05-07T10:30:00+00:00",
  "valid_until": "2027-05-07T10:30:00+00:00",
  "public_key_id": "v1",
  "pdf_hash_sha256": "a3b8c2d1...64chars"
}
```

**Erreurs** :
- 400 Bad Request : `{"error": "credit_score_missing", "message": "Aucun score crédit calculé. Veuillez d'abord finaliser le scoring crédit."}`
- 400 Bad Request : `{"error": "esg_assessment_missing", "message": "Aucune évaluation ESG finalisée. Veuillez d'abord finaliser une évaluation ESG."}`
- 401 Unauthorized : token JWT manquant ou expiré
- 500 Internal Server Error : `{"error": "pdf_generation_failed", "message": "Erreur lors de la génération du PDF. Veuillez réessayer."}` (transactional, pas de ligne créée)

**Effets de bord** :
- 1 ligne `attestations` insérée
- 1 fichier PDF dans `/uploads/attestations/pdfs/{id}.pdf`
- 1 fichier PNG dans `/uploads/attestations/qr/{id}.png`
- 1 entrée `audit_log` avec `action='create'`, `entity_type='attestations'`, `source_of_change='manual'`

---

### GET /api/attestations

**Description** : liste des attestations de la PME courante (RLS PostgreSQL filtre automatiquement).

**Query params** :
- `?status=authentic|revoked|expired|all` (défaut `all`)
- `?type=credit_score|esg_assessment|combined|all` (défaut `all`)
- `?limit=25&offset=0` (pagination)

**Response 200 OK** :
```json
{
  "items": [
    {
      "attestation_id": "abc-1234-def-5678",
      "display_id": "ATT-2026-00042",
      "attestation_type": "combined",
      "status": "authentic",
      "valid_from": "2026-05-07T10:30:00+00:00",
      "valid_until": "2027-05-07T10:30:00+00:00",
      "verification_url": "https://esg-mefali.com/verify/abc-1234-def-5678",
      "pdf_path": "/uploads/attestations/pdfs/abc-1234-def-5678.pdf",
      "revoked_at": null,
      "created_at": "2026-05-07T10:30:00+00:00"
    }
  ],
  "total": 3,
  "limit": 25,
  "offset": 0
}
```

**Notes** :
- `status` est calculé côté serveur (`authentic | revoked | expired`) à partir de `revoked_at` et `valid_until`.
- `pdf_path` est servi via un endpoint séparé `GET /api/attestations/{id}/download` (signed URL post-MVP, lien direct pour le MVP).

---

### POST /api/attestations/{id}/revoke

**Description** : révoque une attestation appartenant à la PME courante.

**URL params** :
- `id` : UUID de l'attestation

**Request body** :
```json
{
  "reason": "Mise à jour majeure du profil financier"
}
```

**Validation Pydantic** :
- `reason` : `min_length=10, max_length=500`

**Response 200 OK** :
```json
{
  "attestation_id": "abc-1234-def-5678",
  "revoked_at": "2026-08-15T14:00:00+00:00",
  "revoked_reason": "Mise à jour majeure du profil financier",
  "revoked_by_user_id": "user-uuid-pme",
  "verification_url": "https://esg-mefali.com/verify/abc-1234-def-5678"
}
```

**Erreurs** :
- 400 Bad Request : `{"error": "validation_error", "details": [{"loc": ["reason"], "msg": "La raison doit comporter au moins 10 caractères"}]}`
- 401 Unauthorized
- 404 Not Found : attestation introuvable (RLS : appartient à un autre tenant ou n'existe pas)
- 409 Conflict : `{"error": "already_revoked", "message": "Cette attestation est déjà révoquée"}`

**Effets de bord** :
- Mise à jour : `revoked_at = now()`, `revoked_reason`, `revoked_by_user_id = current_user.id`
- 1 entrée `audit_log` avec `action='revoke'`, `field='revoked_at'`, `actor_role='pme'`

---

### GET /api/attestations/{id}/download

**Description** : télécharge le PDF d'une attestation appartenant à la PME courante.

**URL params** :
- `id` : UUID de l'attestation

**Response 200 OK** :
- `Content-Type: application/pdf`
- `Content-Disposition: attachment; filename="ATT-2026-00042.pdf"`
- Body : binaire PDF

**Erreurs** :
- 401 Unauthorized
- 404 Not Found : attestation introuvable (RLS) ou fichier disque manquant

---

## Endpoints Admin (rôle Admin requis via `get_current_admin` F02)

### GET /api/admin/attestations

**Description** : liste de TOUTES les attestations cross-tenant (admin uniquement).

**Query params** :
- `?account_id=<uuid>` (filtre par tenant, optionnel)
- `?status=authentic|revoked|expired|all`
- `?type=credit_score|esg_assessment|combined|all`
- `?from=<ISO>&until=<ISO>` (filtre période)
- `?limit=50&offset=0`

**Response 200 OK** : identique à `GET /api/attestations` + colonnes complémentaires `account_id`, `user_id`.

**Erreurs** :
- 401 Unauthorized
- 403 Forbidden : utilisateur non admin

---

### POST /api/admin/attestations/{id}/revoke

**Description** : révoque toute attestation cross-tenant (admin uniquement).

**URL params** : `id` — UUID

**Request body** :
```json
{
  "reason": "Suspicion de fraude — investigation en cours"
}
```

**Response 200 OK** : identique à `POST /api/attestations/{id}/revoke`.

**Erreurs** :
- 401 Unauthorized
- 403 Forbidden : utilisateur non admin
- 404 Not Found : attestation inexistante (cross-tenant car admin contourne RLS)
- 409 Conflict : déjà révoquée

**Effets de bord** :
- Mise à jour : `revoked_by_user_id = admin.id`
- 1 entrée `audit_log` avec `actor_role='admin'`

---

## Codes HTTP standards

| Code | Sens | Cas |
|------|------|-----|
| 200 | OK | Lecture / mise à jour réussie |
| 201 | Created | Nouvelle attestation créée |
| 400 | Bad Request | Validation Pydantic échec |
| 401 | Unauthorized | Token manquant/expiré |
| 403 | Forbidden | Manque les droits admin |
| 404 | Not Found | Attestation introuvable (RLS ou inexistance) |
| 409 | Conflict | Attestation déjà révoquée |
| 429 | Too Many Requests | Rate limiting (page publique uniquement, pas sur ces endpoints authentifiés) |
| 500 | Internal Server Error | Erreur génération PDF / signature / I/O |

## Exemples cURL

```bash
# Authentification (préliminaire)
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"pme@test.com","password":"..."}' | jq -r .access_token)

# 1. Générer une attestation combined
curl -X POST http://localhost:8000/api/attestations \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"attestation_type":"combined"}'

# 2. Lister mes attestations
curl http://localhost:8000/api/attestations \
    -H "Authorization: Bearer $TOKEN"

# 3. Révoquer une attestation
curl -X POST http://localhost:8000/api/attestations/abc-1234-def-5678/revoke \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"reason":"Mise à jour majeure du profil financier"}'

# 4. Télécharger le PDF
curl http://localhost:8000/api/attestations/abc-1234-def-5678/download \
    -H "Authorization: Bearer $TOKEN" \
    -o attestation.pdf
```
