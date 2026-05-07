# Contract — F08 Public API REST (no-auth)

**Spec** : [../spec.md](../spec.md)
**Plan** : [../plan.md](../plan.md)
**Date** : 2026-05-07

## Endpoints publics (aucune authentification)

Ces endpoints sont montés AVANT le middleware d'auth dans `app/main.py`. Aucun token JWT n'est requis ni validé.

### GET /api/public/verify/{attestation_id}

**Description** : vérifie publiquement le statut et l'authenticité d'une attestation.

**URL params** :
- `attestation_id` : UUID v4

**Headers** :
- `Accept-Language: fr | en` (défaut `fr`) — détermine la langue des messages

**Rate limiting** : 10 req/IP/min (FR-015). Au-delà, retourne HTTP 429 avec `Retry-After: 60`.

**Response 200 OK** : discriminated union par `status`.

#### Cas `status: "authentic"` (signature valide + non révoquée + non expirée)

```json
{
  "status": "authentic",
  "verified_at": "2026-05-07T10:35:00+00:00",
  "message": "Attestation authentique délivrée le 07/05/2026, valide jusqu'au 07/05/2027",
  "attestation_id": "abc-1234-def-5678",
  "display_id": "ATT-2026-00042",
  "attestation_type": "combined",
  "valid_from": "2026-05-07T10:30:00+00:00",
  "valid_until": "2027-05-07T10:30:00+00:00",
  "issued_at": "2026-05-07T10:30:00+00:00",
  "scores": {
    "combined": 73,
    "solvability": 68,
    "green_impact": 78,
    "esg_global": 65
  },
  "referentials": [
    {"name": "ESG Mefali", "version": "1.2", "published_at": "2026-03-15"},
    {"name": "GCF Investment Framework", "version": "2.3", "published_at": "2025-11-01"}
  ],
  "pdf_hash_sha256": "a3b8c2d1e4f5...64chars",
  "public_key_id": "v1"
}
```

#### Cas `status: "revoked"`

```json
{
  "status": "revoked",
  "verified_at": "2026-08-15T14:30:00+00:00",
  "message": "Attestation révoquée le 15/08/2026 par la PME — Raison : Mise à jour majeure du profil financier",
  "attestation_id": "abc-1234-def-5678",
  "display_id": "ATT-2026-00042",
  "attestation_type": "combined",
  "valid_from": "2026-05-07T10:30:00+00:00",
  "valid_until": "2027-05-07T10:30:00+00:00",
  "issued_at": "2026-05-07T10:30:00+00:00",
  "scores": {
    "combined": 73,
    "solvability": 68,
    "green_impact": 78,
    "esg_global": 65
  },
  "referentials": [
    {"name": "ESG Mefali", "version": "1.2", "published_at": "2026-03-15"}
  ],
  "pdf_hash_sha256": "a3b8c2d1e4f5...64chars",
  "public_key_id": "v1",
  "revoked_at": "2026-08-15T14:00:00+00:00",
  "revoked_reason": "Mise à jour majeure du profil financier",
  "revoked_by_role": "pme"
}
```

#### Cas `status: "expired"`

```json
{
  "status": "expired",
  "verified_at": "2027-06-01T09:00:00+00:00",
  "message": "Attestation expirée le 07/05/2027 — Demandez une nouvelle attestation à la PME",
  "attestation_id": "abc-1234-def-5678",
  "display_id": "ATT-2026-00042",
  "attestation_type": "combined",
  "valid_from": "2026-05-07T10:30:00+00:00",
  "valid_until": "2027-05-07T10:30:00+00:00",
  "issued_at": "2026-05-07T10:30:00+00:00",
  "scores": {
    "combined": 73,
    "solvability": 68,
    "green_impact": 78,
    "esg_global": 65
  },
  "referentials": [
    {"name": "ESG Mefali", "version": "1.2", "published_at": "2026-03-15"}
  ],
  "pdf_hash_sha256": "a3b8c2d1e4f5...64chars",
  "public_key_id": "v1",
  "expired_since": "2027-05-07T10:30:00+00:00"
}
```

#### Cas `status: "invalid"` (UUID inexistant OU signature corrompue, pas de différenciation)

