# F24 — Extension Chrome MV3 Complète (Module 8)

**Module(s) source(s)** : Module 8 (Extension Chrome — 7 sous-modules)
**Priorité** : P2 — différenciateur produit, mais après les fondations
**Dépendances** : F02 (multi-tenant + auth bearer), F06 (Project), F07 (Offer + url_patterns), F08 (attestation), F09 (admin saisit url_patterns), F10 (widgets)
**Estimation** : 5-6 sprints (greenfield 100 %)

## Contexte & motivation

Module 8 du brainstorming (7 sous-modules) :
- 8.1 Détection automatique sites fonds + intermédiaires
- 8.2 Pré-remplissage intelligent des formulaires
- 8.3 Panneau latéral de guidage
- 8.4 Suivi des candidatures (= couple Projet+Offre)
- 8.5 Notifications et rappels
- 8.6 Recommandations d'offres
- 8.7 Multilingue FR/EN

**État actuel** : **0 % implémenté**. Aucun fichier d'extension dans le projet (`find` exhaustif négatif). Aucune spec dédiée dans `/specs/`. Le doc deferred-work.md confirme l'extension repoussée.

**Prérequis backend non remplis** :
1. Entité `Offer` (F07) — couple Fonds × Intermédiaire (URL patterns par fonds ET par intermédiaire)
2. `intermediary.required_documents` (F07)
3. `funds.url_patterns` et `intermediaries.url_patterns` (F07 enrichi)
4. Tool LangChain `update_candidature_status` (F10/F15)
5. Endpoints REST `/api/extension/*`
6. CORS pour `chrome-extension://`
7. Multi-référentiels ESG (F13) pour scoring décomposé

**Conséquence** : F24 ne peut commencer qu'après que F07, F13, F10, F15 soient livrées.

## User stories

- **PME naviguant sur boad.org** : « L'extension détecte que je suis sur le portail SUNREF Ecobank et m'affiche un bandeau "Offre détectée — voulez-vous candidater pour votre projet panneaux solaires ?" »
- **PME** : « Quand je clique sur le formulaire SUNREF, l'extension pré-remplit mes champs (nom entreprise, secteur, montant, etc.) avec un code couleur : vert (auto-rempli), bleu (suggéré IA), orange (à remplir manuellement). »
- **PME** : « Le panneau latéral m'affiche un guide pas-à-pas spécifique à l'Offre : checklist documentaire, ton recommandé, points d'attention. »
- **PME** : « Mes candidatures suivent leur cycle de vie dans la popup : statut, prochaine action, documents manquants. »

## Périmètre fonctionnel

### Phase A — Pré-requis backend (1 sprint)

#### A.1 — Enrichir `Fund` et `Intermediary` avec `url_patterns`

Ajouter colonne `url_patterns: jsonb` (liste de regex) sur `funds` et `intermediaries` (lien F07).

```json
[
  {"pattern": "^https://www\\.boad\\.org/.+", "scope": "homepage"},
  {"pattern": "^https://sunref\\.boad\\.org/.+", "scope": "submission_portal"}
]
```

Page admin (F09) `pages/admin/funds/[id]/url-patterns.vue` pour saisir.

#### A.2 — Tool LangChain `update_candidature_status`

Manquait F10 — créer dans `application_tools.py` :

```python
@tool(args_schema=UpdateApplicationStatusArgs)
@with_retry(max_retries=1, ...)
async def update_application_status(application_id: UUID, new_status: ApplicationStatusEnum, step_at_intermediary: str | None, notes: str | None):
    ...
```

Enum `ApplicationStatusEnum` strict : `draft|preparing|submitted_to_intermediary|under_review_intermediary|submitted_to_fund|under_review_fund|approved|rejected|disbursed|cancelled`.

#### A.3 — API REST `/api/extension/v1/*`

Sous-routeur dédié `app/modules/extension/router.py` :
- `GET /api/extension/v1/me/profile-snapshot` (profil entreprise + projets allégé pour pré-remplissage)
- `POST /api/extension/v1/detect` (URL → offer_id, fund, intermediary, confidence)
- `POST /api/extension/v1/applications/auto-create` (idempotent par `(account_id, offer_id, project_id)`)
- `GET /api/extension/v1/applications/active`
- `POST /api/extension/v1/suggestions/field` (input : nom champ + contexte HTML serializé minimal → output : suggestion IA)
- `GET /api/extension/v1/recommendations/offers` (multi-référentiels via F13)

#### A.4 — CORS pour extension

`app/main.py` ajouter `chrome-extension://*` dans `CORSMiddleware.allow_origin_regex`.

#### A.5 — Auth Bearer dédié extension

- Endpoint `POST /api/extension/v1/auth/exchange` : transforme un JWT user en token long-lived dédié extension (scope limité)
- Stocké côté extension dans `chrome.storage.session`

### Phase B — Squelette extension MV3 (1 sprint)

Structure :
```
extension/
├── manifest.json (Manifest V3, permissions: storage, alarms, sidePanel, notifications, activeTab, scripting, host_permissions)
├── _locales/{fr,en}/messages.json
├── src/
│   ├── background/service_worker.ts (chrome.alarms 6h, dedup, fetch)
│   ├── content/
│   │   ├── detector.ts (MutationObserver + matcher url_patterns)
│   │   ├── form_filler.ts (séquentiel + code couleur)
│   │   └── overlay.ts (bandeau "Offre détectée")
│   ├── sidepanel/
│   │   ├── index.html
│   │   └── App.vue (Vue 3 + Pinia, panneau guide)
│   ├── popup/
│   │   ├── index.html
│   │   └── Popup.vue (dashboard candidatures)
│   └── shared/
│       ├── api.ts (client REST + bearer)
│       ├── i18n.ts (wrapper chrome.i18n)
│       └── types.ts (partagés avec frontend Nuxt — symlinker ou monorepo)
├── tests/ (Vitest + @types/chrome avec fakes)
├── package.json (Vite + crxjs/vite-plugin pour HMR MV3)
└── vite.config.ts
```

