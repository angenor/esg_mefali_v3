# F11 — Tools de Visualisation Typés (KPICard, MatchCard, Map, ComparisonTable)

**Module(s) source(s)** : Module 1.1.2 (Réponses Graphiques + Textuelles)
**Priorité** : P1 — important pour la qualité conversationnelle et le matching projet↔offre
**Dépendances** : F01 (sources cliquables), F04 (Money typed), F06 (Project), F07 (Offer)
**Estimation** : 1.5 sprints

## Contexte & motivation

Module 1.1.2 spécifie un catalogue de tools de visualisation typés (Pydantic backend, composants Vue stylés frontend). État actuel : la plupart des visualisations passent par des **blocs markdown ```chart, ```mermaid, ```table, ```timeline, ```progress, ```gauge** parsés en frontend (`useMessageParser.ts`, `MessageParser.vue`). C'est générique mais pas conforme au catalogue typé attendu.

**État actuel** :
- `richblocks/` contient : `ChartBlock` (chart.js wrapper générique), `TableBlock`, `TimelineBlock`, `ProgressBlock`, `GaugeBlock`, `MermaidBlock` ✅
- `show_kpi_card` ❌ : pas de composant KPI typed (chiffre clé + delta)
- `show_match_card` ❌ : pas de composant carte projet↔offre cliquable
- `show_map` ❌ : pas de Leaflet, aucune dépendance
- `show_comparison_table` ⚠️ : `TableBlock` est générique, pas de variante "comparaison" pour offres concurrentes

**Conséquences** :
- Pour afficher "45 tCO2e ↓12% vs 2024", le LLM produit du texte ou un bar chart (overkill)
- Pour proposer une offre matchée, le LLM produit du texte ou une `TableBlock` au lieu d'une carte cliquable qui ouvre `/financing/offers/{id}`
- Pas de carte des projets / intermédiaires, alors que c'est très pertinent pour PME africaines (visuel régional)
- Comparateur d'offres pour même fonds (différenciateur Module 3) ne peut pas être rendu visuellement structuré

## User stories

- **PME** : « Quand le LLM résume mon empreinte carbone, je veux voir un gros chiffre "45 tCO2e" + indicateur ↓12% vs 2024 + un picto Source à côté, pas un paragraphe de texte. »
- **PME** : « Quand le LLM me propose 3 offres compatibles, je veux voir 3 cartes (logo fonds + intermédiaire, score 78 %, montant, délai) avec bouton "Explorer" qui ouvre la fiche offre. »
- **PME** : « Quand le LLM compare GCF via BOAD vs GCF via UNDP vs GCF via AFD, je veux un tableau côte-à-côte : critères, frais, délais, taux de succès, avec les écarts en couleur. »
- **PME** : « Quand le LLM me parle de mon projet à Bouaké et de l'intermédiaire BOAD à Lomé, je veux voir une carte UEMOA avec les deux points et l'itinéraire visuel, pour avoir le contexte géographique. »

## Périmètre fonctionnel

### Tool `show_kpi_card`

Tool LangChain (typé Pydantic strict) :
```python
class KPICardArgs(BaseModel):
    title: str  # "Empreinte carbone 2026"
    value: str  # "45 tCO2e" — formatted
    value_money: Money | None  # si chiffre monétaire (Money typé F04)
    delta: float | None  # +12 (positif) / -12 (négatif)
    delta_label: str | None  # "vs 2024"
    delta_direction: Literal["up", "down", "neutral"] | None
    delta_is_good: bool | None  # True si "up = good" (ex : score), False si "down = good" (ex : émissions)
    icon: str | None  # nom heroicons
    color: Literal["emerald", "blue", "rose", "amber", "violet"] = "emerald"
    source_id: UUID | None  # F01 cliquable
    drilldown_url: str | None  # ex : /carbon/results
```

Composant `KPICardBlock.vue` :
- Card avec gradient subtil selon `color`
- Icône à gauche
- Titre + value gros
- Delta avec flèche couleur (vert si is_good, rouge sinon)
- Picto Source en bas-droite (F01)
- Click → navigate vers `drilldown_url`
- Dark mode

### Tool `show_match_card`

```python
class MatchCardArgs(BaseModel):
    project_id: UUID  # contexte projet
    offer_id: UUID  # offre matchée
    fund_name: str
    fund_logo_url: str | None
    intermediary_name: str
    intermediary_logo_url: str | None
    compatibility_score: int  # 0-100
    compatibility_breakdown: dict | None  # {fund_score: 80, intermediary_score: 65}
    amount_range: str  # "1M - 5M FCFA"
    timeline: str  # "12-18 mois"
    instruments: list[str]  # ["subvention", "blending"]
    missing_criteria_count: int  # combien manquent à compléter
    cta_label: str = "Explorer"
    drilldown_url: str  # /financing/offers/{offer_id}?project_id={project_id}
```

