# Extension Chrome MV3 — F24 (MVP P1)

Extension Chrome Manifest V3 minimale d'ESG Mefali. Trois fonctions
principales pour le MVP :

1. Authentification PME via échange identifiants → tokens scope=`extension`.
2. Détection automatique : un bandeau « Offre détectée » apparaît lorsqu'on
   visite un site dont une offre publiée matche un `url_pattern`.
3. Popup dashboard : liste read-only des candidatures actives avec
   deep-link vers l'application principale.

## Architecture

```
extension/
├── manifest.json              # MV3
├── _locales/fr/messages.json  # i18n FR uniquement (MVP)
├── public/icons/              # 16/48/128 px
├── src/
│   ├── background/service_worker.ts  # cache LRU + handler DETECT_URL
│   ├── content/
│   │   ├── detector.ts        # message DETECT_URL au SW au load + popstate
│   │   └── overlay.ts         # bandeau ARIA injecté via createElement
│   ├── popup/
│   │   ├── index.html
│   │   ├── App.vue            # switch login / dashboard
│   │   └── components/{LoginForm,ApplicationsList,EmptyState}.vue
│   ├── stores/{auth,applications}.ts   # Pinia
│   └── shared/{api,types,lru,i18n}.ts
└── tests/                     # Vitest jsdom + fakes chrome.*
```

## Setup développement

```bash
cd extension
npm install
npm run build         # produit extension/dist/ (Manifest V3)
npm test              # Vitest, ≥ 80 % de couverture sur la logique métier
```

Charger l'extension :
1. Ouvrir `chrome://extensions/`.
2. Activer le mode développeur (toggle haut-droit).
3. Cliquer « Charger l'extension non empaquetée ».
4. Sélectionner `extension/dist/`.

L'icône Mefali apparaît dans la barre d'outils Chrome.

## Backend

Sous-routeur dédié `/api/extension/v1/*` :

| Méthode | Path                        | Auth        | Description                                           |
|---------|-----------------------------|-------------|-------------------------------------------------------|
| POST    | `/auth/exchange`            | public      | Échange identifiants → tokens scope=extension          |
| GET     | `/me/profile-snapshot`      | bearer      | Sector + country + 3 derniers projets actifs           |
| POST    | `/detect`                   | bearer      | Matching url → offre publiée (200 ou 204)              |
| GET     | `/applications/active`      | bearer      | Candidatures actives (max 50, tri date desc)           |

CORS : ajout regex `chrome-extension://.*` dans `allow_origin_regex` de
`app/main.py`. Middleware `ExtensionAuditContextMiddleware` positionne
`source_of_change='extension'` pour toutes les mutations issues de
`/api/extension/*` (cohérent F03).

## Détection d'URL

Logique côté serveur (`app/modules/extension/service.py::match_url`) :

1. Charger toutes les `Offer` `publication_status='published'` + `is_active=true`.
2. Pour chaque offre, concaténer `fund.url_patterns ∪ intermediary.url_patterns`.
3. Compiler chaque regex (un pattern invalide est silencieusement loggé et
   ignoré).
4. Tester contre l'URL fournie.
5. Si plusieurs offres matchent : priorité aux couples `intermediary.code='DIRECT'`,
   sinon premier par `created_at` croissant (déterministe).
6. Renvoyer `DetectResponse(confidence=1.0)` ou `None` (→ HTTP 204).

## Procédure : ajouter un `url_pattern` (MVP via SQL)

Le back-office admin F09 d'édition des `url_patterns` est différé en P2.
En MVP, on les saisit via SQL ou la migration de seed :

```sql
UPDATE funds
SET url_patterns = '[
  {"pattern": "^https://(www\\\\.)?example\\\\.org/.*", "scope": "homepage"}
]'::jsonb
WHERE name = 'Mon Fonds';
```

Validation côté serveur : chaque pattern doit être compilable (Python `re.compile`).
Un pattern invalide est ignoré au runtime (warning logué).

## Sécurité

- **Aucun secret** dans le code de l'extension.
- Token bearer stocké dans `chrome.storage.session` (éphémère, supprimé à la
  fermeture du navigateur).
- Cache de détection dans `chrome.storage.local` (TTL 1 h, max 200 entrées).
- Bandeau injecté via `document.createElement` + `textContent` uniquement —
  jamais `innerHTML` (anti-XSS strict).
- Refresh tokens marqués `scope='extension'` en BDD pour révocation ciblée
  admin si compromission.
- CORS limité à `chrome-extension://*` + origines existantes.
- Audit log F03 : toute mutation `/api/extension/*` est tracée
  `source_of_change='extension'`.

## Migration Alembic 042

`alembic/versions/042_extension_url_patterns.py` ajoute :

- `funds.url_patterns JSONB DEFAULT '[]'`
- `intermediaries.url_patterns JSONB DEFAULT '[]'`
- `refresh_tokens.scope VARCHAR(20) DEFAULT 'web' NOT NULL` + CHECK enum.
- Valeur `'extension'` à l'ENUM PostgreSQL `audit_source` (skip SQLite).
- Seed UPSERT (idempotent) ~5 patterns prioritaires (BOAD, GCF, AFD, PNUD,
  Ecobank Sunref) si les fonds/intermédiaires correspondants existent.

Round-trip `up/down/up` validé sur PostgreSQL. NB : la valeur enum
`'extension'` reste dans `audit_source` après `downgrade` (limitation
PostgreSQL native — sans impact car non utilisée).

## Smoke test manuel (procédure)

1. Backend up : `uvicorn app.main:app --reload`.
2. Créer un user PME en BDD (ou via `/api/auth/register`).
3. Ajouter un `url_pattern` sur un fonds publié (cf. SQL ci-dessus).
4. `cd extension && npm run build` puis charger `dist/` dans `chrome://extensions/`.
5. Cliquer l'icône → écran login → entrer email / mot de passe.
6. Naviguer vers une URL matchée (ex : `https://greenclimate.fund/`)
   → bandeau « Offre détectée » apparaît en haut.
7. Cliquer sur l'icône extension → la liste des candidatures actives s'affiche
   (ou message « Aucune candidature » si vide).

## Hors-scope MVP P1 (différé P2-P4)

- Pré-remplissage de formulaires sur les sites externes.
- Panneau latéral (`side_panel`).
- Notifications push.
- Multi-langue (anglais).
- Soumission Chrome Web Store.
- Recommandations multi-référentiels.
- E2E Playwright `--load-extension` automatisé en CI (procédure manuelle uniquement
  pour MVP).
- UI admin F09 d'édition des `url_patterns` (SQL/seed uniquement en MVP).

## Tests

- **Backend** : `pytest tests/modules/extension/` — 40 tests verts, couverture ≥ 85 %
  sur `app/modules/extension/`.
- **Extension** : `npm test` (Vitest jsdom) — 27 tests verts couvrant LRU, api,
  auth store, service worker, overlay.
- **E2E** : skip MVP. Procédure manuelle ci-dessus.
