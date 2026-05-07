# Feature Specification: F11 — Tools de Visualisation Typés (KPICard, MatchCard, Map, ComparisonTable)

**Feature Branch**: `feat/F11-tools-visualisation-typed`
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: « Catalogue de tools de visualisation typés (Pydantic backend, composants Vue stylés frontend) pour Module 1.1.2 — KPICard, MatchCard, Map, ComparisonTable, avec sources cliquables (F01), Money typé (F04), références projet (F06) et offre (F07). »

## Clarifications

### Session 2026-05-07

- Q: Source du GeoJSON des frontières UEMOA pour `show_uemoa_overlay` ? → A: Asset local bundlé côté frontend (~30 KB compressé), pas de CDN externe — déterministe, offline, pas de dépendance réseau au runtime.
- Q: Tile layer dark mode pour MapBlock ? → A: CartoDB Dark Matter (gratuit, OSM-based, pas de clé API) ; light mode = OpenStreetMap standard. Choix piloté par le composable `useMapTiles` qui lit le store `ui`.
- Q: Mécanisme d'enforcement de la règle "source_id obligatoire si chiffre critique" ? → A: Politique documentaire dans system prompt + tool `flag_unsourced` (F01) obligatoire en l'absence de `source_id`. Aucune contrainte Pydantic NOT NULL côté tool args (qui rendrait `show_kpi_card` incompatible avec des KPI non quantitatifs comme un statut "Conforme/Non conforme"). Le validator F01 existant reste responsable de bloquer les sorties contenant un chiffre sans citation au niveau du message LLM.
- Q: Bibliothèque d'icônes pour KPICard et MatchCard ? → A: Heroicons (icônes SVG inline, pas de webfont) — alignement standard projet. Le champ `icon` Pydantic accepte un nom heroicons (ex: `"chart-bar"`, `"banknotes"`). Le composant frontend embarque uniquement le sous-set utilisé via tree-shaking (pas d'ajout au bundle initial pour les icônes non référencées).
- Q: Layout de plusieurs MatchCards rendues dans un même message LLM ? → A: Empilement vertical pleine largeur (1 carte par ligne) dans la bulle de chat ; pas de grille responsive multi-colonnes côté chat (la grille reste réservée à la page `/financing`). Avantages : lisibilité mobile, pas de risque de troncature, parcours linéaire conservé.
- Q: Source des coordonnées centroïdes pays pour le fallback géolocalisation ? → A: Constante Python hardcodée côté backend (`UEMOA_COUNTRY_CENTROIDS`, ~8 entrées), pas de table BDD. Toute évolution future (carte plus large que UEMOA) passera par F09 admin et un seed dédié.

## Contexte métier

Aujourd'hui, l'assistant IA produit des visualisations via des blocs markdown génériques (chart, table, timeline, progress, gauge, mermaid). Cette approche "fence-based" est générique mais ne permet pas :

- d'afficher proprement un chiffre clé sourcé (KPI) sans surcharge graphique ;
- de proposer une carte projet↔offre cliquable qui mène à la fiche offre ;
- de comparer côte-à-côte plusieurs offres concurrentes (différenciateur Module 3) ;
- de localiser géographiquement projet, intermédiaires et bureaux fonds dans la zone UEMOA.

Ce manque dégrade la lisibilité des réponses, surcharge le texte, et casse le parcours conversationnel "découverte → choix → action".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Carte KPI sourcée pour chiffre clé (Priority: P1)

En tant que dirigeant·e de PME, lorsque l'assistant me résume mon empreinte carbone, je veux voir un grand chiffre "45 tCO2e" avec un indicateur "↓12% vs 2024" et un picto Source cliquable, plutôt qu'un paragraphe de texte. Cela me permet de saisir l'information critique en un coup d'œil et de vérifier la source du calcul.

**Why this priority**: P1 — c'est le cas d'usage le plus fréquent (chaque module ESG, carbone, crédit, financement produit des KPI). Une carte KPI propre et sourcée renforce immédiatement la confiance et la crédibilité de la plateforme. C'est aussi le composant le plus simple à livrer.

