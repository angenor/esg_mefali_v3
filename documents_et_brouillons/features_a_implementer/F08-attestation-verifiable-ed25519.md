# F08 — Attestation Vérifiable Ed25519 + QR + Page Publique `/verify/{id}` + Révocation

**Module(s) source(s)** : Module 5.3 (Attestation et Certification du Score)
**Priorité** : P0 — bloquante pour le différenciateur produit n°2 (vérification hors-plateforme)
**Dépendances** : F01 (sources, référentiels versionnés), F02 (multi-tenant + admin), F04 (Money typed pour scores), F09 (révocation par admin)
**Estimation** : 2 sprints

## Contexte & motivation

**Module 5.3 — Innovation 9 du brainstorming** : « la plateforme étant fermée aux intermédiaires, le partage du score se fait via une attestation vérifiable que la PME contrôle et transmet par ses propres canaux. Le fund officer scanne un QR code pour vérifier l'authenticité — pas besoin de compte. »

**État actuel** :
- `generate_certificate_pdf` (`backend/app/modules/credit/certificate.py:4-57`) génère un PDF basique via WeasyPrint
- Template `certificate_template.html` simpliste : pas de signature, pas de QR, pas d'identifiant unique visible
- **Aucune signature numérique Ed25519** (pas d'import `nacl` ni `cryptography.hazmat.primitives.asymmetric.ed25519`)
- **Aucun QR code** (pas de `qrcode`/`segno` dans les dépendances)
- **Aucune page publique `/verify/{id}`** : recherche `verify_*` retourne uniquement `verify_password` dans `core/security.py`. Aucune page Vue `pages/verify/[id].vue`. Le middleware `auth.global.ts` n'autorise que `/login` et `/register` en pages publiques.
- **Aucune logique de révocation** : pas de champ `revoked`, `revoked_at`, `revocation_reason` sur `CreditScore`. Aucun endpoint de révocation.
- Tool LLM `generate_credit_certificate` est un **placeholder** (`credit_tools.py:101-119` retourne un chemin fictif `/uploads/certificates/...` sans appel à `generate_certificate_pdf`)
- Score ESG par référentiel non inclus dans le template (Module 0.5 versioning manquant)
- Aucun hash document conforme

**Conséquences** :
- Le différenciateur produit le plus visible aux yeux d'un fund officer (vérification QR sans login) n'existe pas
- L'attestation actuelle est **non vérifiable** : un PDF peut être altéré, l'URL fictive ne mène nulle part
- Risque crédibilité MAJEUR

## User stories

- **PME** : « Je veux générer une attestation PDF de mon score crédit + ESG, signée numériquement, que je peux télécharger et envoyer par email à mon banquier. »
- **PME** : « Je veux que l'attestation contienne un QR code + un lien `https://esg-mefali.com/verify/{attestation_id}` que mon banquier peut scanner/ouvrir pour vérifier l'authenticité sans avoir besoin de créer un compte. »
- **PME** : « Si mon profil change significativement (nouveau scoring), je veux pouvoir révoquer l'ancienne attestation pour qu'elle apparaisse "RÉVOQUÉE" sur la page publique. »
- **Fund officer (utilisateur tiers, hors plateforme)** : « Je scanne le QR avec mon téléphone, je tombe sur une page publique qui m'affiche : authentique/révoquée, score, référentiel utilisé, version, date d'émission, hash document. Je peux comparer avec le PDF reçu. »
- **Admin** : « En cas d'incident détecté (fraude, erreur de calcul majeure), je dois pouvoir révoquer une attestation côté plateforme. »

## Périmètre fonctionnel

### Modèle `Attestation` (premier rang)

Nouvelle table `attestations` (séparée de `credit_scores` qui reste l'objet de calcul) :
- `id: UUID PK` (= `attestation_id` exposé publiquement)
- `account_id: UUID FK accounts.id NOT NULL` (multi-tenant F02)
- `user_id: UUID FK users.id NOT NULL` (qui a généré)
- `attestation_type: enum('credit_score', 'esg_assessment', 'combined')` (extensible)
- `payload: jsonb NOT NULL` (snapshot complet : scores, référentiels avec versions, indicateurs avec sources)
- `referential_snapshot: jsonb` (versioning F04 capturé)
- `pdf_path: str` (chemin local/S3 du PDF généré)
- `pdf_hash_sha256: str(64) NOT NULL` (hash du PDF pour vérification)
- `signature_ed25519: str NOT NULL` (signature détachée de `payload + pdf_hash_sha256`)
- `public_key_id: str` (identifiant de la clé publique utilisée — permet rotation post-MVP)
- `qr_code_path: str` (PNG du QR généré)
- `valid_from: datetime`
- `valid_until: datetime` (1 an par défaut)
- `revoked_at: datetime | null`
- `revoked_reason: str | null`
- `revoked_by_user_id: UUID FK users.id | null` (PME elle-même ou admin)
- `verification_url: str` (= `https://esg-mefali.com/verify/{id}`)
- `created_at`, `updated_at`

### Génération de signature Ed25519

Lib : `cryptography>=41.0` (déjà fréquente) ou `pynacl>=1.5`.

Au démarrage de l'app, charger une clé privée Ed25519 depuis variable env `ATTESTATION_PRIVATE_KEY_PEM` (rotation post-MVP). La clé publique correspondante est exposée publiquement à `/api/attestations/public-key`.

Signature :
```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

# Au moment de génération :
canonical = json.dumps({
    "attestation_id": str(attestation.id),
    "scores": {...},
    "referential_snapshot": {...},
    "pdf_hash_sha256": pdf_hash,
    "valid_from": valid_from.isoformat(),
    "valid_until": valid_until.isoformat(),
}, sort_keys=True, separators=(",", ":"))
signature = private_key.sign(canonical.encode("utf-8"))
attestation.signature_ed25519 = base64.b64encode(signature).decode()
```

Vérification (côté page publique) :
```python
public_key.verify(base64.b64decode(signature), canonical.encode("utf-8"))
```

### Génération QR code

Lib : `segno>=1.5` (préférée pour MVP, taille minimale) ou `qrcode>=7.4`.

```python
import segno
qr = segno.make(verification_url, error="M")
qr.save(qr_path, scale=10, dark="black", light="white")
```

QR pointe vers `https://esg-mefali.com/verify/{attestation_id}`.

### Template HTML enrichi

Refactor `backend/app/modules/credit/certificate_template.html` (renommer en `attestation_template.html`) :
- Header avec logo + identifiant unique visible (`Attestation #ATT-2026-00042`)
- Sections : 
  - Identité PME (nom, sector, location)
  - Scores (combined, solvability, green_impact, ESG par référentiel sélectionné)
  - **Référentiel(s) utilisé(s) avec versions** : "Évalué selon ESG Mefali v1.2 du 15/03/2026 + GCF Investment Framework v2.3"
  - Sources et références (annexe auto-générée F01)
  - Date d'émission + validité
  - **QR code** (image PNG embarqué via `<img src="data:image/png;base64,...">`)
  - **URL de vérification** en clair (texte) sous le QR
  - **Hash SHA-256** du PDF en pied de page (en hexa)
  - Disclaimer : "Cette attestation ne se substitue pas à une évaluation bancaire formelle. Vérification : https://esg-mefali.com/verify/{id}"

### Service `attestations`

`backend/app/modules/attestations/service.py` :
- `generate_attestation(account_id, user_id, type, scores_to_include) → Attestation`
  1. Calculer le payload (scores, snapshot référentiels)
  2. Générer le PDF (WeasyPrint) avec template enrichi
  3. Calculer SHA-256 du PDF
  4. Signer (canonical_json + pdf_hash) avec Ed25519
  5. Générer QR code
  6. Persister `Attestation` row avec audit_log (F03)
  7. Retourner l'objet
- `revoke_attestation(attestation_id, reason, revoked_by_user_id)`
- `verify_attestation(attestation_id) → VerificationResult` (utilisé par la page publique)

### Page publique `/verify/{id}` (CRITIQUE)

Layout `frontend/app/layouts/public.vue` (créé par F02 ou ici) :
- Pas de sidebar, pas de header user, juste un header simple "ESG Mefali — Vérification d'attestation"
- Pas d'auth requise
- Footer minimaliste

Page `frontend/app/pages/verify/[id].vue` :
- Récupère `GET /api/public/verify/{attestation_id}` (no-auth)
- Affichage selon `verification_status` :
  - **AUTHENTIQUE** (vert ✓) : "Attestation #ATT-2026-00042 délivrée le 15/03/2026, valide jusqu'au 14/03/2027"
    - Métadonnées non sensibles : type, score combiné, score solvabilité, score impact, référentiels utilisés, hash PDF
    - Bouton "Comparer avec votre PDF" : champ pour coller le hash du PDF reçu, comparaison
  - **RÉVOQUÉE** (rouge ✗) : "Attestation révoquée le 30/03/2026 par la PME — Raison : Mise à jour majeure du profil"
  - **EXPIRÉE** (orange ⚠️) : "Attestation expirée le 14/03/2027 — Demandez une nouvelle attestation à la PME"
  - **INVALIDE** (rouge ✗) : "Cet identifiant d'attestation n'existe pas ou la signature est invalide"

Aucune donnée sensible additionnelle (pas de coordonnées, pas de profil entreprise, pas de breakdown détaillé).

Modifier le middleware `frontend/app/middleware/auth.global.ts` pour ajouter `/verify/[id]` aux pages publiques.

### Endpoint backend public

`backend/app/api/public.py` (nouveau router, pas d'auth) :
- `GET /api/public/verify/{attestation_id}` :
  - Charge l'attestation
  - Vérifie la signature Ed25519
  - Retourne `{status: 'authentic' | 'revoked' | 'expired' | 'invalid', metadata: {...}, message: str}`
  - Métadonnées NON sensibles (whitelisté côté serveur)
- `GET /api/public/attestation-public-key` : retourne la clé publique Ed25519 pour vérification offline (un fund officer technique peut la récupérer et vérifier signatures localement)

### Révocation

Endpoints :
- `POST /api/attestations/{id}/revoke` (PME, son propre attestation, raison facultative) → audit log F03
- `POST /api/admin/attestations/{id}/revoke` (admin, raison obligatoire) → audit log F03

UI :
- Sur la page `/credit-score` ou nouvelle page `/attestations` : liste des attestations émises avec statut, bouton "Révoquer" (avec modal de confirmation et raison libre)
- Page admin : `pages/admin/attestations/index.vue` (back-office) : liste globale, possibilité de révoquer

### Tool LLM corrigé

Réécrire `backend/app/graph/tools/credit_tools.py:generate_credit_certificate` :
- Appelle réellement `attestations/service.generate_attestation`
- Retourne le `verification_url` + chemin PDF + identifiant attestation
- LLM peut copier le verification_url dans la conversation

### Intégration aux dossiers de candidature (Module 3.3 / F15)

- `FundApplication` peut référencer une `Attestation` (FK `attestation_id` nullable)
- Dans le PDF du dossier généré, inclure une section "Attestation ESG Mefali" avec QR + résumé
- L'utilisateur choisit lors de la génération du dossier s'il veut joindre une attestation existante ou en générer une nouvelle

## Hors-scope (post-MVP)

- Rotation automatique des clés Ed25519 avec gestion HSM
- Signature multi-clés (M-of-N pour attestations critiques)
- Ancrage blockchain (hash sur Ethereum/Polygon pour preuve d'antériorité — overkill pour MVP, pertinent post-MVP)
- Wallet PME pour stocker plusieurs attestations
- API d'agrégation pour fonds qui veulent vérifier en batch
- Watermark visuel anti-altération sur le PDF (overlay diagonal)
- Notarization formelle par un tiers de confiance

## Exigences techniques

### Backend

- Migration Alembic `025_create_attestations.py` :
  - Table `attestations`
  - Index : `attestations(account_id, valid_until)`, `attestations(revoked_at)`
- Modèle `app/models/attestation.py`
- Service `app/modules/attestations/service.py` (génération, révocation, vérification)
- Service `app/modules/attestations/signing.py` (chargement clé Ed25519, sign/verify)
- Service `app/modules/attestations/qr.py` (génération QR via segno)
- Routers :
  - `app/modules/attestations/router.py` (PME, auth)
  - `app/api/public.py` ou `app/modules/attestations/public_router.py` (no-auth, monté à `/api/public/*`)
- Modification `app/main.py` : monter le public router AVANT le middleware d'auth
- Refactor template `app/modules/attestations/templates/attestation_template.html`
- Configuration `core/config.py` :
  - `ATTESTATION_PRIVATE_KEY_PEM: str` (env var, secret)
  - `ATTESTATION_PUBLIC_KEY_ID: str = "v1"` (versionné)
  - `ATTESTATION_VALIDITY_DAYS: int = 365`
- Génération de la clé Ed25519 (one-shot bootstrap) : script `scripts/generate_attestation_keypair.py` qui génère et imprime, à stocker dans le secret manager.
- Tool `credit_tools.generate_credit_certificate` : appel réel au service
- Mise à jour tool selector pour exposer `revoke_attestation` sur `/credit-score`, `/attestations`
- Tests :
  - Test génération : Attestation row créée avec PDF + signature + QR valides
  - Test signature : signature Ed25519 vérifiable avec la public key
  - Test PDF hash : SHA-256 du fichier match `pdf_hash_sha256` stocké
  - Test QR : décoder le QR donne bien `https://esg-mefali.com/verify/{id}`
  - Test public verify : endpoint sans auth retourne 200 et metadata
  - Test révocation : après revoke, public verify retourne `status='revoked'`
  - Test expiration : after `valid_until`, public verify retourne `status='expired'`
  - Test invalid ID : 200 avec `status='invalid'`, pas de leak (pas 404 qui révèle existence)
  - Test signature alteration : si on altère le payload après coup, vérification échoue

### Frontend

- Layout `layouts/public.vue` (réutilisable F09 pour `/legal/privacy`)
- Page `pages/verify/[id].vue` (no-auth)
- Page `pages/attestations/index.vue` (PME, liste)
- Page admin `pages/admin/attestations/index.vue` (F09)
- Modifier middleware `auth.global.ts` pour autoriser `/verify/[id]`, `/legal/*`
- Composants `components/attestations/AttestationCard.vue`, `RevokeAttestationModal.vue`
- Composable `composables/useAttestations.ts`
- Mise à jour `pages/credit-score/index.vue` : bouton "Générer attestation" appelle réellement le service, affiche le verification_url, copie en presse-papier
- Dark mode
- Page publique : design soigné, mobile-first (le fund officer scanne avec son téléphone)
- I18n FR/EN sur la page publique (un fund officer GCF peut être anglophone)

### Base de données

- Table : `attestations`
- Indexes spécifiés
- Audit log via F03 : génération + révocation
- (post-MVP) : table `attestation_keys` pour rotation des clés

## Critères d'acceptation

- [ ] Modèle `Attestation` créé avec tous les champs spécifiés
- [ ] Clé Ed25519 générée et stockée en secret env
- [ ] Génération PDF : signature détachée + QR code + hash SHA-256 corrects
- [ ] Endpoint `GET /api/public/verify/{id}` accessible sans auth
- [ ] Page `/verify/[id]` accessible sans auth, affiche les 4 statuts (authentic/revoked/expired/invalid)
- [ ] Layout `public.vue` réutilisable
- [ ] Tool LLM `generate_credit_certificate` génère réellement (plus de placeholder)
- [ ] Révocation par PME et par admin fonctionnelle
- [ ] Test E2E : générer attestation → télécharger PDF → ouvrir QR avec phone → page publique affiche "AUTHENTIQUE"
- [ ] Test E2E : altérer le PDF avec un éditeur → hash ne matche plus → message "vérifiez avec l'attestation originale"
- [ ] Test E2E : révoquer → recharger page publique → "RÉVOQUÉE"
- [ ] Test E2E : modifier la date système à `valid_until + 1` → "EXPIRÉE"
- [ ] Test E2E : tenter `/verify/invalid-uuid` → "INVALIDE"
- [ ] Couverture tests ≥ 85 % sur signing, qr, service
- [ ] Documentation `docs/attestations-and-verification.md` : how it works, how to verify offline, format de la signature
- [ ] La page publique est responsive mobile (le fund officer scanne avec un téléphone)

## Risques & garde-fous

- **Risque** : la clé privée Ed25519 fuit. **Garde-fou** : stockage secret manager (pas dans le repo, pas dans `.env` checké en git), rotation post-MVP avec versioning de la `public_key_id`. Documentation procédure de rotation.
- **Risque** : un attaquant tente d'énumérer les attestation_ids via `/api/public/verify/{guess}`. **Garde-fou** : UUID v4 (entropie suffisante), rate limiting strict (10 req/IP/min), pas de leak entre `invalid` (UUID inexistant) et `revoked`/`expired` (UUID valide mais autre statut) en termes de timing.
- **Risque** : le PDF peut être altéré et le hash invalidé sans que la PME s'en aperçoive. **Garde-fou** : le PDF lui-même contient le hash en pied de page → la PME peut comparer le hash visible avec celui sur la page publique. Documentation utilisateur.
- **Risque** : le QR code mène vers un domaine compromis. **Garde-fou** : `verification_url` codé en dur via env var au moment de la génération (pas extractible depuis l'URL utilisateur), HTTPS strict, HSTS preload.
- **Risque** : performance de génération (PDF + signature + QR) = ~3-5 sec. **Garde-fou** : génération asynchrone si > 2 sec (Celery post-MVP, pour MVP : background task FastAPI), notification quand prêt.
- **Risque** : un user PME malveillant tente de générer une attestation falsifiée en altérant la requête API. **Garde-fou** : la signature côté backend est faite serveur-side avec la clé privée jamais exposée — impossible côté client. La PME ne peut pas modifier le payload signed.
- **Risque** : une attestation révoquée pour fraude reste sur le PDF déjà transmis et le fund officer ne sait pas qu'elle est révoquée s'il ne scanne pas le QR. **Garde-fou** : encourager dans la documentation et le PDF "scanner systématiquement le QR pour vérifier", éducation des partenaires fonds.