Stack : Vite + `@crxjs/vite-plugin` (HMR MV3), Vue 3 + Pinia (cohérence Nuxt frontend), réutilisation max via package `@esg-mefali/shared-types`.

### Phase C — Sub-modules incrémentaux (4 sprints)

#### Sprint 1 : 8.1 Détection + 8.4 Suivi candidatures (popup)

- `detector.ts` : MutationObserver, matcher url_patterns via `/api/extension/v1/detect`
- `overlay.ts` : bandeau "Offre détectée — voulez-vous candidater ?"
- Popup `Popup.vue` : dashboard candidatures actives (fetch `/applications/active`)
- Création auto candidature : `auto-create` endpoint au consentement user

#### Sprint 2 : 8.2 Pré-remplissage

- `form_filler.ts` :
  - Détection types de champs (input, select, textarea) par labels HTML
  - Mapping vers `profile-snapshot` fields
  - Code couleur via attribut `data-fill-source` injecté
  - Animation séquentielle "Tout remplir"
  - Pour champs ambigus : appel `/suggestions/field` avec contexte HTML

#### Sprint 3 : 8.3 Panneau latéral + 8.5 Notifications

- `sidepanel/App.vue` : panneau de guidage pas-à-pas spécifique à l'offre détectée
- Mini-chat IA : iframe pointant vers `pages/chat?embed=1`
- `chrome.alarms` toutes les 6h pour vérifier deadlines
- `chrome.notifications` pour J-30/J-7/J-1
- Déduplication via `chrome.storage` (clé : `notification_{reminder_id}`)

#### Sprint 4 : 8.6 Recommandations + 8.7 Multilingue EN complet

- Recommendations : appelle `/recommendations/offers` (utilise multi-référentiels F13)
- Comparaison côte-à-côte d'offres concurrentes
- I18n complet via `_locales/{fr,en}/messages.json` + `chrome.i18n.getMessage`

## Hors-scope (post-MVP)

- Email parsing OAuth Gmail/Outlook pour update auto statut candidature
- Navigateurs autres que Chrome (Firefox, Edge, Safari)
- Mode offline avec sync différée (Service Worker IndexedDB)
- Auto-soumission de formulaires (juste pré-remplir)
- Plugin équivalent en mobile (Android/iOS)
- Reconnaissance OCR de PDFs téléchargés sur les portails

## Exigences techniques

### Backend (Phase A)

- Migration Alembic `036_extension_url_patterns.py`
- Module `app/modules/extension/`
- Tool `update_application_status` dans `application_tools.py`
- CORS update
- Auth bearer extension
- Tests : E2E API extension

### Extension (Phase B + C)

- Repo séparé `extension/` à la racine
- Stack : Manifest V3, Vue 3, Pinia, Vite, @crxjs/vite-plugin
- Tests Vitest avec fakes `chrome.*`
- Tests Playwright en mode `--load-extension` sur fixtures HTML BOAD/GCF/SUNREF/NIE
- CI dédié `extension-ci.yml` (lint + test + build + zip Chrome Web Store)

### Backend `/api/extension/v1/*`

- 6 endpoints décrits Phase A.3
- CORS configuré

### Sécurité

- Manifest CSP strict (pas de `eval`)
- Sanitisation des données injectées par sites détectés (anti-XSS contre l'extension)
- Bearer token en `chrome.storage.session` (pas `local`)
- Rotation token côté backend

## Critères d'acceptation

- [ ] Phase A : 6 endpoints `/api/extension/v1/*` fonctionnels
- [ ] Phase A : tool `update_application_status` créé
- [ ] Phase A : CORS extension configuré
- [ ] Phase B : extension MV3 chargeable dans Chrome dev mode
- [ ] Sprint 1 : détection automatique fonctionne sur 5 sites prioritaires (BOAD, GCF, SUNREF Ecobank, PNUD, AFD)
- [ ] Sprint 1 : popup affiche dashboard candidatures
- [ ] Sprint 2 : pré-remplissage fonctionne avec code couleur
- [ ] Sprint 3 : panneau latéral guide pas-à-pas
- [ ] Sprint 3 : notifications J-30/J-7/J-1 fonctionnelles avec dédup
- [ ] Sprint 4 : recommendations multi-référentiels affichées
- [ ] Sprint 4 : extension i18n FR + EN complète
- [ ] Tests E2E Playwright `--load-extension` sur 5 sites prioritaires
- [ ] Soumission Chrome Web Store réussie (review approved)

## Risques & garde-fous

- **Risque** : url_patterns non saisis → extension inutilisable. **Garde-fou** : seed initial admin de 10+ patterns prioritaires, processus continu de catalogage.
- **Risque** : CSP des sites cibles bloquent l'overlay. **Garde-fou** : audit site par site, fallback `chrome.sidePanel` (hors-page).
- **Risque** : `update_candidature_status` LLM hallucinations. **Garde-fou** : enum strict côté tool + rejet si valeur hors enum.
- **Risque** : Manifest V3 service worker éphémère, état perdu. **Garde-fou** : design impératif autour de `chrome.storage`, `chrome.alarms` pour la persistence.
- **Risque** : utilisateur installe l'extension sans avoir un compte ESG Mefali. **Garde-fou** : popup affiche écran "Connectez-vous d'abord" avec lien vers app.
- **Risque** : faux positifs détection (URL similaire mais pas la bonne offre). **Garde-fou** : confidence threshold sur matcher, demande confirmation user via `ask_yes_no`-like dans overlay.