**Independent Test**: Peut être testé indépendamment en demandant à l'assistant de résumer un bilan carbone existant et en vérifiant qu'une carte KPI s'affiche dans le chat avec valeur, delta, picto Source cliquable, lien drill-down vers la page de détail, et que le composant répond aux thèmes light/dark.

**Acceptance Scenarios**:

1. **Given** une PME avec un bilan carbone 2026 finalisé (45 tCO2e) et un bilan 2024 (51 tCO2e), **When** l'utilisateur demande "résume mon empreinte carbone 2026", **Then** l'assistant répond avec une carte KPI affichant "Empreinte carbone 2026", "45 tCO2e", "↓12% vs 2024" en vert (car baisse = bonne nouvelle pour les émissions), un picto Source ADEME cliquable et un bouton drill-down qui ouvre `/carbon/results`.
2. **Given** une carte KPI affichée dans le chat, **When** l'utilisateur clique sur le picto Source, **Then** une modale ou un panneau latéral présente les métadonnées de la source (titre, éditeur, version, URL, date publication).
3. **Given** un thème dark activé, **When** une carte KPI est rendue, **Then** les couleurs s'adaptent (fond sombre, texte clair, gradient discret) sans perte de lisibilité.

---

### User Story 2 - Cartes de matching projet↔offre cliquables (Priority: P1)

En tant que dirigeant·e de PME en recherche de financement, lorsque l'assistant me propose 3 offres compatibles avec mon projet, je veux voir 3 cartes structurées (logo fonds + intermédiaire, score de compatibilité, montant, délai, instruments) avec un bouton "Explorer", plutôt qu'un tableau ou un paragraphe. Cela me permet de comparer visuellement et d'ouvrir la fiche détaillée en un clic.

**Why this priority**: P1 — c'est le cœur de la valeur du module financement (Module 3). Sans carte cliquable, le parcours conversationnel s'interrompt et l'utilisateur doit chercher manuellement dans le catalogue.

**Independent Test**: Peut être testé indépendamment en créant un projet test, en demandant à l'assistant "quelles offres me correspondent ?" et en vérifiant que 3 MatchCards s'affichent, que le score est cohérent avec le scoring backend, et que le clic sur "Explorer" navigue vers `/financing/offers/{offer_id}?project_id={project_id}`.

**Acceptance Scenarios**:

1. **Given** un projet "Recyclage plastique Bouaké" et 3 offres compatibles, **When** l'utilisateur demande "quelles offres me correspondent ?", **Then** l'assistant affiche 3 cartes empilées avec : logos fonds + intermédiaire, score circulaire (ex: 78 %), range montant ("1-5 M FCFA"), timeline ("12-18 mois"), badges instruments ("subvention", "blending"), compteur critères manquants, bouton "Explorer".
2. **Given** une MatchCard affichée, **When** l'utilisateur clique sur "Explorer", **Then** la navigation ouvre `/financing/offers/{offer_id}?project_id={project_id}` (fiche offre dans le contexte du projet).
3. **Given** une décomposition de score disponible (fund_score=80, intermediary_score=65), **When** l'utilisateur survole le score circulaire, **Then** un tooltip affiche la décomposition.

---

### User Story 3 - Tableau comparatif d'offres concurrentes (Priority: P1)

En tant que dirigeant·e de PME face à plusieurs intermédiaires distribuant le même fonds (ex : GCF via BOAD vs GCF via UNDP vs GCF via AFD), je veux un tableau côte-à-côte des critères, frais, délais et taux de succès, avec mise en évidence visuelle de la meilleure cellule par ligne. Cela me permet de prendre une décision éclairée et de justifier mon choix d'intermédiaire.

**Why this priority**: P1 — c'est un différenciateur unique du Module 3 (comparaison cross-intermédiaires pour un même fonds). Les concurrents n'offrent pas cette vue. Sans ce composant, le LLM produit un tableau générique non comparatif.

