# Quickstart — F11 Tools de Visualisation Typés

**Date**: 2026-05-07
**Branche**: `feat/F11-tools-visualisation-typed`

Procédure pour valider manuellement F11 après implémentation (Phase B + B').

## Pré-requis

```bash
# 1. DB up
cd /Users/mac/Documents/projets/2025/esg_mefali_v3
docker compose up postgres -d

# 2. Backend venv + migrations + seed
cd backend
source venv/bin/activate
alembic upgrade head

# 3. Frontend deps
cd ../frontend
npm install   # installera leaflet et @types/leaflet

# 4. Lancer backend + frontend
cd ../backend && source venv/bin/activate && uvicorn app.main:app --reload &
cd ../frontend && npm run dev &
```

## Scénario 1 — KPICard pour empreinte carbone

1. S'authentifier sur `http://localhost:3000` avec un compte test ayant un bilan carbone 2026 finalisé.
2. Aller sur `/dashboard` ou `/chat`.
3. Demander à l'assistant : « résume mon empreinte carbone 2026 ».
4. **Attendu** :
   - Une carte KPI inline avec :
     - Titre "Empreinte carbone 2026"
     - Valeur grande (ex: "45 tCO2e")
     - Delta colorisé (vert si baisse — `delta_is_good=true` car émissions = down is good)
     - Picto Source (cliquable) en bas-droite si une source ADEME est citée
     - Bouton drill-down "Voir le détail" → `/carbon/results`
   - Cliquer sur le picto Source → modale source affichée
   - Activer le dark mode (bouton ui store) → carte adapte ses couleurs

## Scénario 2 — MatchCards pour offres compatibles

1. S'assurer qu'au moins un projet est créé (ex: "Recyclage plastique Bouaké") et qu'au moins 3 offres sont seedées.
2. Aller sur `/financing` ou `/chat`.
3. Demander à l'assistant : « quelles offres me correspondent pour mon projet de recyclage à Bouaké ? ».
4. **Attendu** :
   - 3 cartes MatchCard empilées verticalement avec :
     - Logo fonds + intermédiaire (ou initiales placeholder si URL absente)
     - Score circulaire (ex: 78 %) avec tooltip décomposition au survol
     - Range montant + timeline en lecture directe
     - Badges instruments (ex: "subvention", "blending")
     - Compteur critères manquants
     - Bouton "Explorer"
   - Cliquer sur "Explorer" → navigation vers `/financing/offers/{offer_id}?project_id={project_id}`

## Scénario 3 — ComparisonTable pour offres concurrentes

1. S'assurer qu'au moins 3 offres GCF (BOAD, UNDP, AFD) sont seedées.
2. Aller sur `/financing` ou `/chat`.
3. Demander à l'assistant : « compare GCF via BOAD vs GCF via UNDP vs GCF via AFD ».
4. **Attendu** :
   - Une table comparative avec 3 colonnes "GCF via BOAD" / "GCF via UNDP" / "GCF via AFD" (headers cliquables → fiches offres)
   - Plusieurs lignes de critères : "Frais d'instruction" (Money), "Délai instruction" (durée lisible), "Taux de succès" (pourcentage), "Documents requis" (texte), …
   - La meilleure cellule par ligne mise en valeur (vert subtil)
   - Pictos Source cliquables sur les cellules sourcées
5. Réduire la fenêtre à < 768 px → la table se replie en cartes verticales.

## Scénario 4 — Map UEMOA

1. S'assurer qu'un projet est localisé à Bouaké (lat/lon en base) et qu'un intermédiaire BOAD est localisé à Lomé.
2. Aller sur `/profile` ou `/chat`.
3. Demander à l'assistant : « où sont mes interlocuteurs en UEMOA ? ».
4. **Attendu** :
   - Une carte Leaflet apparaît (chargement asynchrone : un placeholder s'affiche brièvement puis la carte)
   - 2 markers SVG colorés : projet (emerald) à Bouaké, intermédiaire (blue) à Lomé
   - Popup au clic sur chaque marker (label + lien)
   - Overlay GeoJSON UEMOA (frontières des 8 pays)
   - Bouton plein écran fonctionnel
5. Activer dark mode → tile layer CartoDB Dark Matter remplace OSM standard.

## Scénario 5 — Validation Pydantic stricte

1. Avec un client tier (Postman, curl ou test Python) simuler un payload tool invalide :
   - extra field non déclaré
   - enum `color` hors liste
   - `compatibility_score` > 100
2. **Attendu** :
   - Le tool LangChain rejette via `ValidationError`
   - Le validator F11 retourne un message d'erreur LLM structuré
   - Après 1 retry échoué, fallback texte
   - Aucun rendu cassé côté frontend

## Lancer les tests

```bash
# Backend
cd backend && source venv/bin/activate && \
  pytest tests/unit/test_visualization_tools_kpi.py \
         tests/unit/test_visualization_tools_match.py \
         tests/unit/test_visualization_tools_map.py \
         tests/unit/test_visualization_tools_comparison.py \
         tests/unit/test_visualization_centroids.py \
         tests/unit/test_tool_selector_visualization.py \
         tests/integration/test_visualization_prompts.py \
         -v --cov=app.graph.tools.visualization_tools \
            --cov=app.schemas.visualization \
            --cov=app.core.visualization_centroids \
            --cov-report=term-missing

# Frontend unit
cd ../frontend && npm run test -- --coverage \
  tests/unit/richblocks/KPICardBlock.spec.ts \
  tests/unit/richblocks/MatchCardBlock.spec.ts \
  tests/unit/richblocks/MapBlock.spec.ts \
  tests/unit/richblocks/ComparisonTableBlock.spec.ts \
  tests/unit/richblocks/useMapTiles.spec.ts

# E2E Playwright
cd frontend && npx playwright test tests/e2e/F11-tools-visualisation-typed.spec.ts --reporter=html
```

## Génération du GeoJSON UEMOA (asset)

À exécuter une seule fois (ou lors d'une mise à jour Natural Earth) :

```bash
# Pré-requis : npm install -g mapshaper
cd /tmp
curl -O https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/110m/cultural/ne_110m_admin_0_countries.zip
unzip ne_110m_admin_0_countries.zip
ogr2ogr -f GeoJSON countries.geojson ne_110m_admin_0_countries.shp

mapshaper countries.geojson \
  -filter "iso_a3 == 'BEN' || iso_a3 == 'BFA' || iso_a3 == 'CIV' || iso_a3 == 'GNB' || iso_a3 == 'MLI' || iso_a3 == 'NER' || iso_a3 == 'SEN' || iso_a3 == 'TGO'" \
  -simplify 5% keep-shapes \
  -o /Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/app/assets/geo/uemoa-borders.geo.json format=geojson
```

Vérifier la taille finale : objectif ≤ 35 KB. Inspecter visuellement avec geojson.io.

## Vérifications avant PR

- [ ] Tests backend ≥ 80 % couverture sur les nouveaux fichiers
- [ ] Tests frontend ≥ 80 % couverture sur les nouveaux composants
- [ ] E2E Playwright 4/4 scénarios verts
- [ ] Bundle frontend chat (sans interaction map) : delta ≤ +20 KB (vérifier via `nuxt build` + analyse stats)
- [ ] Leaflet absent du bundle initial (vérifier que le chunk est chargé uniquement quand `MapBlock` est rendu)
- [ ] Dark mode complet sur les 4 composants (audit visuel manuel)
- [ ] ARIA labels présents sur les éléments interactifs (audit avec NVDA / VoiceOver)
- [ ] Constitution check passé (Cf. plan.md)
- [ ] CLAUDE.md mis à jour (technologie Leaflet + tools visualization ajoutée)
