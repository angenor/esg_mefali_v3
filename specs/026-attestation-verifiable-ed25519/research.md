# Phase 0 : Research — F08 Attestation Vérifiable Ed25519

**Spec** : [spec.md](./spec.md)
**Plan** : [plan.md](./plan.md)
**Date** : 2026-05-07

## Décisions de design technique

### 1. Bibliothèque cryptographique : `cryptography>=41.0`

**Décision** : utiliser `cryptography>=41.0` (sous-paquet `cryptography.hazmat.primitives.asymmetric.ed25519`) pour la signature et la vérification Ed25519.

**Alternatives écartées** :
- `pynacl>=1.5` (libsodium) : excellent pour des cas avancés (multi-curve, NaCl boxes), mais ajoute une dépendance C externe non déjà présente dans le projet.
- `pycryptodome` : non recommandé pour Ed25519 moderne (API datée).

**Rationale** :
- `cryptography` est mainteneur PyCA (Python Cryptographic Authority) et est largement adopté dans l'écosystème (FastAPI, Starlette, JWT libs y dépendent transitivement).
- API de haut niveau : `Ed25519PrivateKey.generate()`, `from_private_bytes()`, `sign()`, `from_public_bytes()`, `verify()` — pas besoin de plonger dans les primitives bas niveau.
- Vérification offline supportée : un fund officer technique peut récupérer la clé publique via `GET /api/public/attestation-public-key` et reproduire la vérification avec la même bibliothèque.
- Sérialisation PEM standard (PKCS8 base64) compatible avec les outils crypto système (openssl).

**Format de la clé** :
- Clé privée : PEM PKCS8 base64 (chargée depuis env var `ATTESTATION_PRIVATE_KEY_PEM`, multi-ligne dans un single-line `\n` encodé)
- Clé publique : PEM (Subject Public Key Info) exposée via `GET /api/public/attestation-public-key`

**Format canonique de la signature** :
```python
canonical = json.dumps({
    "attestation_id": str(attestation.id),
    "scores": {"combined": 73, "solvability": 68, "green_impact": 78, "esg_global": 65},
    "referential_snapshot": [...],
    "pdf_hash_sha256": pdf_hash,
    "valid_from": valid_from.isoformat(),
    "valid_until": valid_until.isoformat(),
}, sort_keys=True, separators=(",", ":"))  # déterministe, reproductible
signature = private_key.sign(canonical.encode("utf-8"))
attestation.signature_ed25519 = base64.b64encode(signature).decode("ascii")
```

**Vérification** :
```python
public_key.verify(base64.b64decode(signature), canonical.encode("utf-8"))
# raise InvalidSignature si non valide
```

---

### 2. Bibliothèque QR code : `segno>=1.5`

**Décision** : utiliser `segno>=1.5` pour la génération de QR codes au format PNG.