**Independent Test**: Peut être testé indépendamment en demandant à l'assistant "compare GCF via BOAD vs GCF via UNDP vs GCF via AFD" et en vérifiant que la table affiche 3 colonnes sujets, plusieurs lignes critères avec types adaptés (montant, durée, pourcentage), highlight winner par ligne et sources cliquables.

**Acceptance Scenarios**:

1. **Given** 3 offres GCF (BOAD, UNDP, AFD) en base, **When** l'utilisateur demande "compare-les", **Then** l'assistant affiche une table avec headers "GCF via BOAD" / "GCF via UNDP" / "GCF via AFD" cliquables (drill-down fiches offres) et lignes "Frais d'instruction" (Money), "Délai instruction" (durée), "Taux succès" (pourcentage), "Documents requis" (texte), avec la meilleure cellule par ligne mise en valeur (vert subtil).
2. **Given** un tableau comparatif sur mobile (< 768 px), **When** l'utilisateur affiche la conversation, **Then** la table se replie en cartes verticales lisibles.
3. **Given** une cellule monétaire avec source ADEME, **When** l'utilisateur clique sur le picto Source, **Then** la source s'ouvre comme dans la User Story 1.

---

### User Story 4 - Carte géographique UEMOA pour contextualisation (Priority: P2)

En tant que dirigeant·e de PME basé·e à Bouaké et orienté·e vers l'intermédiaire BOAD (Lomé), je veux voir une carte UEMOA avec mes sites de projet et l'intermédiaire visualisés, pour saisir le contexte géographique et la distance impliquée. Cela facilite la planification logistique (déplacements, suivi terrain).

**Why this priority**: P2 — utile pour la prise de conscience géographique mais non bloquant pour la valeur métier principale. Dépend aussi de la disponibilité progressive des coordonnées (lat, lon) des intermédiaires (saisie F09).

**Independent Test**: Peut être testé indépendamment en créant un projet avec localisation (Bouaké) et un intermédiaire avec coordonnées (Lomé), en demandant à l'assistant "où sont mes interlocuteurs ?" et en vérifiant qu'une carte Leaflet apparaît avec les markers et l'overlay UEMOA.

**Acceptance Scenarios**:

1. **Given** un projet à Bouaké (lat, lon connus) et un intermédiaire BOAD à Lomé (lat, lon connus), **When** l'utilisateur demande "où sont mes interlocuteurs ?", **Then** une carte centrée sur la zone UEMOA s'affiche avec 2 markers distincts (icône projet + icône intermédiaire), popup au clic avec label et CTA, et overlay GeoJSON des frontières UEMOA visible.
2. **Given** un intermédiaire sans coordonnées précises, **When** l'assistant rend la carte, **Then** un fallback sur le centroïde du pays est utilisé (avec un disclaimer "approximatif").
3. **Given** un thème dark activé, **When** la carte est rendue, **Then** un tile layer dark est utilisé pour cohérence visuelle.

---

### User Story 5 - Sélection du bon tool par l'assistant (Priority: P2)

En tant qu'utilisateur·rice, je m'attends à ce que l'assistant choisisse automatiquement le composant le plus pertinent (KPI vs Match vs Comparaison vs Map vs chart générique) en fonction du contexte de ma question, sans que je doive spécifier le format. L'arbre de décision doit être explicite dans le system prompt.

**Why this priority**: P2 — qualité conversationnelle. Si le LLM n'oriente pas correctement, il revient au texte ou au mauvais composant ; on conserve les fallbacks markdown génériques mais on perd le bénéfice principal.

**Independent Test**: Peut être testé en lançant un golden set de 10 questions (5 KPI, 3 match, 1 comparaison, 1 map) et en vérifiant que ≥ 90 % des réponses utilisent le bon tool typé.

**Acceptance Scenarios**:

1. **Given** un system prompt enrichi avec l'arbre de décision visualisation, **When** une question "résume mon score ESG" est posée, **Then** le LLM appelle `show_kpi_card` (et non pas `chart` ou texte).
2. **Given** une question "compare 2 offres", **When** le LLM répond, **Then** il invoque `show_comparison_table` (pas `show_match_card` ni `TableBlock`).
3. **Given** une question floue ("aide-moi à choisir"), **When** le LLM ne sait pas trancher, **Then** il privilégie le texte simple (fallback) plutôt que de mal choisir un composant.

