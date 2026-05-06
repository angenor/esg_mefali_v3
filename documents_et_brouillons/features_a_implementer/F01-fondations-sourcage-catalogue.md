# F01 — Fondations Sourçage et Catalogue Source

**Module(s) source(s)** : Module 0.1 (Sourçage et Anti-Hallucination), Module 0.7 (Mapping ESG)
**Priorité** : P0 — BLOQUANTE pour la crédibilité produit (différenciateur n°1)
**Dépendances** : aucune (feature de fondation)
**Estimation** : 3-4 sprints

## Contexte & motivation

Dans le brainstorming (Module 0.1), il est dit : « en finance verte/ESG, une affirmation non sourcée n'a aucune valeur. Un fund officer, un auditeur ou la PME elle-même doit pouvoir cliquer et vérifier chaque chiffre, chaque critère, chaque formule, chaque seuil. C'est l'avantage compétitif majeur de la plateforme. »

**État actuel** :
- Aucune table `sources` dans la BDD
- Les facteurs d'émission carbone sont **codés en dur** dans `backend/app/modules/carbon/emission_factors.py` (ex : `electricity_ci: 0.456 kgCO2e/kWh` sans URL/page/version)
- Les 30 critères ESG sont des dataclasses Python dans `backend/app/modules/esg/criteria.py` sans aucune source liée
- Les pondérations sectorielles `SECTOR_WEIGHTS` (`backend/app/modules/esg/weights.py`) sont des constantes non sourcées
- Les benchmarks ESG sectoriels indiquent uniformément `"source": "Estimations basees sur moyennes regionales Afrique de l'Ouest"` (auto-référence non vérifiable)
- Les constantes du simulateur financier (`_SAVINGS_RATE = 0.15`, `_CARBON_IMPACT_PER_MXOF = 1.7`) sont **inventées sans source**
- Aucun tool LangChain `cite_source`, `search_source`, `flag_unsourced`
- Aucun composant frontend `SourceLink`, `SourceModal`, `SourceBadge`
- Le PDF de rapport ESG affiche des références à 4 référentiels (UEMOA, BCEAO, CEDEAO, Gold Standard/Verra) qui sont du **rebadge cosmétique** sans calcul indépendant

**Conséquence** : la promesse marketing « chaque chiffre cliquable vers sa source officielle » est techniquement fausse. La plateforme actuelle est dans la même catégorie que les outils ESG « boîte noire » qu'elle prétend remplacer.

## User stories

- **PME** : « En tant que PME, quand je vois un score ESG, un facteur d'émission, un seuil d'éligibilité ou une recommandation, je veux pouvoir cliquer sur un picto Source pour voir l'URL officielle, la version du document, la page et la date de capture, afin de défendre mon dossier et de vérifier l'information. »
- **Fund officer** (utilisateur tiers, hors-plateforme) : « Quand je reçois un rapport ESG ou un dossier de candidature généré par la plateforme, je veux trouver en annexe une liste auto-générée de toutes les sources utilisées (URL, version, date, page), afin d'auditer la crédibilité de l'analyse. »
- **Admin ESG Mefali** : « En tant qu'admin, je veux saisir manuellement une `Source` (URL, titre, publisher, version, date, page, section), la marquer `pending`, et qu'un autre admin la valide en `verified` avant qu'elle ne soit utilisable. »
- **LLM** : « En tant qu'agent IA, quand je dois affirmer un chiffre, un critère ou une formule, je veux invoquer le tool `cite_source(source_id)` pour pointer vers une source vérifiée. Si je ne dispose pas de source, je dois invoquer `flag_unsourced(claim)` ou `search_source(query)` pour explorer le catalogue. Le backend doit me rejeter si je produis un chiffre sans `cite_source` correspondant. »

## Périmètre fonctionnel

### Entité `Source` (premier rang)

