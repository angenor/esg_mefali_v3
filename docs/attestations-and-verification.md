# Attestations vérifiables Ed25519 (F08)

## Vue d'ensemble

ESG Mefali émet des **attestations vérifiables** pour permettre aux PME de partager
leur score crédit / ESG avec un partenaire fonds vert sans nécessiter de compte
sur la plateforme. Chaque attestation est :

- Signée numériquement avec une clé privée **Ed25519** (clé courbe elliptique).
- Identifiée par un UUID v4 + un identifiant lisible `ATT-YYYY-NNNNN`.
- Contenue dans un PDF avec QR code embarqué pointant vers la page publique
  de vérification `/verify/{attestation_id}`.
- Vérifiable hors-ligne par tout acteur disposant de la clé publique.

## Architecture

```
PME (authentifiée)          API authentifiée                Service interne
    │                              │                             │
    │ POST /api/attestations       │                             │
    ├─────────────────────────────>│                             │
    │                              │ generate_attestation        │
    │                              ├────────────────────────────>│
    │                              │                             │ 1. load CreditScore + EsgAssessment
    │                              │                             │ 2. compute display_id
    │                              │                             │ 3. generate QR (segno)
    │                              │                             │ 4. build PDF (WeasyPrint + Jinja2)
    │                              │                             │ 5. compute SHA-256 du PDF
    │                              │                             │ 6. build canonical JSON payload
    │                              │                             │ 7. sign Ed25519 (cryptography)
    │                              │                             │ 8. persist row + audit log F03
    │                              │                             │
    │                              │ <───────────────────────────│
    │ <────── 201 attestation      │                             │
    │
    │ partage URL/PDF par email/messagerie hors-plateforme
    │ ▼
Fund officer (no auth)        API publique (no-auth)          Service interne
    │                              │                             │
    │ GET /api/public/verify/{id}  │                             │
    ├─────────────────────────────>│                             │
    │                              │ verify_attestation          │
    │                              ├────────────────────────────>│
    │                              │                             │ 1. parse UUID
    │                              │                             │ 2. load row (no RLS — public)
    │                              │                             │ 3. rebuild canonical JSON
    │                              │                             │ 4. verify Ed25519
    │                              │                             │ 5. apply priority revoked > expired > authentic
    │                              │ <───────────────────────────│
    │ <─── DTO discriminated union │
    │      par status              │
```

## Format canonique JSON

La signature Ed25519 s'applique sur un payload JSON **canonique** déterministe :

```json
{
  "attestation_id": "11111111-2222-3333-4444-555555555555",
  "pdf_hash_sha256": "a1b2c3...64chars",
  "referential_snapshot": [
    {"name": "ESG Mefali", "version": "1.2", "published_at": "2026-03-15"}
  ],
  "scores": {
    "combined": 73,
    "esg_global": 65,
    "green_impact": 78,
    "solvability": 68
  },
  "valid_from": "2026-05-07T10:30:00+00:00",
  "valid_until": "2027-05-07T10:30:00+00:00"
}
```

**Garanties** :

- Clés alphabétiquement triées (`sort_keys=True`).
- Pas d'espaces dans les séparateurs (`separators=(',', ':')`).
- Encodage UTF-8 strict (pas de BOM).
- Datetimes normalisés UTC ISO 8601 sans microsecondes.
- Floats absents (les scores sont des entiers).

Cette spécification est compatible RFC 8785 ("JSON Canonicalization Scheme").

## Algorithme de vérification offline

### Python

```python
import base64
import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

# Récupérer la clé publique via GET /api/public/attestation-public-key
public_key_pem = b"""-----BEGIN PUBLIC KEY-----
...
-----END PUBLIC KEY-----
"""
public_key = serialization.load_pem_public_key(public_key_pem)

# Récupérer l'attestation via GET /api/public/verify/{id}
attestation = {
    "attestation_id": "...",
    "scores": {...},
    "referential_snapshot": [...],
    "pdf_hash_sha256": "...",
    "valid_from": "...",
    "valid_until": "...",
}

# Sérialisation canonique identique au backend
canonical = json.dumps(attestation, sort_keys=True, separators=(",", ":"))
signature_b64 = "<récupérée du backend>"
signature_bytes = base64.b64decode(signature_b64)

try:
    public_key.verify(signature_bytes, canonical.encode("utf-8"))
    print("Signature valide ✓")
except InvalidSignature:
    print("Signature invalide ✗")
```

### Node.js

