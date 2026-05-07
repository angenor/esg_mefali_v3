# Phase 0 — Research: F11 Tools de Visualisation Typés

**Date**: 2026-05-07
**Feature**: F11 — Tools de Visualisation Typés (KPICard, MatchCard, Map, ComparisonTable)

## R-1. Choix de la bibliothèque cartographique frontend

**Decision**: Leaflet 1.9 vanilla, intégré dans Vue 3 via composable + `defineAsyncComponent`, sans wrapper Vue dédié.

**Rationale**:
- Leaflet est la bibliothèque OSS de référence (≥ 12 ans en production), bundle minimal (~42 KB gzipped pour le core), API stable.
- Pas de dépendance Vue spécifique : les wrappers Vue-Leaflet (vue3-leaflet, etc.) ajoutent un layer d'abstraction redondant pour notre usage simple (markers + overlay GeoJSON statique).
- Intégration Nuxt 4 documentée (manipulation `window`/`document` en `onMounted`).

**Alternatives considered**:
- **MapLibre GL JS** : moteur WebGL plus performant pour grandes données mais ~250 KB gzipped, surdimensionné pour un usage chat.
- **OpenLayers** : très complet mais ~150 KB et API plus complexe.
- **Mapbox GL JS** : nécessite clé API et licence payante au-delà d'un seuil de chargements.
- **vue3-leaflet / @vue-leaflet/vue-leaflet** : ajoute ~10 KB et un layer d'abstraction non nécessaire.

## R-2. Tile layer dark mode gratuit sans clé API

**Decision**: CartoDB Dark Matter (`https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png`) en dark mode, OpenStreetMap standard (`https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`) en light mode.

**Rationale**:
- CartoDB Dark Matter est gratuit, utilise les tuiles Carto basées sur les données OSM, attribution requise (`© OpenStreetMap contributors © CARTO`).
- Pas de clé API requise pour usage gratuit (limite raisonnable, pas de quota dur publié).
- Cohérence visuelle avec le dark mode du projet (palette neutre sombre).

**Alternatives considered**:
- **Stamen Toner Lite** (dark) : trop minimaliste (sans labels colorés).
- **Maptiler / Mapbox dark** : nécessite clé API et abonnement.
- **OpenStreetMap.HOT** (humanitarian) : plus orienté light mode.

**Attribution attendue dans le composant** : `© OpenStreetMap contributors` (light), `© OpenStreetMap contributors © CARTO` (dark).

## R-3. Stratégie de lazy-load Leaflet dans Nuxt 4 / Vue 3

**Decision**: Composant `MapBlock.vue` enveloppé via `defineAsyncComponent` dans `MessageParser.vue`. À l'intérieur du composant, l'import Leaflet est dynamique :

```ts
let L: typeof import('leaflet') | null = null
onMounted(async () => {
  if (typeof window === 'undefined') return
  L = await import('leaflet')
  await import('leaflet/dist/leaflet.css')
  // ... initialisation map
})
```

**Rationale**:
- Leaflet manipule `window` / `document` ; SSR Nuxt doit ignorer le composant côté serveur (`ClientOnly` ou import dynamique).
- `defineAsyncComponent` dans `MessageParser.vue` garantit que le chunk Leaflet n'est inclus dans aucun bundle initial, uniquement chargé lorsqu'un message contient un tool `show_map`.
- L'import du CSS Leaflet est aussi dynamique pour éviter d'inclure les styles tant que la carte n'est pas affichée.

**Alternatives considered**:
- `<ClientOnly>` partout : fonctionne mais charge Leaflet dès le premier rendu côté client.
- `nuxt-leaflet` (module) : ajoute un layer module Nuxt pas nécessaire pour un usage isolé.

## R-4. Source du GeoJSON UEMOA

