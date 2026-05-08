# Research — Extension Chrome MV3 (F24 MVP P1)

**Date** : 2026-05-08
**Branche** : feat/F24-extension-chrome (042)

## R1 — @crxjs/vite-plugin

**Decision** : utiliser `@crxjs/vite-plugin` v2.x stable.
**Rationale** : maintenu par CRXJS, support officiel Manifest V3, HMR sur service worker + content scripts + popup, intégration Vite native, Vue 3 SFC compatible via `@vitejs/plugin-vue`. C'est le standard de facto MV3 + Vite.
**Alternatives** :
- esbuild manuel : moins de DX, pas de HMR.
- webpack 5 + crx-webpack : plus complexe, moins maintenu.
- Plasmo : framework opinionné, ajoute couche d'abstraction inutile pour MVP.

## R2 — Manifest V3 CSP

**Decision** : ne pas définir de CSP custom dans le manifest (utiliser celle par défaut MV3 : `script-src 'self'; object-src 'self';`).
**Rationale** : la CSP MV3 par défaut interdit déjà `eval` et le code distant, ce qui satisfait FR-024. L'overlay injecté dans la page hôte hérite de la CSP de cette page (les content scripts ne sont pas soumis à la CSP de la page elle-même mais ne peuvent pas charger de ressources externes pour leur propre besoin).
**Alternatives** : CSP plus stricte explicite (`'sandbox'`) — non justifié en MVP.

## R3 — Auth bearer long-lived dédié extension

**Decision** : ajouter colonne `scope VARCHAR(20) DEFAULT 'web' NOT NULL CHECK (scope IN ('web','extension'))` sur `refresh_tokens` F02. Endpoint `/auth/exchange` génère un couple access (TTL 24 h) + refresh (TTL 30 j) avec `scope='extension'`. Réutilisation totale de l'infra rotation refresh F02.
**Rationale** : pas de nouvelle table, pas de duplication de code crypto, scope distinct permet révocation ciblée future (logout extension sans logout web).
**Alternatives** :
- Nouvelle table `extension_sessions` : doublon F02, complexité inutile.
- Token API key statique : viole rotation F02, rejet sécurité.

## R4 — CORS `chrome-extension://`

**Decision** : ajouter `chrome-extension://.*` à `allow_origin_regex` dans `app/main.py` `CORSMiddleware`. Conserver origines existantes (localhost dev, frontend prod).
**Rationale** : pattern regex le plus simple, FastAPI/Starlette le supporte nativement via `allow_origin_regex`. Le preflight OPTIONS est géré automatiquement.
**Alternatives** :
- `allow_origins=["*"]` : trop permissif, rejet sécurité.
- Whitelist d'extension IDs spécifiques : impossible avant publication Chrome Web Store.

## R5 — chrome.storage.session vs local

**Decision** :
- `chrome.storage.session` pour le bearer token (éphémère, vidé à fermeture Chrome) — FR-003.
- `chrome.storage.local` pour le cache LRU détection (persistant, borné 200 entrées TTL 1 h) — FR-008.
**Rationale** : `session` n'est pas persisté sur disque, ce qui réduit surface d'attaque pour le token sensible. Le cache détection est non-sensible (mappe URL → offer_id public) et bénéficie de la persistance pour éviter de reinterroger l'API au prochain démarrage Chrome.
**Alternatives** : tout en `local` (rejeté pour sécurité token), tout en mémoire service worker (rejeté car SW éphémère MV3).

## R6 — Audit log `source_of_change='extension'`

**Decision** : ajouter middleware FastAPI `ExtensionAuditContextMiddleware` monté sur `/api/extension/v1/*` qui set le ContextVar `current_source_of_change` à `'extension'` (pattern identique à `AdminAuditContextMiddleware` F03). Ajouter valeur `'extension'` à l'enum PostgreSQL `audit_source` via migration 042.
**Rationale** : cohérence architecturale F03, pas de modification du listener `before_flush`.
**Alternatives** : `source_of_change` paramétré explicitement par endpoint — rejeté (violation DRY, risque oubli).

## R7 — LRU TTL TypeScript ≤ 50 LOC

**Decision** : implémentation maison `LRUCache<K, V>` basée sur `Map` (préserve l'ordre d'insertion JavaScript) avec :
- `set(key, value)` : delete + set pour mettre à jour l'ordre
- éviction si `size > 200` : `delete(this.keys().next().value)`
- TTL via timestamp stocké : `{value, expires_at}`, vérifié à `get()`
~ 30 LOC, pas de dépendance externe (lru-cache npm = ~12 KB minified, justification YAGNI).
**Rationale** : ultra-léger, testable, zero-dep.
**Alternatives** : `lru-cache` npm (rejeté YAGNI), `WeakMap` (rejeté car pas d'éviction par taille).

## R8 — Tests Playwright `--load-extension`

**Decision** : doc setup uniquement en MVP dans `docs/extension-chrome.md`. Pas d'exécution CI auto.
**Rationale** : `chromium.launchPersistentContext` avec `args: ['--load-extension=path']` fonctionne en local mais ajoute ~30 s par run en CI et flaky sur GitHub Actions sans display. Le coût n'est pas justifié pour 4 user stories MVP read-only. Validation manuelle par développeur sur les 5 sites prioritaires (SC-009).
**Alternatives** : auto-run en CI avec `xvfb-run` (rejeté MVP), Cypress (rejeté car pas de support natif extension).

## R9 — i18n Chrome native

**Decision** : utiliser `chrome.i18n.getMessage(key)` avec `_locales/fr/messages.json` uniquement en MVP. Wrapper TypeScript `t(key, fallback)` qui renvoie le fallback FR si la clé n'existe pas (sécurise dev).
**Rationale** : standard MV3, supporté nativement, zero-dep, structure prête pour ajouter `_locales/en/` post-MVP.
**Alternatives** : vue-i18n (rejeté car taille bundle + duplication avec API native), strings hardcodées (rejeté car violation FR-028).

## R10 — Sanitisation overlay

**Decision** : pas d'usage de `innerHTML` ; construire les éléments DOM via `document.createElement` + `textContent`. Aucun HTML provenant de l'API n'est rendu en tant que markup.
**Rationale** : zero-dep, défense en profondeur, satisfait FR-025.
**Alternatives** : DOMPurify (rejeté YAGNI car aucune source HTML attendue), template literals + escape (rejeté plus error-prone).
