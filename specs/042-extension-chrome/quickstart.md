# Quickstart — Extension Chrome ESG Mefali (F24 MVP)

## Pré-requis

- **Node.js** ≥ 20
- **pnpm** (ou npm) — utiliser le même que `frontend/` Nuxt
- **Chrome** ≥ 120 (Manifest V3 requis)
- Backend dev tournant sur `http://localhost:8000`
- Compte PME de test inséré en base (cf. `scripts/seed_dev_users.py`)

## Installation

```bash
cd extension
pnpm install
```

## Build & chargement dev mode

```bash
# Build watch + HMR
pnpm dev
# Génère extension/dist/
```

Puis dans Chrome :

1. Ouvrir `chrome://extensions`
2. Activer le mode développeur (toggle en haut à droite)
3. Cliquer « Charger l'extension non empaquetée »
4. Sélectionner le dossier `extension/dist/`
5. Épingler l'extension dans la barre d'outils

## Vérification des 4 user stories

### US1 — Authentification

1. Cliquer sur l'icône extension → popup s'ouvre
2. Vérifier l'écran « Connectez-vous d'abord »
3. Saisir email + mot de passe d'un compte PME → Connexion
4. Vérifier l'écran connecté avec nom + rôle PME

### US2 — Détection offre

1. Avec utilisateur connecté
2. Naviguer sur `https://sunref.boad.org/`
3. Vérifier qu'un bandeau « Offre détectée — SUNREF Ecobank » apparaît dans les 2 secondes
4. Cliquer « Voir dans ESG Mefali » → ouvre `/financing/offers/<id>` dans nouvel onglet
5. Naviguer sur `https://example.com/` (URL non cataloguée) → vérifier qu'aucun bandeau n'apparaît

### US3 — Dashboard candidatures

1. Avec utilisateur connecté ayant ≥ 2 candidatures actives
2. Ouvrir popup → vérifier liste des candidatures
3. Vérifier que les libellés de statuts sont en français
4. Cliquer sur une candidature → ouvre fiche dans nouvel onglet

### US4 — Onboarding non authentifié

1. Profil Chrome neuf ou bouton « Se déconnecter »
2. Ouvrir popup → écran « Connectez-vous d'abord »
3. Cliquer « Pas encore de compte ? » → ouvre page inscription web

## Tests automatisés

```bash
# Tests unitaires extension
cd extension
pnpm test

# Tests backend module extension
cd backend && source venv/bin/activate
pytest tests/modules/test_extension/ -v --cov=app/modules/extension --cov-report=term-missing
```

## Build production

```bash
cd extension
pnpm build
# Génère extension/dist/ optimisé (minified, sourcemaps)

# Optionnel : zip pour distribution manuelle
cd dist && zip -r ../esg-mefali-extension.zip .
```

**Note** : la soumission Chrome Web Store est hors-scope MVP.

## Dépannage

- **CORS erreur dans console extension** : vérifier que `chrome-extension://*` est bien dans `allow_origin_regex` du backend (`app/main.py`).
- **Token 401 immédiat** : vérifier la migration 042 appliquée (`alembic current` doit afficher `042_extension_url_patterns`).
- **Bandeau ne s'affiche pas** : vérifier (1) utilisateur connecté, (2) URL matche un pattern seedé, (3) cache local `chrome.storage.local` vidé (DevTools → Application → Storage).
- **HMR cassé** : redémarrer `pnpm dev` et recharger l'extension dans `chrome://extensions`.
