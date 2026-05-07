# Quickstart — F08 Attestation Vérifiable Ed25519

**Spec** : [spec.md](./spec.md)
**Plan** : [plan.md](./plan.md)
**Date** : 2026-05-07

## Pré-requis

- Backend ESG Mefali tournant (`uvicorn app.main:app --port 8000`)
- Frontend Nuxt tournant (`npm run dev` sur :3000)
- Base PostgreSQL accessible via Docker Compose (`docker compose up postgres -d`)
- Migrations à jour (`alembic upgrade head` après l'application de `026_create_attestations`)
- Au moins un user PME avec un `CreditScore` finalisé et une `EsgAssessment` finalisée

## Étape 0 — Bootstrap des clés Ed25519

**Une seule fois** au démarrage du projet, générer la paire Ed25519 :

```bash
$ source backend/venv/bin/activate
$ python backend/scripts/generate_attestation_keypair.py
```

Sortie attendue :
```
=== Generated Ed25519 Keypair ===
public_key_id: v1

# Ajouter dans backend/.env :
ATTESTATION_PRIVATE_KEY_PEM='-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----'
ATTESTATION_PUBLIC_KEY_ID=v1
ATTESTATION_VALIDITY_DAYS=365
ATTESTATION_VERIFICATION_BASE_URL=http://localhost:3000

# Pour la production, stocker la clé privée dans le secret manager.
# Ne JAMAIS commiter ATTESTATION_PRIVATE_KEY_PEM en git.
```

Copier la clé privée (`ATTESTATION_PRIVATE_KEY_PEM=...`) dans `backend/.env` (gitignoré).

Redémarrer le backend pour prendre en compte les variables :
```bash
$ uvicorn app.main:app --port 8000 --reload
INFO:     Loading attestation key... public_key_id=v1
INFO:     Application startup complete.
```

Si la variable est manquante en production : l'app refuse de démarrer avec :
```
ValueError: ATTESTATION_PRIVATE_KEY_PEM is required in production. Run scripts/generate_attestation_keypair.py to bootstrap.
```

## Étape 1 — Créer une attestation via l'API REST

```bash
# Authentification PME
$ TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"pme@test.com","password":"motdepasse"}' | jq -r .access_token)

# Génération attestation combined (crédit + ESG)
$ curl -X POST http://localhost:8000/api/attestations \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"attestation_type":"combined"}' | jq

{
  "attestation_id": "abc-1234-def-5678",
  "display_id": "ATT-2026-00042",
  "verification_url": "http://localhost:3000/verify/abc-1234-def-5678",
  "pdf_path": "/uploads/attestations/pdfs/abc-1234-def-5678.pdf",
  "qr_code_path": "/uploads/attestations/qr/abc-1234-def-5678.png",
  "valid_from": "2026-05-07T10:30:00+00:00",
  "valid_until": "2027-05-07T10:30:00+00:00",
  "public_key_id": "v1",
  "pdf_hash_sha256": "a3b8c2d1...64chars"
}
```

Le PDF est disponible à `backend/uploads/attestations/pdfs/abc-1234-def-5678.pdf`.

Le QR code est disponible à `backend/uploads/attestations/qr/abc-1234-def-5678.png`.

## Étape 2 — Télécharger le PDF

```bash
$ curl http://localhost:8000/api/attestations/abc-1234-def-5678/download \
    -H "Authorization: Bearer $TOKEN" \
    -o my-attestation.pdf

$ open my-attestation.pdf
```

Le PDF contient :
- Le QR code en haut
- L'identifiant `Attestation #ATT-2026-00042`
- Les scores (combined, solvability, green_impact, esg_global)
- Les référentiels avec versions
- L'annexe « Sources et références » (F01)
- Le hash SHA-256 en pied de page

## Étape 3 — Vérifier publiquement (sans authentification)

```bash
# Pas de token JWT — vérification publique
$ curl http://localhost:8000/api/public/verify/abc-1234-def-5678 | jq

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
  "scores": {"combined": 73, "solvability": 68, "green_impact": 78, "esg_global": 65},
  "referentials": [
    {"name": "ESG Mefali", "version": "1.2", "published_at": "2026-03-15"}
  ],
  "pdf_hash_sha256": "a3b8c2d1...64chars",
  "public_key_id": "v1"
}
```

## Étape 4 — Vérifier via le navigateur (UI)

1. Ouvrir un onglet privé (sans cookies) : `http://localhost:3000/verify/abc-1234-def-5678`
2. La page charge sans redirection vers `/login`
3. Le badge vert **AUTHENTIQUE** s'affiche
4. Les scores et référentiels sont visibles
5. Le hash SHA-256 est en monospace, copiable
6. Le bouton « Comparer avec votre PDF » permet de coller le hash imprimé sur le PDF et de comparer

## Étape 5 — Récupérer la clé publique (vérification offline)

```bash
$ curl http://localhost:8000/api/public/attestation-public-key | jq

{
  "public_key_id": "v1",
  "algorithm": "ed25519",
  "public_key_pem": "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA...\n-----END PUBLIC KEY-----",
  "canonical_format_doc_url": "http://localhost:3000/docs/attestations-and-verification",
  "issued_at": "2026-03-30T00:00:00+00:00"
}
```

Vérifier offline en Python :
```python
import json, base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

# 1. Charger la clé publique
public_key_pem = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEA...
-----END PUBLIC KEY-----"""
public_key = serialization.load_pem_public_key(public_key_pem.encode())

# 2. Reconstituer le payload canonique (depuis l'API)
canonical = json.dumps({
    "attestation_id": "abc-1234-def-5678",
    "scores": {"combined": 73, "solvability": 68, "green_impact": 78, "esg_global": 65},
    "referential_snapshot": [{"name": "ESG Mefali", "version": "1.2", "published_at": "2026-03-15"}],
    "pdf_hash_sha256": "a3b8c2d1...",
    "valid_from": "2026-05-07T10:30:00+00:00",
    "valid_until": "2027-05-07T10:30:00+00:00",
}, sort_keys=True, separators=(",", ":"))

# 3. Vérifier
signature = base64.b64decode("...")  # signature_ed25519 récupérée
public_key.verify(signature, canonical.encode("utf-8"))
print("✓ Signature valide — attestation authentique")
```

## Étape 6 — Révoquer une attestation

```bash
$ curl -X POST http://localhost:8000/api/attestations/abc-1234-def-5678/revoke \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"reason":"Mise à jour majeure du profil financier"}' | jq

{
  "attestation_id": "abc-1234-def-5678",
  "revoked_at": "2026-08-15T14:00:00+00:00",
  "revoked_reason": "Mise à jour majeure du profil financier",
  "revoked_by_user_id": "user-uuid-pme",
  "verification_url": "http://localhost:3000/verify/abc-1234-def-5678"
}
```

Recharger `/verify/abc-1234-def-5678` (en onglet privé) → badge rouge **RÉVOQUÉE** affiché.

## Étape 7 — Tester l'expiration (manipulation manuelle pour démo)

```bash
$ docker compose exec postgres psql -U esg_mefali -d esg_mefali_db -c \
    "UPDATE attestations SET valid_until = NOW() - INTERVAL '1 day' WHERE id = 'abc-1234-def-5678';"
```

Recharger `/verify/abc-1234-def-5678` → badge orange **EXPIRÉE** affiché.

## Étape 8 — Tester l'UUID invalide

```bash
$ curl http://localhost:8000/api/public/verify/00000000-0000-0000-0000-000000000000 | jq

{
  "status": "invalid",
  "verified_at": "2026-05-07T11:00:00+00:00",
  "message": "Cet identifiant d'attestation n'existe pas ou la signature est invalide"
}
```

Ouvrir `/verify/00000000-0000-0000-0000-000000000000` → badge rouge **INVALIDE** affiché (sans leak d'information).

## Étape 9 — Tester le rate limiting

```bash
$ for i in {1..15}; do
    curl -w "%{http_code}\n" -o /dev/null -s \
        http://localhost:8000/api/public/verify/abc-1234-def-5678
  done

200
200
200
200
200
200
200
200
200
200
429
429
429
429
429
```

Au-delà de 10 requêtes/IP/min, retourne 429.

## Étape 10 — Générer une attestation depuis le chat (LLM)

Ouvrir `http://localhost:3000/chat` (logé en PME), saisir :

```
Génère-moi une attestation pour mon score crédit
```

Observer dans le SSE stream :
- Event `tool_call_start` avec `name=generate_credit_certificate`
- Event `tool_call_end` avec `result={ok:true, verification_url:...}`
- Réponse texte du LLM : « Votre attestation est prête. Vous pouvez la télécharger ici : ... ou la vérifier publiquement à : `http://localhost:3000/verify/...`. »

Vérifier en base :
```bash
$ docker compose exec postgres psql -U esg_mefali -d esg_mefali_db -c \
    "SELECT id, attestation_type, display_id FROM attestations ORDER BY created_at DESC LIMIT 1;"
```

## Vue Admin

```bash
# Login admin
$ ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@esg-mefali.com","password":"..."}' | jq -r .access_token)

# Liste cross-tenant des attestations
$ curl http://localhost:8000/api/admin/attestations \
    -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# Révoquer cross-tenant
$ curl -X POST http://localhost:8000/api/admin/attestations/abc-1234-def-5678/revoke \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"reason":"Suspicion de fraude — investigation en cours"}'
```

## Tests E2E

```bash
$ cd frontend
$ npx playwright test tests/e2e/F08-attestation-verifiable-ed25519.spec.ts --reporter=html
```

5 scénarios :
1. Générer attestation → télécharger PDF → page publique affiche AUTHENTIQUE
2. Altérer le PDF (modification du hash visible) → comparaison hash → discordance détectée
3. Révoquer → recharger /verify/[id] → RÉVOQUÉE
4. Date système après valid_until → EXPIRÉE
5. UUID inexistant → INVALIDE (sans leak timing)

## Documentation utilisateur

`docs/attestations-and-verification.md` (rédigé en F08) explique :
- Le format canonique JSON utilisé pour la signature
- L'algorithme de vérification offline (Python, Node.js, Go, Rust)
- La procédure de rotation des clés post-MVP
- Les bonnes pratiques pour le fund officer (vérifier le hash, scanner systématiquement le QR)

## Troubleshooting

| Problème | Cause probable | Solution |
|----------|---------------|----------|
| Backend refuse de démarrer : `ATTESTATION_PRIVATE_KEY_PEM is required` | Variable d'env manquante | Exécuter `scripts/generate_attestation_keypair.py` et copier dans `.env` |
| Signature invalide même sur attestation fraîche | Format canonique différent (ordre des clés, espaces) | Vérifier que la sérialisation utilise `sort_keys=True, separators=(",", ":")` |
| `/verify/[id]` redirige vers `/login` | Middleware `auth.global.ts` non modifié | Vérifier que la regex exception `/verify/` ou `/legal/` est bien en place |
| QR code ne se scanne pas | Scale trop petit ou error level trop bas | `segno.make(url, error="M")` + `scale=10` minimum |
| Hash PDF ne correspond pas | PDF altéré OU calcul du hash après écriture | Vérifier que `hash = hashlib.sha256(pdf_bytes).hexdigest()` est calculé après `tempfile.flush()` |
| Rate limiting 429 inattendu | Tests E2E parallèles depuis même IP | Désactiver rate limiting en mode test (`if settings.ENV == "test": skip`) |