```json
{
  "status": "invalid",
  "verified_at": "2026-05-07T10:35:00+00:00",
  "message": "Cet identifiant d'attestation n'existe pas ou la signature est invalide"
}
```

**Erreurs** :
- 429 Too Many Requests : `{"error": "rate_limit_exceeded", "message": "Trop de requêtes. Veuillez patienter 60 secondes.", "retry_after": 60}`

**Notes** :
- Aucune donnée nominative de la PME (nom d'entreprise, coordonnées) n'est jamais exposée.
- `revoked_by_role` est limité à `pme` ou `admin` (pas l'identité nominative).
- Le champ `display_id` (`ATT-YYYY-NNNNN`) facilite l'archivage côté fund officer.
- Les champs sont strictement whitelistés côté serveur (pas de sérialisation auto).
- L'algorithme de vérification de la signature est documenté dans `docs/attestations-and-verification.md`.

---

### GET /api/public/attestation-public-key

**Description** : récupère la clé publique Ed25519 active pour vérification offline.

**Response 200 OK** :
```json
{
  "public_key_id": "v1",
  "algorithm": "ed25519",
  "public_key_pem": "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA...\n-----END PUBLIC KEY-----",
  "canonical_format_doc_url": "https://esg-mefali.com/docs/attestations-and-verification",
  "issued_at": "2026-03-30T00:00:00+00:00"
}
```

**Notes** :
- Pas de rate limiting strict (la clé publique est statique, peut être mise en cache CDN).
- Permet à un fund officer technique de vérifier la signature d'une attestation hors-plateforme avec n'importe quelle bibliothèque Ed25519 (Python `cryptography`, Node.js `tweetnacl`, Go `crypto/ed25519`, Rust `ed25519-dalek`).

**Algorithme de vérification offline (documenté)** :
```python
import json, base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

# 1. Charger la clé publique depuis la réponse
public_key_pem = "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
public_key = serialization.load_pem_public_key(public_key_pem.encode())

# 2. Reconstituer le payload canonique
canonical = json.dumps({
    "attestation_id": "abc-1234-def-5678",
    "scores": {"combined": 73, "solvability": 68, "green_impact": 78, "esg_global": 65},
    "referential_snapshot": [
        {"name": "ESG Mefali", "version": "1.2", "published_at": "2026-03-15"}
    ],
    "pdf_hash_sha256": "a3b8c2d1...",
    "valid_from": "2026-05-07T10:30:00+00:00",
    "valid_until": "2027-05-07T10:30:00+00:00",
}, sort_keys=True, separators=(",", ":"))

# 3. Vérifier la signature
signature = base64.b64decode("...")  # signature_ed25519 récupérée via API
try:
    public_key.verify(signature, canonical.encode("utf-8"))
    print("✓ Signature valide")
except InvalidSignature:
    print("✗ Signature invalide")
```

---

## Comportement anti-énumération (FR-015, FR-016, SC-006)

- **Statut uniforme `invalid`** : pour UUID inexistant ET pour UUID valide mais signature corrompue, la même réponse est retournée.
- **Aucune différenciation timing** : la latence DB normale (~1-5 ms pour un SELECT indexé) couvre la différence entre les deux cas. Le serveur effectue toujours un SELECT (pas de short-circuit logique avant le SELECT).
- **Rate limiting** : 10 req/IP/min via cache LRU local. Au-delà, HTTP 429.
- **Logs WARN** : si > 5 hits/IP/min sur `/api/public/verify/*`, événement WARN avec adresse IP et user-agent (sans persister en BDD).
- **Pas de CAPTCHA** : frottement utilisateur trop élevé pour le fund officer occasionnel. UUID v4 (122 bits d'entropie) protège suffisamment contre l'énumération aléatoire.

## Exemples cURL

```bash
# 1. Vérifier une attestation publique (no-auth)
curl https://esg-mefali.com/api/public/verify/abc-1234-def-5678

# 2. Récupérer la clé publique
curl https://esg-mefali.com/api/public/attestation-public-key

# 3. Tester le rate limiting (devrait retourner 429 après le 10ème hit)
for i in {1..15}; do
    curl -w "%{http_code}\n" -o /dev/null -s \
        https://esg-mefali.com/api/public/verify/00000000-0000-0000-0000-000000000000
done
# 200 200 200 200 200 200 200 200 200 200 429 429 429 429 429
```