Composant `MatchCardBlock.vue` :
- Header : 2 logos (fund + intermediary), score circle gauge avec décomposition
- Body : range montant, timeline, badges instruments
- Footer : "X critères manquants" + bouton CTA
- Click → ouvre la fiche offre dans le contexte du projet
- Hover effect, dark mode

### Tool `show_map`

```python
class MapArgs(BaseModel):
    title: str | None
    center: tuple[float, float] | None  # lat, lon
    zoom: int = 6
    markers: list[MapMarker]
    show_uemoa_overlay: bool = False  # overlay des frontières UEMOA

class MapMarker(BaseModel):
    lat: float
    lon: float
    label: str
    type: Literal["project", "intermediary", "fund_office", "company_hq"]
    icon: str | None
    popup_content: str | None  # HTML rich (XSS sanitized)
    drilldown_url: str | None
```

Composant `MapBlock.vue` :
- Wrapper Leaflet (`leaflet>=1.9` + `leaflet-vue` ou direct)
- Tile layer OpenStreetMap par défaut, fallback Africa CENTER (ex : `https://tile.openstreetmap.fr/`)
- Markers SVG colorés selon `type`
- Popup au clic
- Si `show_uemoa_overlay` : layer GeoJSON des 8 pays UEMOA
- Bouton "Plein écran"
- Dark mode (avec tile layer dark via `https://api.maptiler.com/maps/streets-dark/`)

Installer dépendance : `pnpm add leaflet @types/leaflet`

### Tool `show_comparison_table`

```python
class ComparisonTableArgs(BaseModel):
    title: str
    subjects: list[ComparisonSubject]  # ex : 3 offres
    rows: list[ComparisonRow]  # ex : critères, frais, délais
    highlight_winner: bool = True  # surligne la meilleure cellule par row

class ComparisonSubject(BaseModel):
    id: str
    label: str  # "GCF via BOAD"
    sublabel: str | None  # "Track record: 80%"
    drilldown_url: str | None

class ComparisonRow(BaseModel):
    label: str  # "Frais d'instruction"
    values: list[ComparisonValue]  # 1 par subject
    type: Literal["text", "money", "duration", "percentage", "rating", "boolean"]
    higher_is_better: bool = True

class ComparisonValue(BaseModel):
    subject_id: str
    value: str | int | float
    money: Money | None
    annotation: str | None  # ex : "+0.5% par rapport à GCF/UNDP"
    source_id: UUID | None
```

Composant `ComparisonTableBlock.vue` :
- Table headers cliquables (drilldown_url)
- Cellules formatées selon type (Money via F04, durations en lisible "12 mois", percentages "80 %")
- Highlight de la meilleure cellule selon `higher_is_better` (vert subtil)
- Flèches indiquant tendance entre cellules d'une même row
- Sources cliquables F01
- Responsive (collapse en cards sur mobile)

### Refactor des blocs richblocks existants

Conserver les blocs markdown génériques (`ChartBlock`, `TableBlock`, etc.) pour les cas ad-hoc, MAIS :
- Privilégier les tools typés quand un cas spécifique existe
- Le `KPICardBlock` remplace les usages "afficher un chiffre clé" via `chart` ou `gauge` simpliste
- Le `MatchCardBlock` remplace les `TableBlock` qui listent des matches
- Le `ComparisonTableBlock` remplace les `TableBlock` quand c'est une comparaison de subjects

### Validation backend Pydantic

Pour chaque tool, payload validé strict (cf. F22 Module 10.2) :
- Champs requis, enums fermés, bornes
- Si invalide → erreur structurée au LLM, retry max 1, fallback texte

### Décision tree dans le prompt (lien F22)

Étendre le system prompt :
```
## ARBRE DE DÉCISION VISUALISATION
- Chiffre clé important (score, total, KPI) → show_kpi_card
- Comparaison de plusieurs entités sur plusieurs critères → show_comparison_table
- Match projet↔offre → show_match_card
- Position géographique pertinente → show_map
- Évolution temporelle → show_line_chart (richblock chart)
- Répartition catégorielle → show_pie_chart / show_donut_chart
- Process / décision → show_mermaid (fallback)
- Sinon → texte
```

## Hors-scope (post-MVP)