**Alternatives écartées** :
- `qrcode>=7.4` : nécessite Pillow comme dépendance pour PNG (alourdit l'image Docker).
- `python-qrcode` (PyPI legacy) : abandonné.

**Rationale** :
- `segno` est minimaliste (~50 KB pure Python) et autonome (PNG natif sans Pillow obligatoire).
- Compression intelligente : produit des QR codes de taille minimale pour une URL donnée (mode automatique alphanumérique vs binaire).
- Export multi-format direct : PNG, SVG, EPS, PDF.
- Pour le MVP, on n'utilise que PNG (`scale=10` → ~300x300 px, `error="M"` pour récupération moyenne suffisante pour un QR scanné depuis un PDF imprimé).

**Usage** :
```python
import segno
qr = segno.make(verification_url, error="M")
qr.save(qr_path, scale=10, dark="black", light="white")  # PNG ~3 ko
```

**Pourquoi `error="M"` (15 % récupération)** plutôt que `error="H"` (30 %) :
- `error="M"` produit un QR plus petit, plus facile à scanner depuis un PDF imprimé.
- `error="H"` (utilisé pour QR avec logo overlay) n'est pas nécessaire ici (pas de logo).

---

### 3. Stockage de la clé privée Ed25519

**Décision** : variable d'environnement `ATTESTATION_PRIVATE_KEY_PEM` au format PEM PKCS8 base64, chargée au démarrage de l'app via `core/config.py` puis mise en cache dans une singleton `SigningKeyStore`.

**Alternatives écartées** :
- Vault (HashiCorp) / AWS Secrets Manager : ajoute une dépendance d'infra non triviale, surdimensionné pour le MVP.
- Fichier monté en volume : moins sécurisé (un fichier secret en clair est plus visible qu'une variable d'environnement isolée par le process).
- Fichier `.env` checké en git : interdit par invariant `.cc-orchestrator.md` #6.

**Rationale** :
- Variable d'env est l'approche la plus simple et alignée avec la pratique existante (`OPENROUTER_API_KEY`, `JWT_SECRET_KEY`).
- En production, l'env var est injectée par le secret manager d'infra (Docker secrets / Kubernetes secrets / AWS ECS Task Definition).
- En développement, l'opérateur génère sa propre paire via `scripts/generate_attestation_keypair.py` et l'injecte dans son `.env` local (qui est gitignoré).
- En tests pytest, une fixture session-scope génère une paire à la volée (jamais persistée).

**Bootstrap** :
```bash
# Une seule fois au démarrage du projet
$ python scripts/generate_attestation_keypair.py
=== Generated Ed25519 Keypair ===
public_key_id: v1
ATTESTATION_PRIVATE_KEY_PEM=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
ATTESTATION_PUBLIC_KEY_PEM=-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----
ATTESTATION_PUBLIC_KEY_ID=v1
```

**Rotation post-MVP** :
- Ajouter `ATTESTATION_PRIVATE_KEY_PEM_V2` + `ATTESTATION_PUBLIC_KEY_ID=v2` à l'env.
- `SigningKeyStore` gère un mapping `{public_key_id → key}` ; les nouvelles attestations utilisent la clé active (`v2`), les anciennes attestations restent vérifiables avec `v1`.
- Procédure documentée dans `docs/attestations-and-verification.md`.

---

### 4. Anti-énumération du endpoint public

**Décision** : statut uniforme `invalid` pour UUID inexistant ET signature corrompue, rate limiting 10 req/IP/min, pas de différenciation timing.

**Alternatives écartées** :
- HTTP 404 pour UUID inexistant + 200 invalid pour UUID valide : leak l'existence des attestations.
- CAPTCHA : frottement utilisateur trop élevé pour un fund officer occasionnel.

**Rationale** :
- UUID v4 a 122 bits d'entropie → énumération aléatoire pratiquement impossible (probabilité de collision ~10⁻³⁶ même après 10⁹ requêtes).
- Le rate limiting 10 req/IP/min protège contre un attaquant déterminé.
- Le statut uniforme `invalid` ne révèle rien d'utile à un attaquant (il sait juste que sa devinette est fausse).
- La latence DB normale (lecture d'un index UUID) couvre la différence de timing entre « UUID hors plage » et « UUID en base mais signature corrompue ». SC-006 valide statistiquement (test Mann-Whitney p > 0.1).

**Implémentation rate limiting** :
- Cache LRU local en mémoire FastAPI (pas de Redis pour le MVP). Clé = IP source, valeur = compteur sur fenêtre glissante 1 min. Capacité 10 000 IPs (TTL 60 s par entrée).
- Au-delà du seuil, retourne HTTP 429 avec header `Retry-After: 60`.
- Logs WARN si > 5 hits/IP/min sur `/api/public/verify/*` (sans persister en BDD pour ne pas saturer audit log).

---

### 5. Whitelist explicite des métadonnées publiques

**Décision** : DTO explicite côté serveur (jamais de sérialisation automatique du modèle SQLAlchemy → JSON).

**Champs exposés selon statut** :

| Champ | `authentic` | `revoked` | `expired` | `invalid` |
|-------|-------------|-----------|-----------|-----------|
| `status` | ✓ | ✓ | ✓ | ✓ |
| `verified_at` | ✓ | ✓ | ✓ | ✓ |
| `message` | ✓ (i18n) | ✓ | ✓ | ✓ |
| `attestation_id` | ✓ | ✓ | ✓ | ✗ |
| `attestation_type` | ✓ | ✓ | ✓ | ✗ |
| `valid_from` | ✓ | ✓ | ✓ | ✗ |
| `valid_until` | ✓ | ✓ | ✓ | ✗ |
| `issued_at` | ✓ | ✓ | ✓ | ✗ |
| `scores` | ✓ | ✓ | ✓ | ✗ |
| `referentials` | ✓ | ✓ | ✓ | ✗ |
| `pdf_hash_sha256` | ✓ | ✓ | ✓ | ✗ |
| `public_key_id` | ✓ | ✓ | ✓ | ✗ |
| `revoked_at` | ✗ | ✓ | ✗ | ✗ |
| `revoked_reason` | ✗ | ✓ | ✗ | ✗ |
| `revoked_by_role` | ✗ | ✓ (`pme`/`admin`, sans nom) | ✗ | ✗ |
| `expired_since` | ✗ | ✗ | ✓ | ✗ |

**Rationale** :
- Principe RGPD de minimisation (préparation F05) : aucun nom d'entreprise, aucune coordonnée, aucun détail des indicateurs ESG/crédit.
- `revoked_by_role` (string `pme` ou `admin`) plutôt que `revoked_by_user_id` (UUID lourd) ou `revoked_by_user_email` (PII).
- Les scores affichés sont les agrégats finaux (combined, solvabilité, impact, ESG global) — pas le détail des 30 critères ESG ni les facteurs de calcul.

---

### 6. Format canonique JSON pour la signature

**Décision** : `json.dumps(payload, sort_keys=True, separators=(",", ":"))` UTF-8, déterministe.

**Spécification** :
- Clés ordonnées alphabétiquement (`sort_keys=True`).
- Pas d'espace dans les séparateurs (`separators=(",", ":")`).
- Encodage UTF-8 strict (pas de BOM).
- Floats sérialisés sans notation scientifique (les scores sont des entiers Pydantic `int` ; aucun float dans le payload).
- Datetime ISO 8601 avec timezone explicite (`2026-05-07T10:30:00+00:00`).

**Reproductible offline** : le format est canonique RFC 8785 ("JSON Canonicalization Scheme")-compatible (limitations connues sur les nombres flottants ne s'appliquent pas car payload est `int`/`str`).

**Documenté dans `docs/attestations-and-verification.md`** : un fund officer technique peut reproduire la vérification en Python, Node.js, Go avec n'importe quelle lib JSON canonique.

---

### 7. Compteur `ATT-YYYY-NNNNN`

**Décision** : compteur scopé `(account_id, année_valid_from)` calculé à la volée à la création.

**Alternatives écartées** :
- Table dédiée `attestation_counters(account_id, year, last_n)` avec lock SELECT FOR UPDATE : surdimensionné pour la volumétrie attendue.
- Compteur global cross-tenant : leak la volumétrie totale du système.

**Rationale** :
- Volumétrie attendue : 100-1000 attestations/mois TOTAL. Par PME : ≤ 50/an. COUNT(*) sur indexed sub-query = 1-5 ms.
- Implémentation :
  ```python
  next_n = await session.execute(
      select(func.count(Attestation.id)).where(
          Attestation.account_id == account_id,
          extract('year', Attestation.valid_from) == valid_from.year
      )
  ) + 1
  display_id = f"ATT-{valid_from.year}-{next_n:05d}"
  ```
- Pas de risque de collision : transaction unique par INSERT, COUNT effectué dans la même transaction.

**Affichage** :
- `ATT-2026-00042` apparaît sur le PDF (visible) et dans la page publique (champ `attestation_id_display`).
- L'UUID v4 reste l'identifiant technique unique en base et dans l'URL de vérification.

---

### 8. Réutilisation des composants existants

**Composants Vue réutilisés (pas de duplication)** :
- `<SourceLink>` (F01) : utilisé dans l'annexe sources du PDF (rendering HTML par WeasyPrint, pas Vue, mais on conserve la cohérence visuelle des marqueurs sources).
- `<MoneyDisplay>` (F04) : utilisé sur `/attestations` si on affiche un montant `target_amount` issu d'un projet associé.
- `useFocusTrap` (F18 héritage) : utilisé dans `RevokeAttestationModal.vue` pour le piège de focus accessible.

**Composants Vue créés (nouveaux, génériques)** :
- `AttestationStatusBadge.vue` : paramétrable via prop `status: 'authentic' | 'revoked' | 'expired' | 'invalid'`. Réutilisable post-MVP par d'autres types de statuts visuels.
- `HashCompareInput.vue` : paramétrable via prop `expected: string` + emit `compared`. Utile post-MVP pour d'autres comparaisons hash (signatures, checksums).

**Pas de réutilisation forcée** : aucun composant existant ne couvre exactement le pattern card attestation + actions (download/copy/revoke). On crée donc `AttestationCard.vue` dédié.

---

## Recommandations pour la Phase 1 (Design & Contracts)

- **API REST** : 4 endpoints authentifiés + 2 endpoints publics no-auth. Voir `contracts/attestations-api.md` et `contracts/public-api.md`.
- **Tools LangChain** : 1 tool refactoré (`generate_credit_certificate`). Voir `contracts/attestations-tools-langchain.md`.
- **Schéma DB** : 1 table `attestations` avec 21 colonnes, 2 indexes, RLS héritée F02. Voir `data-model.md`.
- **Migration Alembic** : `026_create_attestations.py` avec `down_revision` conditionnelle (à fixer au moment du merge selon état de `main`).
- **Frontend** : 4 pages, 1 layout, 4 composants, 1 composable, 1 fichier i18n. Voir `plan.md` § Source Code.