**Decision**: Extraire les frontières des 8 pays UEMOA (Bénin, Burkina Faso, Côte d'Ivoire, Guinée-Bissau, Mali, Niger, Sénégal, Togo) depuis [Natural Earth](https://www.naturalearthdata.com/) (Public Domain), simplifier à ~30 KB via mapshaper, bundler dans `frontend/app/assets/geo/uemoa-borders.geo.json`.

**Rationale**:
- Natural Earth = source de référence Public Domain, pas de licence à respecter.
- Asset local bundlé = chargement déterministe, offline-friendly, pas de dépendance CDN externe.
- Simplification mapshaper réduit la taille tout en conservant la lisibilité visuelle (zoom 4-8).

**Alternatives considered**:
- CDN OSM-Boundaries / GADM : dépendance externe, taille plus grande, pas de garantie SLA.
- Inline (constante TS dans le composant) : pollue le bundle initial même quand la carte n'est pas affichée.

**Procédure de génération** (à documenter dans quickstart.md) :
```bash
# 1. Télécharger Natural Earth admin_0_countries
# 2. Filtrer : iso_a3 in (BEN, BFA, CIV, GNB, MLI, NER, SEN, TGO)
# 3. mapshaper -i countries.geojson -filter 'iso_a3 in [...]' -simplify 5% keep-shapes -o uemoa-borders.geo.json
```

## R-5. Transport des tool calls structurés vers le frontend

**Decision**: SSE existant (012-langgraph-tool-calling). Les événements émis par `astream_events()` du graphe LangGraph contiennent déjà `tool_call_end` avec :
- `tool_name` ∈ {show_kpi_card, show_match_card, show_map, show_comparison_table}
- `output` : sérialisation JSON du résultat tool (le tool retourne une string JSON ou un dict structuré)
- `tool_call_id` : identifiant unique pour corrélation

**Pattern adopté** : chaque tool retourne une string JSON (compatible avec la signature LangChain `@tool` et le formatage `tool_calls` du modèle). Le frontend parse cette string et injecte les props dans le composant Vue correspondant.

**Rationale**:
- Pas de duplication de mécanisme de transport.
- Compatibilité ascendante avec les autres tools (cite_source, profile_update, etc.).
- Schéma vérifiable côté frontend via Zod ou type guards TypeScript.

**Alternatives considered**:
- Fences markdown structurées (ex: ` ```kpi_card ... ``` `) : bypass du tool calling, perd la traçabilité dans `tool_call_logs`.
- Custom SSE event type (ex: `kpi_card_emitted`) : multiplie les types d'événements à gérer.

## R-6. Pattern de rendu d'un tool typé inline dans le chat

**Decision**: Étendre `useMessageParser.ts` (composable existant) pour ajouter un détecteur de blocs typés. Le composable retourne, pour chaque message LLM, une liste ordonnée de blocs : texte / fence markdown / tool typé. `MessageParser.vue` parcourt cette liste et instancie le composant Vue correspondant à chaque bloc typé via une table de routing :

```ts
const TYPED_BLOCK_COMPONENTS = {
  show_kpi_card: KPICardBlock,
  show_match_card: MatchCardBlock,
  show_map: defineAsyncComponent(() => import('./MapBlock.vue')),
  show_comparison_table: ComparisonTableBlock,
}
```

**Rationale**:
- Réutilise la chaîne de rendu existante (richblocks markdown ChartBlock/TableBlock/etc. continuent de fonctionner).
- L'ordre des blocs dans le message est préservé : un message peut contenir alternance texte ↔ KPI ↔ texte ↔ MatchCards.

**Alternatives considered**:
- Composant unique `TypedBlockRouter` : plus de couches mais moins lisible pour 4 cas seulement.
- Slot dynamique : équivalent en complexité à la table de routing.

## R-7. Validation Pydantic asymétrique

**Decision**: Pydantic est appliqué automatiquement par LangChain via `args_schema=KPICardArgs` au moment où le LLM invoque le tool. La sortie sérialisée vers le frontend utilise `args.model_dump(mode="json")` pour garantir :
- `Decimal` (Money.amount) → string (préserve précision)
- `UUID` → string
- `Literal[...]` enums → string brute

**Rationale**:
- Évite les divergences entre validation LLM (Python) et rendu (TypeScript).
- Le frontend reçoit toujours du JSON pur, conforme au schéma sérialisé.

**Alternatives considered**:
- Double validation (Pydantic backend + Zod frontend) : sur-ingénierie pour un scope bouclé serveur-client.
- Sérialisation custom : risque d'oublier des champs ; `model_dump(mode="json")` couvre tous les cas Pydantic.

## R-8. Stratégie golden set de tests

**Decision**: Tests d'intégration `test_visualization_prompts.py` avec `unittest.mock.AsyncMock` simulant les réponses LLM (`AIMessage(content="", tool_calls=[ToolCall(name="show_kpi_card", args=...)])`). Pour chaque question du golden set, on vérifie :
1. Le routeur LangGraph a bien sélectionné le tool attendu.
2. Le payload validé respecte le schéma Pydantic.
3. (optionnel, hors-scope MVP) Test d'exécution end-to-end avec vrai LLM derrière flag `LLM_EVAL=1`.

**Rationale**:
- Mock LLM = déterminisme + pas de coût API + tests rapides (CI < 30 s).
- Golden set documenté = source de vérité pour l'évolution future du system prompt.

**Composition golden set MVP** :
- 5 questions KPI (esg score, empreinte carbone, score crédit, montant total levé, nombre de critères validés)
- 3 questions match (offres compatibles, intermédiaires partenaires, fonds prioritaires)
- 1 question comparaison (compare 2 offres GCF)
- 1 question map (où sont mes interlocuteurs)

## R-9. Réutilisation du composant modale source F01

**Decision**: Importer le composant existant introduit en F01. À identifier précisément lors de l'implémentation (probablement `frontend/app/components/sources/SourceModal.vue` + composable `useSourceModal.ts`). Le picto Source est exposé comme un sous-composant réutilisable (ex: `SourceCitationIcon.vue`) avec prop `sourceId: string`.

**Rationale**:
- Cohérence UX : un seul comportement pour ouvrir une source partout dans l'application.
- Pas de duplication de logique fetch / cache source.

**Vérification à faire en B**: chercher dans `frontend/app/components/` les composants source* après merge F01 ; sinon coordonner avec l'équipe F01.

## R-10. Stratégie de fallback texte si payload invalide

**Decision**: Étendre le validator existant `app/graph/validators/source_required.py` (ou créer un validator paire `payload_invalid.py`) qui :
1. Capture les `ValidationError` Pydantic levées par LangChain lors du tool calling typé.
2. Renvoie un message d'erreur structuré au LLM dans le tour suivant : `"Le tool {name} a échoué avec erreur de validation: {details}. Réponds en texte simple."`.
3. Limite à 1 retry ; au 2e échec, le LLM bascule en texte natif.

**Rationale**:
- Robustesse face aux hallucinations LLM (champ inconnu, enum hors liste, dépassement borne).
- Pas de rendu cassé côté frontend.

**Alternatives considered**:
- Désactiver l'enforcement Pydantic et accepter tout : casse les invariants de typage.
- Faire silence et logger : utilisateur reçoit un message vide, mauvaise UX.

---

## Synthèse — Aucune NEEDS CLARIFICATION restante

Toutes les décisions techniques sont arrêtées. Phase 1 peut démarrer.
