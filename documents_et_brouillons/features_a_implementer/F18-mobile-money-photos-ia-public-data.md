# F18 — Mobile Money + Photos IA + Données Publiques (avec Consentements)

**Module(s) source(s)** : Module 5.1 (Collecte de Données Non-Conventionnelles)
**Priorité** : P1 — innovation 3 (scoring crédit vert inclusif)
**Dépendances** : F01 (sources), F02 (multi-tenant), F05 (consentements granulaires)
**Estimation** : 3 sprints

## Contexte & motivation

Module 5.1 : 3 collectes critiques nécessitant **consentement granulaire explicite (Module 0.3)** :
1. **Mobile Money** : flux, régularité, volume
2. **Photos exploitation** analysées par IA
3. **Données publiques** : réseaux sociaux, avis, programmes verts

**État actuel** :
- `CreditCategory` enum (`backend/app/models/credit.py:29-33`) ne contient que `solvability` et `green_impact`
- **Aucun pipeline Mobile Money** : pas d'upload, pas de parser, pas de catégorie, pas d'analyse
- **Aucun pipeline photos IA** : pas d'upload contextualisé, pas d'appel Claude Vision
- **Aucune intégration données publiques** (réseaux sociaux, avis Google, etc.)
- **Aucune table `user_consents`** ni mécanisme de consentement (couvert par F05)

**Conséquences** :
- Impossible d'inclure les données alternatives → score crédit pauvre
- Promesse "scoring crédit vert inclusif" non tenue
- Différenciateur produit absent

## User stories

- **PME informelle** (sans comptabilité formelle) : « Je veux uploader mon historique Mobile Money (Wave, Orange Money) en CSV pour qu'il alimente mon scoring crédit. »
- **PME** : « Avant que la plateforme analyse mes photos d'exploitation par IA, je dois donner mon consentement explicite. Je peux le révoquer à tout moment. »
- **PME** : « L'analyse IA de mes photos d'exploitation regarde : qualité matériel, organisation, hygiène — et alimente mon score impact vert. »
- **Architecte** : « Aucune collecte ne démarre sans consentement actif vérifié au runtime. »

## Périmètre fonctionnel

### Mobile Money

#### Upload manuel CSV

- Endpoint `POST /api/credit/mobile-money/upload` accepte CSV/Excel exporté depuis Wave / Orange Money / MTN MoMo / Moov Money
- Parser robuste (formats connus) : extrait `{date, type: 'incoming'/'outgoing', amount, counterparty, balance}`
- Stocke en table `mobile_money_transactions` (timestamps, amount Money typed F04, counterparty hashé pour confidentialité)

#### Analyse

`backend/app/modules/credit/mobile_money_analyzer.py` :
- **Volume mensuel** : moyenne, écart-type
- **Régularité** : ratio jours avec transactions sur 30j
- **Solde moyen** : approximation cash flow
- **Croissance** : tendance sur 12 mois
- **Top counterparties** : (anonymisé) — détection clients récurrents

Alimente `CreditCategory.mobile_money_flux` (nouveau).

#### Garde-fou consent

```python
async def analyze_mobile_money(account_id, user_id, ...):
    consent = await get_active_consent(account_id, "mobile_money_analysis")
    if not consent:
        raise HTTPException(403, "Consentement Mobile Money requis")
    ...
```

Lié à F05 consents.

### Photos IA

#### Upload

- Endpoint `POST /api/credit/photos/upload` accepte JPG/PNG max 5 MB par photo, max 10 photos
- Stockage dans `/uploads/{account_id}/credit/photos/`
- Schéma table `credit_photos` : id, account_id, file_path, captured_at, analyzed_at, analysis_result (jsonb)

#### Analyse via Claude Vision (OpenRouter)

```python
async def analyze_photo(photo_id):
    photo = await get_photo(photo_id)
    image_url = await get_signed_url(photo.file_path)
    
    prompt = """
    Analyse cette photo d'une PME africaine. Évalue sur ces dimensions (chacune /10) :
    - État du matériel (rouille, usure)
    - Organisation des espaces (rangement, propreté)
    - Hygiène/sécurité (équipements de protection, signalétique)
    - Pratiques environnementales visibles (tri, énergies renouvelables, gestion eau)
    - Activité observée (productivité visible)
    
    Retourne un JSON {scores, observations, red_flags, green_signals}.
    """
    
    result = await openrouter_vision(prompt, image_url)
    photo.analysis_result = result
```

Alimente `CreditCategory.photos_ia` (nouveau).

#### Garde-fou consent

Identique Mobile Money via F05.

### Données publiques

#### Sources publiques pertinentes

- Réseaux sociaux : Facebook business page, Google My Business
- Avis publics : Google Reviews, Trustpilot (si applicable)
- Programmes verts : participation à des programmes labellisés (PNUE, ADEME, GRI Sustainability)

#### Pipeline

- L'utilisateur fournit les URLs de ses pages publiques (consentement)
- Cron de scrape périodique (1x/mois) : avis, notes, posts
- Analyse sentiment / signaux verts via LLM
- Alimente `CreditCategory.public_data` (nouveau)

**Limitations MVP** :
- Pas de scraping automatique trop avancé (TOS Facebook/Google)
- Mode déclaratif : l'utilisateur saisit ses notes / nombres d'avis manuellement
- Validation par capture d'écran uploadée si le user veut booster son score

#### Garde-fou consent

Identique via F05.

### Méthodologie publiée et sourcée (Module 5.2)