```js
const crypto = require('crypto')

function verifyAttestation(attestation, signatureB64, publicKeyPem) {
  const canonical = JSON.stringify(attestation, Object.keys(attestation).sort())
  const publicKey = crypto.createPublicKey(publicKeyPem)
  const signatureBytes = Buffer.from(signatureB64, 'base64')
  return crypto.verify(null, Buffer.from(canonical, 'utf-8'), publicKey, signatureBytes)
}
```

(Note : `JSON.stringify` JS n'est pas strictement canonique RFC 8785. Pour
production, utiliser `json-stable-stringify` ou similar.)

## Stockage de la clé privée

- **Variable d'environnement** : `ATTESTATION_PRIVATE_KEY_PEM` au format PEM PKCS8.
- En production : injectée par le secret manager d'infra (Docker secrets,
  Kubernetes Secrets, AWS ECS Task Definition).
- En développement : générée localement via
  `python backend/scripts/generate_attestation_keypair.py`.
- En tests : une paire éphémère est générée à la volée (`SigningKeyStore`).
- **Jamais commitée en git.**

## Procédure de rotation des clés

Pour le MVP, une seule clé `v1` est en service. La rotation post-MVP suit ce flux :

1. Générer une nouvelle paire `v2` via le script de bootstrap.
2. Ajouter `ATTESTATION_PRIVATE_KEY_PEM_V2` + `ATTESTATION_PUBLIC_KEY_ID=v2` à l'env.
3. Migrer le code `SigningKeyStore` pour gérer un mapping `{public_key_id → key}`.
4. Les nouvelles attestations utilisent `v2` ; les anciennes restent vérifiables avec `v1`.
5. Documenter l'événement (date, raison) dans un Changelog interne.

## API endpoints

### Authentifiés (PME)

| Méthode | Path | Description |
|---------|------|-------------|
| POST | `/api/attestations` | Générer une nouvelle attestation |
| GET | `/api/attestations` | Lister mes attestations |
| GET | `/api/attestations/{id}` | Détail |
| POST | `/api/attestations/{id}/revoke` | Révoquer |
| GET | `/api/attestations/{id}/download` | Télécharger PDF |

### Admin

| Méthode | Path | Description |
|---------|------|-------------|
| GET | `/api/admin/attestations` | Lister cross-tenant |
| POST | `/api/admin/attestations/{id}/revoke` | Révoquer admin |

### Publics (no-auth, rate-limited 10 req/IP/min)

| Méthode | Path | Description |
|---------|------|-------------|
| GET | `/api/public/verify/{attestation_id}` | Vérifier (4 statuts) |
| GET | `/api/public/attestation-public-key` | Exposer clé publique Ed25519 |

## Statuts de vérification

| Statut | Critère | Champs exposés |
|--------|---------|----------------|
| `authentic` | signature valide + non révoquée + non expirée | tous les champs métier (jamais nom entreprise) |
| `revoked` | révoquée par PME ou admin | + `revoked_at`, `revoked_reason`, `revoked_by_role` |
| `expired` | `valid_until < now()` | + `expired_since` |
| `invalid` | UUID inexistant OU signature corrompue | uniquement `status`, `verified_at`, `message` |

Priorité : `revoked > expired > authentic`.

## Bonnes pratiques pour le fund officer

1. **Toujours scanner le QR** depuis l'application appareil photo native du téléphone.
2. **Vérifier le hash visible** : comparer le hash imprimé en pied de page du PDF
   reçu avec celui affiché sur la page de vérification (champ `pdf_hash_sha256`).
3. **Statut révoqué** : ne jamais accepter une attestation au statut `revoked`,
   même si le PDF semble authentique.
4. **Statut expiré** : demander à la PME de générer une nouvelle attestation.
5. **Statut invalide** : c'est probablement une tentative de fraude. Signaler
   à `fraud@esg-mefali.com`.

## Sécurité

- **Anti-énumération** : statut `invalid` uniforme pour UUID inexistant et signature corrompue.
- **Rate limiting** : 10 req/IP/min sur `/api/public/verify/*`.
- **RGPD minimisation** : aucun nom d'entreprise, aucune coordonnée exposés sur la page publique.
- **Multi-tenant** : RLS PostgreSQL bloque la lecture/révocation cross-tenant pour les PME.
- **Audit log F03** : toute mutation (create, revoke) est tracée avec source_of_change.

## Limitations connues du MVP

- Une seule clé Ed25519 en service (`v1`) — rotation manuelle post-MVP.
- Stockage local des PDF/QR dans `/uploads/attestations/` — migration S3 post-MVP.
- Pas de Redis pour le rate limiting — cache LRU local FastAPI.
- Pas de CAPTCHA sur la page publique (frottement UX excessif pour MVP).
- Watermark anti-altération du PDF non implémenté (le hash SHA-256 + QR suffisent).