---

### Edge Cases

- **Payload Pydantic invalide** (LLM hallucine un champ inconnu, dépasse une borne, fournit un enum hors liste) : le validator backend rejette, retry max 1 vers le LLM avec message d'erreur structuré, fallback texte si toujours invalide.
- **MatchCard sans logo** : afficher un placeholder neutre avec initiales du fonds/intermédiaire (pas d'image cassée).
- **ComparisonTable avec > 5 sujets** : limite Pydantic stricte (5 max) ; au-delà, refus serveur avec message clair au LLM.
- **Map sans markers** : afficher un état vide explicite ("Aucun emplacement à afficher pour ce projet") plutôt qu'une carte vide.
- **Map avec coordonnées hors UEMOA** : la carte s'affiche centrée automatiquement sur les markers, l'overlay UEMOA reste optionnel.
- **KPICard avec value_money mais value="" vide** : la value monétaire formatée prime, value libre devient optionnelle si value_money fourni.
- **KPICard avec delta sans delta_label** : afficher le delta seul ("↓12 %") sans préfixe.
- **Click sur drilldown_url menant à une page sans permission** : l'application standard de l'auth gère le redirect (pas une responsabilité du composant).
- **Bundle Leaflet trop lourd** : charge paresseuse via composant async — la carte n'apparaît qu'après instanciation.
- **Source citée dans une cellule mais source_id introuvable** : afficher le texte de la cellule sans le picto, log côté serveur.
- **Comportement multi-blocs dans une même réponse LLM** : l'assistant peut combiner plusieurs blocs typés dans une réponse (ex: 1 KPI + 3 MatchCards), ils s'empilent verticalement.
- **Mobile portrait** : KPI grand, MatchCard pleine largeur, ComparisonTable repliée en cartes, Map limitée à 300 px de hauteur.

## Requirements *(mandatory)*

### Functional Requirements

#### Tool show_kpi_card

- **FR-001**: Le système DOIT exposer un tool `show_kpi_card` au LLM avec un schéma Pydantic strict (`extra="forbid"`, bornes, enums fermés).
- **FR-002**: Le payload DOIT inclure : `title` (texte court), `value` (texte libre formaté ou tirée de `value_money`), `value_money` (Money typé F04, optionnel), `delta` (nombre signé, optionnel), `delta_label` (texte court, optionnel), `delta_direction` (enum "up"/"down"/"neutral", optionnel), `delta_is_good` (booléen, optionnel), `icon` (nom heroicon, optionnel), `color` (enum "emerald"/"blue"/"rose"/"amber"/"violet", défaut "emerald"), `source_id` (UUID source F01, optionnel), `drilldown_url` (URL relative, optionnel).
- **FR-003**: Le composant frontend DOIT afficher : icône à gauche, titre + valeur grande, delta colorisé selon `delta_is_good` (vert ou rouge avec flèche), picto Source cliquable en bas-droite si `source_id` présent, et naviguer vers `drilldown_url` au clic sur la carte si défini.
- **FR-004**: Le composant DOIT supporter les modes light et dark sans perte de lisibilité.
- **FR-005**: Le composant DOIT exposer un attribut ARIA descriptif (ex: aria-label="KPI: Empreinte carbone 2026, 45 tCO2e, baisse de 12% vs 2024") pour accessibilité.

#### Tool show_match_card

- **FR-006**: Le système DOIT exposer un tool `show_match_card` au LLM avec un schéma Pydantic strict.
- **FR-007**: Le payload DOIT inclure : `project_id` (UUID projet F06, requis), `offer_id` (UUID offre F07, requis), `fund_name` (texte, requis), `fund_logo_url` (URL, optionnel), `intermediary_name` (texte, requis), `intermediary_logo_url` (URL, optionnel), `compatibility_score` (entier 0-100, requis), `compatibility_breakdown` (dict {fund_score: int, intermediary_score: int}, optionnel), `amount_range` (texte, requis), `timeline` (texte, requis), `instruments` (liste de chaînes, requis), `missing_criteria_count` (entier ≥ 0, requis), `cta_label` (texte, défaut "Explorer"), `drilldown_url` (URL, requis).
- **FR-008**: Le composant DOIT afficher : 2 logos en header (avec placeholder initiales si URL absente), score circulaire (avec décomposition en tooltip), range montant + timeline, badges instruments, compteur critères manquants, bouton CTA, hover effect.
- **FR-009**: Le composant DOIT naviguer vers `drilldown_url` au clic sur le bouton CTA (cible attendue : `/financing/offers/{offer_id}?project_id={project_id}`).
- **FR-010**: Le composant DOIT supporter dark mode et fournir un aria-label structuré.

#### Tool show_map

- **FR-011**: Le système DOIT exposer un tool `show_map` au LLM avec un schéma Pydantic strict.
- **FR-012**: Le payload DOIT inclure : `title` (texte, optionnel), `center` (tuple lat,lon, optionnel — défaut centre UEMOA si absent), `zoom` (entier 1-18, défaut 6), `markers` (liste de MapMarker, max 50), `show_uemoa_overlay` (booléen, défaut false).
- **FR-013**: Chaque MapMarker DOIT inclure : `lat` (float -90/90), `lon` (float -180/180), `label` (texte, requis), `type` (enum "project"/"intermediary"/"fund_office"/"company_hq", requis), `icon` (texte, optionnel), `popup_content` (HTML court XSS-sanitisé, optionnel), `drilldown_url` (URL, optionnel).
- **FR-014**: Le composant DOIT être chargé en lazy-load (composant async) pour éviter d'inclure Leaflet dans le bundle initial.
- **FR-015**: Le composant DOIT utiliser un tile layer libre par défaut (OpenStreetMap en light, CartoDB Dark Matter en dark), fournir des markers SVG colorés selon `type`, popups au clic, overlay GeoJSON UEMOA depuis un asset local bundlé si `show_uemoa_overlay=true`, bouton plein écran, et adaptation light/dark via composable `useMapTiles` qui lit le store `ui`.
- **FR-016**: Si un intermédiaire n'a pas de coordonnées précises, le composant accepte un fallback sur le centroïde du pays issu d'une constante backend `UEMOA_COUNTRY_CENTROIDS` (Bénin, Burkina Faso, Côte d'Ivoire, Guinée-Bissau, Mali, Niger, Sénégal, Togo), accompagné d'un disclaimer textuel "position approximative".

#### Tool show_comparison_table

- **FR-017**: Le système DOIT exposer un tool `show_comparison_table` au LLM avec un schéma Pydantic strict.
- **FR-018**: Le payload DOIT inclure : `title` (texte, requis), `subjects` (liste de ComparisonSubject, max 5, min 2), `rows` (liste de ComparisonRow, max 20), `highlight_winner` (booléen, défaut true).
- **FR-019**: Chaque ComparisonSubject DOIT inclure : `id` (texte unique dans la liste), `label` (texte court), `sublabel` (texte, optionnel), `drilldown_url` (URL, optionnel).
- **FR-020**: Chaque ComparisonRow DOIT inclure : `label` (texte court), `values` (liste de ComparisonValue, une par sujet), `type` (enum "text"/"money"/"duration"/"percentage"/"rating"/"boolean"), `higher_is_better` (booléen, défaut true).
- **FR-021**: Chaque ComparisonValue DOIT inclure : `subject_id` (référence à un sujet), `value` (texte/entier/float), `money` (Money optionnel — utilisé si type=money), `annotation` (texte court, optionnel), `source_id` (UUID source F01, optionnel).
- **FR-022**: Le composant DOIT formater les cellules selon `type` (Money via F04, durée lisible "12 mois", pourcentage "80 %", rating "4/5", boolean coche/croix).
- **FR-023**: Le composant DOIT mettre en valeur visuelle (fond vert subtil) la meilleure cellule par ligne quand `highlight_winner=true`, en respectant `higher_is_better`.
- **FR-024**: Le composant DOIT afficher un picto Source cliquable sur les cellules avec `source_id`.
- **FR-025**: Le composant DOIT être responsive : sur largeur ≤ 768 px, replier en cartes verticales ; au-delà, table classique.

#### Comportement et orchestration

- **FR-026**: Le system prompt DOIT inclure un "arbre de décision visualisation" guidant le LLM dans le choix entre KPICard, MatchCard, ComparisonTable, Map, fences markdown génériques et texte.
- **FR-027**: Les prompts spécialisés financing et application DOIVENT encourager l'usage de `show_match_card` (pour résultats matching) et `show_comparison_table` (pour comparaison cross-offres).
- **FR-028**: Le système DOIT filtrer la visibilité des nouveaux tools par page : `show_kpi_card` visible sur dashboard, esg, carbon, credit ; `show_match_card` visible sur financing, candidatures ; `show_map` visible sur profile, financing ; `show_comparison_table` visible sur financing, candidatures.
- **FR-029**: En cas de payload invalide retourné par le LLM, le système DOIT renvoyer une erreur structurée au LLM (avec retry max 1) puis basculer sur fallback texte si la 2e tentative échoue.
- **FR-030**: Les blocs typés DOIVENT pouvoir être combinés librement dans une même réponse LLM (empilement vertical dans le chat, 1 bloc par ligne pleine largeur — pas de grille multi-colonnes côté chat).
- **FR-031**: Les blocs richblocks markdown existants (chart, table, timeline, progress, gauge, mermaid) DOIVENT continuer à fonctionner pour les cas d'usage ad-hoc (compatibilité ascendante).

#### Sourcage et conformité

- **FR-032**: Tout chiffre critique affiché dans un KPICard, MatchCard ou ComparisonValue avec dimension "Money" ou indicateur quantitatif DOIT pouvoir référencer une `source_id` (F01) ; en l'absence, le LLM est instruit dans le system prompt d'invoquer `flag_unsourced` (F01). L'enforcement reste documentaire au niveau du tool args (pas de NOT NULL Pydantic, pour autoriser KPI non quantitatifs comme statut "Conforme/Non conforme") ; le validator F01 existant reste responsable de bloquer toute sortie LLM contenant un chiffre sans citation.
- **FR-033**: Le clic sur un picto Source DOIT ouvrir la modale source standard de la plateforme (introduite en F01).

#### Multi-tenant et auth

- **FR-034**: Les tools DOIVENT respecter le multi-tenant strict (F02) : les `project_id` et `offer_id` référencés DOIVENT appartenir à l'`account_id` courant ; à défaut, l'erreur est levée côté backend avant l'émission du tool.

### Key Entities

- **KPICardArgs** : modèle Pydantic strict pour l'invocation du tool `show_kpi_card`. Tous les champs définis dans FR-002. Aucune persistance (transit LLM → frontend uniquement).
- **MatchCardArgs** : modèle Pydantic strict pour l'invocation du tool `show_match_card`. Tous les champs définis dans FR-007. Aucune persistance.
- **MapArgs** + **MapMarker** : modèles Pydantic stricts pour `show_map`. Champs définis FR-012 et FR-013. Aucune persistance.
- **ComparisonTableArgs** + **ComparisonSubject** + **ComparisonRow** + **ComparisonValue** : modèles Pydantic stricts pour `show_comparison_table`. Champs définis FR-018 à FR-021. Aucune persistance.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Lorsque l'assistant doit afficher un chiffre clé (résumé d'évaluation, KPI dashboard), il choisit `show_kpi_card` dans ≥ 90 % des cas mesurés sur un golden set de 10 questions ciblant les KPI.
- **SC-002**: Lorsque l'assistant propose un matching projet↔offre, il choisit `show_match_card` au lieu d'un tableau ou texte dans ≥ 90 % des cas mesurés sur un golden set de 5 questions de financement.
- **SC-003**: Lorsque l'assistant compare ≥ 2 offres concurrentes, il choisit `show_comparison_table` dans ≥ 90 % des cas mesurés sur un golden set de 3 questions de comparaison.
- **SC-004**: Le bundle JS de la page chat (sans interaction map) ne dépasse pas la taille actuelle + 20 KB après ajout des nouveaux composants typés ; Leaflet est totalement exclu du bundle initial (lazy-load vérifié).
- **SC-005**: La couverture de tests (unit + intégration) atteint ≥ 80 % sur les nouveaux tools backend et nouveaux composants frontend.
- **SC-006**: Tous les composants nouveaux sont accessibles : aria-labels présents, contraste WCAG AA en light et dark, navigation clavier fonctionnelle pour les éléments interactifs (boutons, picto sources, drill-downs).
- **SC-007**: L'utilisateur PME peut, dans une session typique de chat, identifier visuellement le meilleur match parmi 3 offres en moins de 30 secondes (validable lors d'un test usage).
- **SC-008**: Aucun payload invalide n'atteint le rendu frontend : 100 % des invocations avec payload non conforme déclenchent le retry+fallback côté backend.