- Animation gsap entre frames d'un line_chart
- Drill-down inline (cliquer sur une slice de pie ouvre détail dans la même bulle)
- Synchronisation cross-block (hover sur ligne d'un table → highlight le marker map correspondant)
- Tools 3D (radar 3D, force-directed graph)
- Génération SVG vectoriel sur demande (pour rapports PDF)
- Heatmap thermique
- Sankey diagrams

## Exigences techniques

### Backend

- Étendre `backend/app/graph/tools/visualization_tools.py` (nouveau fichier) :
  - 4 tools typés : `show_kpi_card`, `show_match_card`, `show_map`, `show_comparison_table`
  - Schémas Pydantic stricts (extra="forbid", bornes, enums)
  - Docstring conforme au gabarit 5 sections (Use when / Don't use when / Exemple / Anti)
- Mise à jour `tool_selector_config.py` :
  - `show_kpi_card` : visible sur dashboard, esg, carbon, credit
  - `show_match_card` : visible sur financing, applications
  - `show_map` : visible sur profile (project location), financing (intermediaire location)
  - `show_comparison_table` : visible sur financing, applications
- Mise à jour `app/prompts/system.py` : ajouter le decision tree visualisation
- Mise à jour `app/prompts/financing.py`, `application.py` : encourager `show_match_card` pour matches, `show_comparison_table` pour multi-offres
- Tests :
  - Validation Pydantic : payloads invalides rejetés
  - Test golden set (F22) : LLM choisit le bon tool selon contexte

### Frontend

- Installer `leaflet`, `@types/leaflet`
- Composants typés dans `frontend/app/components/richblocks/` :
  - `KPICardBlock.vue`
  - `MatchCardBlock.vue`
  - `MapBlock.vue`
  - `ComparisonTableBlock.vue`
- Mise à jour `MessageParser.vue` ou équivalent pour rendre ces nouveaux blocs (via tool calls SSE typed, pas via fences markdown)
- Composable `useMapTiles.ts` (gère la sélection du tile layer light/dark)
- Stylisation cohérente avec design system (Tailwind utilities, dark mode complet)
- Accessibilité :
  - KPICard : aria-label descriptif ("KPI: 45 tCO2e, baisse de 12% vs 2024")
  - Map : alt text généré par LLM (Module 1.1.2)
  - ComparisonTable : caption + scope sur th
- Tests Vitest : unit sur chaque composant
- Test Playwright : E2E rendu inline dans le chat

### Base de données

- Aucune nouvelle table
- (post-MVP) : tables `intermediary_offices(intermediary_id, lat, lon)` pour `show_map`

## Critères d'acceptation

- [ ] 4 nouveaux tools LangChain implémentés avec Pydantic strict
- [ ] 4 nouveaux composants Vue créés avec dark mode et accessibilité
- [ ] Decision tree mis à jour dans system prompt (lien F22)
- [ ] Leaflet installé et fonctionnel
- [ ] Sources cliquables (F01) intégrées sur KPICard, MatchCard, ComparisonTable
- [ ] Money typé (F04) intégré dans payloads
- [ ] Test E2E : LLM répond avec KPICard pour empreinte carbone → bien rendu inline dans chat
- [ ] Test E2E : LLM propose 3 matches → 3 MatchCards cliquables → click ouvre `/financing/offers/{id}?project_id=Y`
- [ ] Test E2E : LLM compare 3 offres → ComparisonTable affichée avec highlight winner par row
- [ ] Test E2E : LLM parle d'intermédiaires UEMOA → Map affichée avec markers + overlay UEMOA
- [ ] Test eval LLM : 10 cas du golden set vérifient que le LLM choisit le bon tool typé
- [ ] Couverture tests ≥ 80 %

## Risques & garde-fous

- **Risque** : poids du bundle frontend avec Leaflet (~150 KB gzipped). **Garde-fou** : lazy load (`defineAsyncComponent`), seul `MapBlock` charge Leaflet.
- **Risque** : tile layer payant si volume haut. **Garde-fou** : OpenStreetMap par défaut (gratuit, attribution requise) ; Mapbox/Maptiler que post-MVP si besoin.
- **Risque** : confusion entre richblocks markdown génériques et tools typés. **Garde-fou** : documenter dans `app/graph/tools/README.md` la règle "Si tool typé existe, l'utiliser" ; ajouter à `_tokens_baseline.json` (token budget).
- **Risque** : KPICard pour un chiffre non sourcé crée un faux sentiment d'autorité. **Garde-fou** : `source_id` obligatoire (Pydantic NOT NULL) si la value vient d'un calcul critique ; sinon le LLM doit invoquer `flag_unsourced` (F01).
- **Risque** : ComparisonTable avec 10+ subjects illisible mobile. **Garde-fou** : limiter `subjects` à 5 max, fallback en cards mobile.
- **Risque** : Map affiche des coordonnées approximatives car les `intermediaries` n'ont pas encore de geolocalisation précise. **Garde-fou** : F09 (admin) saisit progressivement les `(lat, lon)` ; en attendant, fallback sur `country_centroid` (centroïde pays = imprécis mais visible).