Champs obligatoires :
- `id: UUID` (PK)
- `url: str` (URL officielle, doit pointer vers un document accessible)
- `title: str` (titre du document)
- `publisher: str` (GCF, BOAD, IPCC, ADEME, IFC, UEMOA, BCEAO, etc.)
- `version: str` (version du document au moment de la capture, ex : "v23", "2024", "AR6")
- `date_publi: date` (date de publication du document source)
- `page: int | null` (numéro de page de l'extrait)
- `section: str | null` (référence textuelle, ex : "Annexe 3", "§ 4.2.1")
- `captured_at: datetime` (quand on a enregistré la source)
- `captured_by: UUID FK users.id` (admin qui a saisi)
- `verified_by: UUID FK users.id | null` (admin qui a validé — workflow 4-yeux)
- `verification_status: enum('draft', 'pending', 'verified', 'outdated')` (par défaut `draft`)
- `verified_at: datetime | null`
- `outdated_reason: str | null`

Post-MVP (différé) :
- `archived_url: str | null` (snapshot Wayback / archive interne)
- `content_hash: str | null` (SHA-256 du contenu pour détecter les changements)

### Entités sourcées

Créer (ou enrichir si existant) les tables suivantes avec FK `source_id NOT NULL` :
- `indicators` (= unité atomique de mesure ESG, ex : "% déchets recyclés")
- `referentials` (collection d'indicateurs avec seuils et poids)
- `referential_indicators` (jointure N-N : indicator_id, referential_id, weight, threshold, source_id)
- `criteria` (condition logique sur un ou plusieurs indicateurs)
- `formulas` (formules de calcul, ex : score combiné crédit)
- `thresholds` (seuils d'éligibilité)
- `emission_factors` (facteurs d'émission ADEME/IPCC/IEA, par catégorie + pays UEMOA)
- `required_documents` (liste documents requis par fonds/intermédiaire, sourcés)
- `simulation_factors` (les `_SAVINGS_RATE`, `_CARBON_IMPACT_PER_MXOF` actuels — sortis du code Python)

Pour chaque table : ajouter contrainte `source_id REFERENCES sources(id) NOT NULL`.

### Workflow `draft → published`

- Toute entité du catalogue (indicator, referential, fund, intermediary, etc.) a un champ `publication_status: enum('draft', 'published')`.
- Un objet ne peut passer en `published` que si **toutes ses sources** sont en `verification_status = 'verified'`.
- Le LLM ne peut consommer que des objets `published`.
- Trigger PostgreSQL ou check applicatif au moment du `UPDATE ... SET publication_status = 'published'`.

### Tools LLM dédiés

Créer `backend/app/graph/tools/sourcing_tools.py` :

- `cite_source(source_id: UUID) → SourceCitation` : référencer une source vérifiée. Retourne `{url, title, publisher, version, date_publi, page}` injectables dans la réponse.
- `search_source(query: str, publisher: str | null = None, limit: int = 5) → list[Source]` : recherche dans le catalogue indexé (full-text + embedding). Filtrable par publisher.
- `flag_unsourced(claim: str, reason: str) → FlagResult` : marquer explicitement une assertion qu'on ne peut pas sourcer. Loggé pour revue admin.

Tous trois enregistrés dans `tool_selector_config.py` et exposés sur tous les nœuds qui produisent des chiffres.

### Validation backend stricte

Middleware ou post-processeur dans `backend/app/graph/graph.py` :
- Parse la réponse LLM (texte final + tool_calls de la session)
- Détecte les **chiffres**, **scores**, **critères**, **formules**, **seuils**, **facteurs d'émission** via regex (ex : `\d+(\.\d+)?\s*(%|tCO2e|kgCO2e|FCFA|EUR|USD|/100|/10)`)
- Pour chaque détection : vérifier qu'un `cite_source` correspondant existe dans les tool_calls du tour
- Si absent : **rejeter la réponse**, retourner une erreur structurée au LLM (`"chiffre détecté sans source : 0.456 kgCO2e/kWh — invoque cite_source ou flag_unsourced"`), forcer un retry (max 1).
- Si retry échoue : fallback texte « je ne dispose pas d'une source vérifiée pour ce chiffre » + log incident.

Pas négociable : sans cette validation, le sourçage est une promesse vide.

### UI Frontend

Composants à créer dans `frontend/app/components/sources/` :
- `SourceLink.vue` : picto Source cliquable inline (icône `i-heroicons-link` + tooltip preview)
- `SourceModal.vue` : modal détail (URL cliquable, publisher, version, date_publi, page, section, captured_at, verified_by, statut). Avec bouton "Ouvrir le document officiel" (target="_blank").
- `SourceBadge.vue` : badge visuel `verified` (vert ✓) / `pending` (orange ⏳) / `outdated` (rouge ⚠️).
- `SourcesList.vue` : liste de sources d'un objet (référentiel, indicateur, score) avec drill-down.

Composables :
- `useSources.ts` : `fetchSource(id)`, `searchSources(query)`, `cacheSource(source)`.

Store Pinia :
- `sources.ts` : cache des sources fréquemment consultées.

Page :
- `pages/sources/index.vue` : vue PME read-only du catalogue de sources vérifiées (filtrable par publisher, recherche full-text).

### Intégration UI sur chaque chiffre

À chaque endroit où un chiffre/score/critère est affiché, ajouter le picto `SourceLink` :
- `frontend/app/components/dashboard/ScoreCard.vue` (scores ESG/carbon/credit)
- `frontend/app/components/esg/Recommendations.vue`
- `frontend/app/components/esg/StrengthsBadges.vue`
- `frontend/app/components/esg/CriteriaProgress.vue`
- `frontend/app/components/credit/FactorsRadar.vue`
- `frontend/app/components/credit/Recommendations.vue`
- `frontend/app/components/dashboard/FinancingCard.vue`
- `frontend/app/pages/carbon/results.vue` (chaque facteur d'émission affiché)
- `frontend/app/pages/financing/[id].vue` (critères du fonds + intermédiaire)
- `frontend/app/pages/applications/[id].vue` (montants, frais, délais)

### Annexe "Sources et références" auto-générée dans rapports PDF

Modifier `backend/app/modules/reports/templates/esg_report.html` pour ajouter une **section finale auto-générée** :
- Liste de toutes les sources mobilisées dans le rapport (collectées via les `cite_source` invoqués pendant la génération).
- Pour chaque source : URL, titre, publisher, version, date_publi, page, section, statut.
- Numérotation [1], [2], [3] avec renvois inline dans le texte du rapport.
- Idem pour le rapport Carbone (à créer en F21) et l'attestation Crédit (F08).

## Hors-scope (post-MVP)

- `archived_url` (snapshot Wayback)
- `content_hash` pour détecter les changements de contenu source
- Cron de revalidation automatique des sources (vérifier que les URL répondent toujours, que les versions n'ont pas changé)
- Scraper auto sites officiels (GCF, BOAD, ADEME) pour pré-remplir le catalogue
- Marketplace de sources contributives (consultants tiers)

## Exigences techniques

### Backend

- Migration Alembic : créer `sources`, `indicators`, `referentials`, `referential_indicators`, `criteria`, `formulas`, `thresholds`, `emission_factors`, `required_documents`, `simulation_factors`.
- Modèles SQLAlchemy correspondants dans `backend/app/models/source.py` et split par domaine (`indicator.py`, `referential.py`, etc.).
- Ajouter colonne `publication_status` sur `funds`, `intermediaries`, `referentials`, `indicators`, `templates_dossier`.
- Ajouter FK `source_id` (NOT NULL après backfill) sur tous les objets factuels.
- Trigger PostgreSQL `before_update_publication_status` qui vérifie que toutes les sources liées sont `verified`.
- Schémas Pydantic dans `backend/app/schemas/source.py` (Source, SourceCreate, SourceUpdate, SourceVerify).
- Service `backend/app/modules/sources/service.py` : CRUD + verify + search full-text/embedding.
- Router `backend/app/modules/sources/router.py` :
  - `GET /api/sources` (liste filtrable, paginée, accessible PME read-only sur `verified` only)
  - `GET /api/sources/{id}`
  - `POST /api/sources` (admin only, status = `pending`)
  - `POST /api/sources/{id}/verify` (admin différent du captured_by, transition pending → verified)
  - `POST /api/sources/{id}/mark-outdated` (admin)
  - Tools LangChain dans `backend/app/graph/tools/sourcing_tools.py`.
- Validation middleware dans `backend/app/graph/validators/source_required.py` invoqué après chaque tour LLM.
- Migration des données existantes :
  - Créer ~30 sources verified pour : ADEME Base Carbone v23, IPCC AR6 WG3, IEA Africa Energy Outlook 2024, Taxonomie verte UEMOA, Circulaire BCEAO 002-2024, GCF Investment Framework, IFC Performance Standards 2012, BOAD Politique Sectorielle ESS, Gold Standard, Verra VCS, etc.
  - Migrer `EMISSION_FACTORS` Python → table `emission_factors` avec FK vers ADEME/IPCC.
  - Migrer `ESGCriterion` 30 critères → table `indicators` avec FK vers UEMOA/IFC/GRI/ODD selon contexte.
  - Migrer pondérations `SECTOR_WEIGHTS` → table `referential_indicators`.
  - Migrer constantes simulateur → table `simulation_factors` (en attendant de les sourcer correctement, marquer `verification_status = 'pending'`).

### Frontend

- Composants Vue 3 dans `frontend/app/components/sources/`
- Composable `frontend/app/composables/useSources.ts`
- Store Pinia `frontend/app/stores/sources.ts`
- Page `frontend/app/pages/sources/index.vue`
- Intégration `<SourceLink :sourceId="..." />` partout où un chiffre/critère/score est affiché
- Dark mode complet
- Accessibilité : `aria-label` descriptif, `aria-describedby`, focus trap dans modal

### Base de données

- Tables créées : `sources`, `indicators`, `referentials`, `referential_indicators`, `criteria`, `formulas`, `thresholds`, `emission_factors`, `required_documents`, `simulation_factors`
- Index : `sources(verification_status)`, `sources(publisher)`, full-text sur `(title, publisher)`, embedding `pgvector` sur `(title || publisher || section)` pour `search_source`
- Contraintes : `verified_by != captured_by` (workflow 4-yeux), `publication_status` cohérence
- Trigger : empêcher passage `published` si sources non `verified`

## Critères d'acceptation

- [ ] Table `sources` créée avec tous les champs spécifiés et workflow 4-yeux fonctionnel
- [ ] 30+ sources `verified` seedées dans la BDD pour ADEME, IPCC, IEA, UEMOA, BCEAO, GCF, IFC, BOAD, Gold Standard, Verra, ODD ONU
- [ ] `EMISSION_FACTORS` migré en table `emission_factors` avec FK source vers ADEME/IPCC
- [ ] `ESGCriterion` migré en `indicators` avec FK vers source UEMOA/IFC selon contexte
- [ ] Constantes simulateur migrées en `simulation_factors`
- [ ] Tools `cite_source`, `search_source`, `flag_unsourced` implémentés et exposés à tous les nœuds qui produisent des chiffres
- [ ] Validation backend qui rejette une réponse LLM contenant un chiffre sans `cite_source` correspondant (avec retry et fallback texte)
- [ ] Composants `SourceLink`, `SourceModal`, `SourceBadge`, `SourcesList` implémentés
- [ ] Pictos Source intégrés sur ≥ 80 % des chiffres affichés (audit visuel sur dashboard, ESG, carbon, credit, financing, applications)
- [ ] Page `/sources` PME read-only fonctionnelle (filtres, recherche)
- [ ] Annexe "Sources et références" auto-générée dans le rapport ESG PDF
- [ ] Tests unitaires : couverture ≥ 80 % sur `sources/service.py`, `sourcing_tools.py`, validation middleware
- [ ] Test E2E Playwright : un fund officer peut cliquer sur un score ESG, voir le détail source, ouvrir le document officiel, lire le statut "vérifiée"
- [ ] Test eval LLM : 10 cas du golden set vérifient que le LLM invoque `cite_source` quand il affirme un chiffre

## Risques & garde-fous

- **Risque** : la regex de détection de chiffres est trop laxiste/stricte → faux positifs ou faux négatifs sur la validation. **Garde-fou** : iter sur un golden set de 50 réponses LLM annotées, ajuster la regex, tolérer un seuil d'erreur de 5 %.
- **Risque** : le LLM se met à invoquer `flag_unsourced` systématiquement pour éviter le rejet → contournement du sourçage. **Garde-fou** : surveiller le taux d'unsourced flags dans les métriques admin (Module 9.4) ; alert si > 20 %.
- **Risque** : le seed initial de 30 sources est insuffisant pour couvrir les chiffres affichés → l'application devient inutilisable. **Garde-fou** : phase pilote avec validation humaine quotidienne pendant 2 semaines, ajout itératif de sources.
- **Risque** : les utilisateurs PME pourraient être déstabilisés par des "sources non vérifiées" affichées partout. **Garde-fou** : interdire l'affichage public de sources `pending` ou `draft` (filtrer côté backend, retourner 404 sur `/api/sources/{id}` si non `verified` et user n'est pas admin).
- **Risque** : performance de `search_source` avec embeddings sur catalogue de 1000+ sources. **Garde-fou** : index HNSW sur pgvector + limit hard à 5 résultats + cache Redis post-MVP.