## Assumptions

- F01 (sources cliquables) est mergé : le composant modale Source existe et expose un picto cliquable réutilisable.
- F04 (Money typed) est mergé : le type `Money` Pydantic est disponible côté backend et son équivalent TypeScript côté frontend.
- F06 (Project) est mergé : l'entité Project et ses tools (`list_projects`, `get_project`, etc.) existent ; la table contient `country` et idéalement `lat`/`lon`.
- F07 (Offer) est mergé : l'entité Offer (Fonds × Intermédiaire) existe avec `fund_id`, `intermediary_id`, score de compatibilité.
- F02 (multi-tenant) est mergé : le filtrage par `account_id` est appliqué automatiquement dans les services.
- L'assistant LLM utilise les prompts modulaires existants (system + module-specific) et la politique tool calling LangGraph existante (012-langgraph-tool-calling).
- Le tile layer OpenStreetMap public est suffisant pour le MVP ; la souscription à Mapbox/Maptiler est post-MVP si la charge l'exige.
- Les coordonnées géographiques précises des intermédiaires sont saisies progressivement par les Admins via F09 ; en attendant, fallback sur les centroïdes pays via constante backend `UEMOA_COUNTRY_CENTROIDS` (8 pays UEMOA hardcodés, pas de table BDD).
- Le frontend utilise Leaflet 1.9 (open source), pas de dépendance Leaflet Vue (intégration directe via composable plus mainstream pour Vue 3).
- Le composable `useMapTiles` choisit le tile layer en lisant le store `ui` (light/dark).
- Les nouveaux tools ne mutent rien (lecture/présentation uniquement) : pas de migration BDD, pas d'ajout d'audit log spécifique (au-delà du log standard `tool_call_logs` introduit en 012).
- L'arbre de décision visualisation reste documentaire (system prompt) ; aucune contrainte de routing dur — le LLM peut toujours fallback texte si nécessaire.
- Le golden set de questions pour SC-001/002/003 sera construit lors de la phase d'implémentation (10 + 5 + 3 = 18 questions) et exécuté en mode mock LLM pour le TDD, puis validé manuellement avec un vrai LLM avant merge.

## Dependencies

- **F01 — Catalogue Sources verifiées** (mergé) : `cite_source`, picto modale source.
- **F02 — Multi-tenant** (mergé) : isolation `account_id`.
- **F04 — Money typed** (mergé) : type `Money` Pydantic + TypeScript.
- **F06 — Entité Project** (mergé) : tools projet, géolocalisation projet.
- **F07 — Entité Offer = Fonds × Intermédiaire** (mergé) : `offer_id`, scoring matching.
- **012 — LangGraph tool calling** (mergé) : infrastructure de tool binding et SSE streaming.
- **013 — Multi-turn routing** (mergé) : routage stable entre modules pour permettre au LLM de produire les blocs typés au bon moment.