Endpoint `GET /api/credit/methodology` retourne :
```json
{
  "version": "1.2",
  "factors": [
    {
      "name": "Mobile Money - Régularité",
      "weight": 0.15,
      "category": "solvability",
      "description": "...",
      "source_id": "uuid-source-bcao-mobile-money-study"
    },
    ...
  ]
}
```

Page publique (no-auth) `/legal/methodology-credit.vue` qui affiche cette méthodologie.

### Mise à jour scoring crédit

`compute_combined_score` (`backend/app/modules/credit/service.py:127-135`) accepte les 3 nouvelles catégories :

```python
combined = (
    solvability * w_solv +
    green_impact * w_green +
    mobile_money_flux * w_mm +  # nouveau
    photos_ia * w_photos +  # nouveau
    public_data * w_public  # nouveau
) * confidence_factor
```

Pondérations dynamiques selon disponibilité des données (si pas de Mobile Money consent → poids redistribué).

### UI Frontend

Page `pages/credit-score/index.vue` (refactor) :
- Sections par catégorie (existant + 3 nouvelles)
- Boutons "Connecter Mobile Money", "Uploader photos", "Saisir données publiques"
- Chacun ouvre un modal avec :
  - Texte de consentement explicite (lien F05)
  - CTA "J'accepte et je continue" / "Refuser"
  - Si déjà consenti : interface d'upload/saisie
  - Bouton "Révoquer mon consentement"

## Hors-scope (post-MVP)

- Connexion Open Banking via API (Wave / Orange API)
- Scraping automatique avancé Facebook/Google (TOS issues)
- Reconnaissance faciale ou détection personnes dans photos (privacy)
- Geolocalisation EXIF (privacy)
- Vidéos
- Audio interviews

## Exigences techniques

### Backend

- Migration Alembic `032_alternative_credit_data.py` :
  - Étendre enum `CreditCategory` : ajouter `mobile_money_flux`, `photos_ia`, `public_data`
  - Tables `mobile_money_transactions`, `credit_photos`, `public_data_sources`
- Modules :
  - `app/modules/credit/mobile_money_parser.py` (CSV parsers Wave/OM/MTN/Moov)
  - `app/modules/credit/mobile_money_analyzer.py`
  - `app/modules/credit/photo_analyzer.py` (Claude Vision via OpenRouter)
  - `app/modules/credit/public_data_collector.py`
- Endpoints :
  - `POST /api/credit/mobile-money/upload` (avec consent check)
  - `GET /api/credit/mobile-money/analysis`
  - `POST /api/credit/photos/upload` (avec consent check)
  - `GET /api/credit/photos`
  - `POST /api/credit/photos/{id}/analyze`
  - `POST /api/credit/public-data/declare`
  - `GET /api/credit/methodology` (public)
- Refactor `compute_combined_score` avec pondérations dynamiques
- Helper `app/core/consent.py:require_consent` (F05) intégré
- Tests :
  - Test parser CSV : 4 formats Mobile Money supportés
  - Test consent gating : sans consent → 403
  - Test photo analyzer : analyse Claude Vision retourne scores cohérents
  - Test scoring : ajout Mobile Money modifie le score combiné

### Frontend

- Refactor `pages/credit-score/index.vue` avec 3 nouvelles sections
- Composants `components/credit/MobileMoneyUpload.vue`, `PhotoUpload.vue`, `PublicDataForm.vue`
- Composant `<ConsentRequestModal>` réutilisable (lien F05)
- Page `pages/legal/methodology-credit.vue` (no-auth)
- Composable `useCreditAlternativeData.ts`
- Dark mode

### Base de données

- Tables : `mobile_money_transactions`, `credit_photos`, `public_data_sources`
- Stockage local `/uploads/{account_id}/credit/photos/`
- Index : `mobile_money_transactions(account_id, transaction_date DESC)`
- RLS F02

## Critères d'acceptation

- [ ] Enum `CreditCategory` étendu (mobile_money_flux, photos_ia, public_data)
- [ ] Upload CSV Mobile Money fonctionnel pour 4 fournisseurs (Wave, OM, MTN, Moov)
- [ ] Analyse Mobile Money produit 5+ KPIs (volume, régularité, etc.)
- [ ] Upload photos avec analyse Claude Vision opérationnelle
- [ ] Pipeline données publiques (déclaratif) fonctionnel
- [ ] Consentement granulaire vérifié à chaque collecte (F05)
- [ ] Méthodologie publique exposée à `/api/credit/methodology` + page Vue
- [ ] Scoring combiné prend en compte les 3 nouvelles catégories avec pondérations dynamiques
- [ ] Test E2E : upload Mobile Money sans consent → 403 ; donner consent → upload → KPIs visibles
- [ ] Test E2E : upload photo → analyse Claude Vision → scores affichés
- [ ] Couverture tests ≥ 80 %

## Risques & garde-fous

- **Risque** : RGPD sur les photos (visages, données personnelles). **Garde-fou** : flou auto des visages détectés (post-MVP), instructions claires "ne photographiez pas de personnes", consentement explicite obligatoire.
- **Risque** : coût Claude Vision sur 10 photos × 1000 PME × 12 mois. **Garde-fou** : analyse 1x par photo (idempotent), cache résultats, limite 10 photos / PME.
- **Risque** : faux signaux dans données publiques (avis truqués). **Garde-fou** : pondération limitée (≤ 10 % du score combiné), badge "données déclaratives non vérifiées".
- **Risque** : un user uploade un CSV malveillant. **Garde-fou** : validation stricte du schéma, taille max 5 MB, ligne par ligne avec rejection des lignes invalides.
- **Risque** : Mobile Money révèle indirectement la position bancaire complète (privacy). **Garde-fou** : counterparty hashée, pas de noms en clair stockés, droit d'effacement F05.
