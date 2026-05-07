# Feature Specification: F17 — Carbone Mix UEMOA + Facteurs ADEME/IPCC Sourcés + Catégorie Achats

**Feature Branch**: `feat/F17-carbone-mix-uemoa-source` (alias SpecKit `024-carbone-mix-uemoa-source`)
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "F17 — Migration des facteurs d'émission carbone codés en dur (Python) vers la table BDD `emission_factors` créée par F01, avec sourçage obligatoire (ADEME Base Carbone v23, IPCC AR6 WG3, IEA Africa Energy Outlook 2024). Couverture du mix électrique des 8 pays UEMOA, refactor `CarbonEmissionEntry` pour FK `source_id` + `factor_id`, ajout d'une catégorie « Achats » (matières premières), service `get_emission_factor(category, country, year)` avec priorité pays/année, plan de réduction sourcé, composant Vue `<EmissionFactorBadge>`, intégration `<SourceLink>` sur chaque facteur affiché."

## Clarifications

### Session 2026-05-07

- Q: L'année du facteur d'émission est-elle stockée dans le `code` (snake_case) ou dans une colonne `year` Integer dédiée ajoutée à `emission_factors` ? → A: **Colonne `year: Integer NOT NULL` ajoutée par migration Alembic F17**, plus une contrainte `UNIQUE (category, country, year)` (réécrit `H2` ; rationale : interrogation BDD efficace + index composite, évite parsing fragile de chaîne).
- Q: Pour la conversion FCFA → tonnes/litres dans la catégorie Achats, utilise-t-on `simulation_factors` (F01) ou des entrées dédiées `prices_*` dans `emission_factors` ? → A: **`simulation_factors` (F01)** — réutilise la table existante prévue pour les conversions monétaires/économiques, conserve `emission_factors` strictement aux facteurs d'émission physiques.
- Q: Stratégie de backfill pour les `carbon_emission_entries` historiques (créées avant F17) qui n'ont ni `source_id` ni `factor_id` ? → A: **Matching strict par `subcategory` ↔ `emission_factors.code`** ; si pas de match, lier à un facteur générique global de la catégorie + une `Source` legacy ADEME générique (déjà seedée par F01) ; la migration log les entries non matchées sans bloquer.
- Q: Format JSON canonique d'une action dans `reduction_plan` ? → A: `{title: str, description: str, estimated_reduction_tco2e: float, cost_estimate_fcfa: int|null, timeline: str, source_id: str|null, unsourced: bool}`. `source_id` est optionnel (UUID string ou null), `unsourced: true` quand pas de source.
- Q: Sort de la colonne `source_description: String(500)` actuelle après ajout de `source_id` + `factor_id` NOT NULL ? → A: **Conservée comme colonne nullable legacy au plus 2 sprints** (pas de renommage, pas de drop dans cette migration F17) ; suppression planifiée dans une migration ultérieure post-stabilisation. Cette stratégie respecte la décision orchestrateur « Conserver legacy `_deprecated` 2 sprints ».

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Mix électrique pays-spécifique pour le calcul carbone (Priority: P1)

Une PME ivoirienne renseigne sa consommation électrique dans le calculateur d'empreinte carbone. Le facteur d'émission utilisé est celui du mix électrique 2024 de la Côte d'Ivoire (~0,456 kgCO2e/kWh), pas une valeur générique mondiale. Une PME sénégalaise réalisant le même bilan voit, pour la même quantité de kWh, une empreinte différente, basée sur le mix sénégalais (~0,540 kgCO2e/kWh). Le facteur appliqué est cité avec sa source et l'utilisateur peut cliquer dessus pour vérifier l'origine (ADEME, IEA Africa, etc.).

**Why this priority** : La crédibilité scientifique du calcul carbone repose sur la pertinence géographique des facteurs. Aujourd'hui, un seul facteur électricité (`electricity_ci` à 0,41 kgCO2e/kWh) est codé en dur ; toutes les PME UEMOA utilisent la même valeur, ce qui fausse les bilans. Sans cette user story, le calculateur n'a pas de valeur scientifique réelle pour 7 des 8 pays UEMOA.

**Independent Test** : Créer deux profils PME (un en Côte d'Ivoire, un au Sénégal), saisir 1000 kWh de consommation électrique annuelle dans chacun, vérifier que les tCO2e calculés sont distincts (env. 0,456 t pour CI vs 0,540 t pour SN), et que le badge facteur affiche bien la source pays-spécifique cliquable.

**Acceptance Scenarios** :

1. **Given** un profil PME avec `country = "CI"` et un bilan carbone 2026, **When** la PME saisit 1000 kWh d'électricité, **Then** le facteur retenu est celui d'`electricity` pays `CI` année 2026 (ou la plus récente ≤ 2026), la valeur affichée est `~0.456 kgCO2e/kWh`, l'entrée stockée référence `factor_id` et `source_id` non nuls, et la source est ADEME Base Carbone v23 ou IEA Africa Energy Outlook 2024.
2. **Given** un profil PME avec `country = "SN"` et un bilan 2026, **When** la PME saisit 1000 kWh d'électricité, **Then** le facteur retenu est celui d'`electricity` pays `SN`, la valeur diffère de celle de CI, et l'entrée référence un `factor_id` distinct du scénario 1.
3. **Given** un profil PME avec `country = "TG"` et aucun facteur électricité Togo 2026 disponible, **When** la PME saisit 1000 kWh, **Then** le système retourne le facteur Togo de l'année antérieure la plus récente (par exemple 2024), affiche un libellé « approximatif » et conserve le sourçage.
4. **Given** un profil PME sans pays renseigné, **When** la PME saisit 1000 kWh, **Then** le système applique un facteur global (pays NULL) avec sourçage IEA Africa Energy Outlook ou équivalent, et l'UI signale « facteur générique régional » via le badge.

---

### User Story 2 — Sourçage cliquable sur chaque facteur dans le chat et l'UI carbone (Priority: P1)

Quand l'assistant IA présente un calcul d'empreinte carbone à l'utilisateur, chaque facteur d'émission affiché dans le chat ou sur la page `/carbon/results` est accompagné d'un picto Source cliquable (composant `<SourceLink>` introduit par F01). Le clic ouvre une modale `<SourceModal>` montrant le titre du document, l'éditeur, la version, la date de publication, la page exacte, le statut de vérification, et un lien vers la source originale. Aucun chiffre carbone n'apparaît sans source vérifiable.

**Why this priority** : L'invariant projet n°1 (« Sourçage obligatoire » introduit par F01) impose que tout chiffre, score ou facteur affiché soit lié à une source `verified` via le tool `cite_source`. Tant que les facteurs carbone restent codés en Python sans FK vers `sources`, le validator `source_required` ne peut pas valider les réponses LLM du module carbone et celui-ci viole l'invariant.

**Independent Test** : Lancer une conversation où l'utilisateur déclare une consommation électrique, observer dans le chat que le facteur affiché (par exemple « 0,456 kgCO2e/kWh ») est entouré d'un pictogramme cliquable, cliquer dessus, vérifier que la modale présente bien la source ADEME/IEA avec page et date, et que ces données proviennent de la table `sources` (statut `verified`).

**Acceptance Scenarios** :

1. **Given** un calcul carbone affichant un détail par catégorie dans le chat, **When** l'utilisateur survole/clique sur le picto Source à côté du facteur électricité, **Then** une modale s'ouvre montrant publisher (ADEME / IEA), version, page, date, statut et URL cliquable.
2. **Given** la page `/carbon/results` listant les entrées d'émission d'un bilan, **When** l'utilisateur consulte le détail d'une entrée, **Then** chaque ligne affiche le composant `<EmissionFactorBadge>` qui combine le label du facteur, la valeur, l'unité et le `<SourceLink>` cliquable.
3. **Given** un facteur dont la source est passée au statut `outdated`, **When** la PME consulte un bilan antérieur, **Then** le badge affiche un indicateur visuel « source dépréciée » mais conserve la traçabilité (la PME voit le facteur historique réellement utilisé pour ce bilan, pas le nouveau).
4. **Given** une réponse LLM générée par le `carbon_node`, **When** un chiffre d'émission y apparaît, **Then** la réponse contient un appel `cite_source(source_id)` correspondant et passe la validation `source_required` (sinon retry/fallback).

---

### User Story 3 — Catégorie Achats (matières premières) intégrée au bilan (Priority: P2)

L'utilisateur indique au chat qu'il a acheté plusieurs tonnes de ciment et d'acier durant l'année. L'assistant reconnaît la catégorie « Achats » (`purchases_*`), pose les questions adaptées (volumes en tonnes ou montants FCFA avec ratios par défaut), enregistre les entrées avec les sous-catégories `purchases_cement`, `purchases_steel`, etc., et inclut ces émissions dans le total tCO2e du bilan.

**Why this priority** : Le brainstorming Module 4 cite explicitement quatre catégories : Énergie, Transport, Déchets, Achats. La catégorie Achats est aujourd'hui complètement absente du modèle, ce qui sous-estime systématiquement l'empreinte des PME industrielles, du BTP et du commerce. C'est P2 car les 3 catégories existantes restent fonctionnelles sans elle.

**Independent Test** : Démarrer un bilan, saisir « j'ai acheté 50 tonnes de ciment cette année », observer que le LLM appelle `save_emission_entry` avec `category = "purchases"` et `subcategory = "purchases_cement"`, vérifier que l'entrée est stockée, que le total du bilan augmente du bon nombre de tCO2e, et que la page `/carbon/results` affiche la catégorie Achats dans la ventilation.

**Acceptance Scenarios** :

1. **Given** un bilan en cours, **When** la PME déclare « 50 tonnes de ciment achetées en 2026 », **Then** le LLM enregistre une entrée `category="purchases"`, `subcategory="purchases_cement"`, `quantity=50`, `unit="t"`, avec le facteur ciment (ADEME, ~0,9 kgCO2e/kg de ciment ≈ 900 kgCO2e/t), `factor_id` et `source_id` renseignés.
2. **Given** une PME qui ne connaît pas le tonnage exact mais le montant en FCFA, **When** elle déclare « j'ai dépensé 5 millions FCFA en ciment », **Then** le LLM applique un ratio de conversion par défaut (ex. prix ciment FCFA/tonne) et enregistre l'estimation, avec un libellé « valeur estimée » et la source du ratio.
3. **Given** un bilan avec entrées Achats, **When** l'utilisateur consulte `/carbon/results`, **Then** la ventilation par catégorie inclut « Achats » avec le total tCO2e, le pourcentage et la liste des sous-catégories (`purchases_cement`, `purchases_steel`, etc.).
4. **Given** une PME du secteur tertiaire (services), **When** elle commence un bilan, **Then** la catégorie Achats reste optionnelle (non bloquante) ; l'assistant la propose mais ne la rend pas obligatoire.

---

### User Story 4 — Plan de réduction sourcé (Priority: P3)

À la fin du bilan, l'assistant propose un plan de réduction (par exemple « passer au solaire », « optimiser la flotte », « gérer les déchets »). Chaque action recommandée référence une source documentaire (ADEME, IEA, BOAD policies, GCF, etc.) qui justifie le potentiel de réduction annoncé. Dans l'UI, chaque action est accompagnée d'un `<SourceLink>` cliquable.

**Why this priority** : Aujourd'hui, le plan de réduction est généré par le LLM sans sourçage. Cette user story est P3 car elle n'est pas bloquante pour la validité du calcul, mais elle est nécessaire à terme pour respecter l'invariant n°1 sur l'ensemble du module.

**Independent Test** : Finaliser un bilan, observer le plan de réduction généré, vérifier que chaque action a un `source_id` non null et un `<SourceLink>` cliquable dans `/carbon/results`.

**Acceptance Scenarios** :

1. **Given** un bilan finalisé, **When** le `reduction_plan` est généré, **Then** chaque action contient un champ `source_id` référençant une `Source` `verified` (ADEME guides, IEA reports, BOAD politiques sectorielles).
2. **Given** la page `/carbon/results` avec un plan de réduction, **When** l'utilisateur consulte une action, **Then** un `<SourceLink>` cliquable apparaît à côté de la justification et de l'estimation de réduction.
3. **Given** une action de réduction sans source disponible, **When** elle est générée, **Then** elle est marquée explicitement comme « recommandation générale (non sourcée) » plutôt que de citer une source factice.

---

### Edge Cases

- **Pays non couvert dans le seed initial** : si la PME déclare un pays non UEMOA (ex. Cameroun, Maroc), le service retombe sur le facteur global (pays « global ») avec un libellé « facteur régional approximatif ». Ne jamais bloquer le bilan.
- **Année future** : si la PME demande un bilan pour 2027 mais que les facteurs ne dépassent pas 2024, le service prend le facteur le plus récent disponible (≤ année demandée) et signale au LLM via le résultat du tool que la valeur peut être « légèrement datée ».
- **Sous-catégorie inconnue dans la table** : si le LLM appelle `save_emission_entry` avec une `subcategory` qui n'a aucun équivalent dans `emission_factors` (ex. `purchases_exotic_material`), le tool retourne une erreur explicite et propose au LLM de reformuler ou d'utiliser une catégorie générique « purchases_other » sourcée.
- **Concurrence sur le seed** : si l'admin relance le seed alors qu'un facteur a déjà été utilisé dans une entrée existante, le seed est idempotent (clé unique sur `code`) et ne supprime / n'écrase pas les facteurs déjà liés.
- **Source vérifiée puis dépréciée** : si une source ADEME passe en statut `outdated` après publication d'un bilan, les bilans existants conservent leur `source_id` et `factor_id` (snapshot) ; seul le futur calcul appliquera la nouvelle source si l'admin a publié une remplaçante.
- **Migration des entries historiques** : pour les `carbon_emission_entries` créées avant F17, la migration backfill associe chaque ligne au facteur le plus probable (matching `subcategory` dans le seed) et utilise une source « legacy » spéciale sourcée « migration F17 » ou la source ADEME équivalente déjà seedée.
- **Validator post-tour** : si le LLM génère un chiffre d'émission sans appeler `cite_source`, le validator `source_required` (F01) déclenche un retry, puis substitue par un fallback texte « [je ne dispose pas d'une source vérifiée pour ce chiffre] ».
- **Absence de profil entreprise** : si la PME n'a pas encore complété son profil et donc n'a pas de `country`, le service applique le facteur global et le LLM invite la PME à compléter son profil pour affiner le calcul.

## Requirements *(mandatory)*

### Functional Requirements

#### Donnée de référence (catalogue F01)

- **FR-001** : Le système DOIT peupler la table `emission_factors` (créée par F01) avec entre 27 et 50 lignes initiales couvrant : 8 facteurs `electricity` pour les 8 pays UEMOA (CI, SN, BF, ML, NE, BJ, TG, GW) — année minimale 2024, 3 facteurs combustibles globaux (`fuel_diesel`, `fuel_gasoline`, `fuel_butane`), 4 facteurs `transport_personal` (essence, diesel, hybride, électrique), 3 facteurs `transport_freight` (camion léger, camion lourd, fluvial), 3 facteurs déchets (`waste_landfill`, `waste_incineration`, `waste_compost`), 6 facteurs achats matières premières (`purchases_steel`, `purchases_cement`, `purchases_paper`, `purchases_food`, `purchases_plastic`, `purchases_other`). Le décompte exact final (~50) inclut des variantes années antérieures (2023) sur certaines catégories pour permettre la priorité fallback du service `get_emission_factor`.
- **FR-002** : Chaque ligne de `emission_factors` DOIT référencer une `Source` `verified` ou `pending` parmi : ADEME Base Carbone v23, IPCC AR6 WG3, IEA Africa Energy Outlook 2024 (sources déjà seedées par F01).
- **FR-003** : Chaque ligne DOIT contenir : `code` unique (snake_case `<category>_<country|global>_<year>`), `category`, `country` (code ISO 2 lettres ou « global »), `year` (Integer ; ajouté par migration F17), `value` (décimal), `unit`, `source_id` non null, `publication_status` `published`. Une contrainte `UNIQUE (category, country, year)` est ajoutée.
- **FR-004** : Le seed DOIT être idempotent — relancer le seed ne crée pas de doublons (clé unique composite `(category, country, year)` + clé unique sur `code`).

#### Modèle métier

- **FR-005** : Le modèle `CarbonEmissionEntry` DOIT être étendu avec `source_id: UUID FK sources.id NOT NULL` et `factor_id: UUID FK emission_factors.id NOT NULL`.
- **FR-006** : Le champ `source_description: String(500)` (texte libre) DOIT être conservé tel quel comme colonne nullable legacy au plus 2 sprints (pas de renommage, pas de drop dans la migration F17). La suppression est planifiée dans une migration ultérieure post-stabilisation.
- **FR-007** : La création d'une `CarbonEmissionEntry` SANS `source_id` ni `factor_id` DOIT être rejetée (contrainte NOT NULL en BDD + validation Pydantic côté service).
- **FR-008** : Le système DOIT exposer une migration Alembic réversible (up/down) qui ajoute les colonnes en NULL, peuple le backfill via matching strict `subcategory` ↔ `emission_factors.code` ; pour les entries non matchées, lie au facteur générique global de la catégorie + une `Source` legacy ADEME générique (déjà seedée par F01) ; les entries totalement non-matchables (catégorie inconnue) sont loguées sans bloquer ; puis applique la contrainte NOT NULL en deuxième temps.

#### Service de sélection

- **FR-009** : Le système DOIT fournir un service `get_emission_factor(category, country, year)` qui sélectionne le facteur selon la priorité : (1) pays exact + année exacte, (2) pays exact + année antérieure la plus récente, (3) global + année exacte, (4) global + année antérieure la plus récente.
- **FR-010** : Le service DOIT lever une exception explicite si aucun facteur n'est trouvé (la catégorie est inconnue dans le catalogue), permettant au tool LangChain de retourner un message d'erreur compréhensible.
- **FR-011** : Le service DOIT marquer dans son retour si le facteur est « approximatif » (cas pays non couvert, ou année antérieure de plus de 3 ans à la demande), pour que le LLM puisse en informer l'utilisateur.

#### Catégorie Achats

- **FR-012** : Le système DOIT reconnaître la catégorie `purchases` (et ses sous-catégories `purchases_steel`, `purchases_cement`, `purchases_paper`, `purchases_food`, `purchases_plastic`, `purchases_other`) dans le modèle `CarbonEmissionEntry` (élargissement de la liste `VALID_CATEGORIES`).
- **FR-013** : Le système DOIT permettre la conversion FCFA → tonnes via des ratios sourcés stockés dans la table `simulation_factors` (créée par F01). On ne pollue pas `emission_factors` avec des valeurs économiques. Le tool `save_emission_entry` interroge `simulation_factors` pour les conversions monétaires quand l'utilisateur fournit un montant.
- **FR-014** : La page `/carbon/results` DOIT afficher la catégorie « Achats » dans la ventilation par catégorie quand des entrées `purchases_*` existent.

#### Tools LangChain et prompts

- **FR-015** : Le tool LangChain `save_emission_entry` DOIT être refactoré pour : (1) appeler `get_emission_factor(category, country_from_profile, year_from_assessment)`, (2) calculer les tCO2e avec le facteur retourné, (3) stocker `source_id` et `factor_id` dans l'entrée, (4) retourner ces deux IDs dans le JSON de résultat pour que le LLM puisse appeler `cite_source(source_id)` dans sa réponse.
- **FR-016** : Le prompt `CARBON_PROMPT` DOIT enseigner au LLM à : (1) lire le `country` du profil entreprise dans `company_context`, (2) appeler `cite_source(source_id)` pour chaque facteur affiché dans le texte, (3) reconnaître la catégorie Achats dans les questions, (4) demander confirmation à l'utilisateur si le facteur est marqué « approximatif ».

#### Plan de réduction sourcé

- **FR-017** : Le `reduction_plan` (champ JSON sur `CarbonAssessment`) DOIT contenir, pour chaque action recommandée, un objet conforme au schéma : `{title: str, description: str, estimated_reduction_tco2e: float, cost_estimate_fcfa: int|null, timeline: str, source_id: str|null, unsourced: bool}`. Le champ `source_id` (UUID string) référence une `Source` `verified` quand une source documentaire existe (ADEME guides, IEA roadmaps, BOAD policies).
- **FR-018** : Quand aucune source n'est disponible pour justifier une action, `source_id` est `null` et `unsourced` est `true`. Aucune source factice ne peut être citée.

#### Frontend

- **FR-019** : Un nouveau composant Vue `<EmissionFactorBadge>` DOIT être créé dans `frontend/app/components/` pour afficher une triple information : label du facteur, valeur + unité, et `<SourceLink>` cliquable. Il DOIT être réutilisable, paramétrable via props (`factor`, `source`, `label`), et compatible dark mode.
- **FR-020** : La page `/carbon/results` DOIT être mise à jour pour afficher `<EmissionFactorBadge>` (ou `<SourceLink>` minimal) sur chaque facteur du breakdown par catégorie, sur chaque entrée détaillée et sur chaque action du plan de réduction.
- **FR-021** : Le composant `<EmissionFactorBadge>` DOIT respecter les règles de dark mode (`bg-white dark:bg-dark-card`, `text-surface-text dark:text-surface-dark-text`, etc.) et les conventions ARIA.

#### Tests et qualité

- **FR-022** : La couverture de tests sur les fichiers ajoutés/modifiés DOIT être ≥ 80 %.
- **FR-023** : Un test de bout en bout (Playwright) DOIT vérifier le scénario : profil PME en CI → facteur électricité ≈ 0,456 ; profil PME en SN → facteur différent ; ajout d'un achat de ciment → catégorie `purchases_cement` reconnue + facteur appliqué ; `<SourceLink>` cliquable.

### Key Entities *(include if feature involves data)*

- **EmissionFactor (existante, étendue par F17)** : ligne du catalogue représentant un facteur d'émission pour une catégorie, un pays, une année et une source. Attributs clés : `code` (unique), `label`, `category`, `country` (code pays ISO 2 lettres ou « global »), **`year` (Integer NOT NULL — ajouté par migration F17, contrainte UNIQUE composite `(category, country, year)`)**, `value`, `unit`, `source_id` (FK obligatoire vers `Source`), `publication_status` (`draft`/`published`), `account_id` (NULL pour catalogue commun ; multi-tenant F02), `created_by_user_id`.
- **CarbonEmissionEntry (existante, refactorée)** : ligne d'émission individuelle d'un bilan. Modifications : ajout de `source_id` (FK obligatoire `sources.id`) et `factor_id` (FK obligatoire `emission_factors.id`). Le champ `source_description` (texte libre) est conservé temporairement (legacy) pour réversibilité.
- **CarbonAssessment (existante, étendue)** : aucun changement structurel, mais le champ JSON `reduction_plan` voit son schéma logique enrichi par `source_id` (UUID string) sur chaque action.
- **Source (existante F01)** : aucun changement, mais le seed F17 référence ces sources existantes (ADEME Base Carbone v23, IPCC AR6 WG3, IEA Africa Energy Outlook 2024) et peut en ajouter de nouvelles si nécessaire (ex. politiques sectorielles BOAD pour les actions de réduction).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : 100 % des facteurs d'émission utilisés par le module carbone proviennent de la table `emission_factors` (zéro lookup vers la constante Python `EMISSION_FACTORS`). Vérifiable via : `grep -r "EMISSION_FACTORS\[" backend/app/ --include="*.py" | grep -v "__pycache__\|test_"` doit retourner 0 occurrence dans le code de production après le refactor T023.
- **SC-002** : 100 % des `CarbonEmissionEntry` créées après déploiement F17 ont `source_id` et `factor_id` renseignés (vérifiable via une requête SQL retournant 0 ligne avec NULL).
- **SC-003** : Les 8 pays UEMOA ont chacun au moins un facteur électricité disponible pour l'année courante ou l'année précédente (8 lignes minimum dans `emission_factors` filtré sur `category='electricity'`).
- **SC-004** : Pour les 8 pays UEMOA (CI, SN, BF, ML, NE, BJ, TG, GW), un test paramétré (`pytest.mark.parametrize`) vérifie que la sélection de facteur électricité retourne le bon `factor.code` pour chaque pays (8 cas testés). Sur le bilan complet, 100 % des saisies électricité d'une PME UEMOA utilisent le facteur de son pays exact.
- **SC-005** : 100 % des facteurs affichés dans le chat ou sur `/carbon/results` ont un `<SourceLink>` cliquable (vérifiable via le snapshot DOM des tests E2E Playwright).
- **SC-006** : Le validator `source_required` accepte 100 % des réponses LLM du `carbon_node` après F17 (zéro retry/fallback déclenché par un chiffre d'émission non sourcé), sur le golden_set existant.
- **SC-007** : La couverture de tests sur les fichiers ajoutés/modifiés est ≥ 80 % (mesurée par pytest-cov côté backend, vitest --coverage côté frontend).
- **SC-008** : Aucun bilan carbone existant n'est cassé après la migration (tous les bilans antérieurs sont accessibles, lisibles, leurs entries ont un `source_id` valide via le backfill).
- **SC-009** : Le test E2E Playwright `F17-carbone-mix-uemoa-source.spec.ts` passe à 100 %, validant les 4 scénarios principaux (CI électricité, SN électricité, ciment Achats, SourceLink cliquable).

## Assumptions

### Décisions de scope (Phase A clarifications)

- **A1** : Le seed initial cible **8 pays UEMOA** (Côte d'Ivoire CI, Sénégal SN, Burkina Faso BF, Mali ML, Niger NE, Bénin BJ, Togo TG, Guinée-Bissau GW). Les autres pays africains francophones (Cameroun, Congo, etc.) tombent en fallback sur le facteur global, à élargir post-MVP.
- **A2** : Sources prioritaires : **ADEME Base Carbone v23** (combustibles, transport, déchets, achats — gratuit et contient facteurs Afrique), **IPCC AR6 WG3** (déchets, méthane), **IEA Africa Energy Outlook 2024** (mix électrique pays UEMOA). Toutes ces sources sont déjà seedées par F01 en statut `verified`.
- **A3** : Migration `EMISSION_FACTORS` Python → table BDD via **seed admin** (dédié à F17), pas via `app/scripts/` directement utilisateur. La fonction de seed est idempotente et se lance via une commande dédiée ou pendant la migration Alembic elle-même (fixture initiale).
- **A4** : Sur `CarbonEmissionEntry`, on ajoute `source_id` + `factor_id` **NOT NULL**. Le champ `source_description` (texte libre) est conservé en legacy au plus 2 sprints pour permettre une réversibilité de la migration (puis supprimé dans une migration ultérieure non couverte par F17). Cette stratégie respecte la décision par défaut de l'orchestrateur (« Conserver legacy `_deprecated` 2 sprints »).
- **A5** : Le service `get_emission_factor(category, country, year)` applique la priorité **pays exact + année exacte > pays + année antérieure > global + année exacte > global + antérieure**. Si rien n'est trouvé → exception explicite (le tool LangChain retourne une erreur lisible).
- **A6** : Le **plan de réduction** voit chaque action enrichie d'un `source_id` (UUID string) optionnel ; quand pas de source, l'action est marquée `unsourced: true`. Cette structure JSON ne modifie pas le schéma SQL.
- **A7** : Le composant Vue `<EmissionFactorBadge>` est créé dans `frontend/app/components/` (pas dans `ui/`) car il combine un facteur + une source et n'est pas générique au sens « bouton/input ».
- **A8** : Le LLM (`carbon_node`) lit le `country` depuis `company_context` injecté dans le prompt (champ déjà disponible via le profil entreprise) et le passe au tool `save_emission_entry` ; le tool ne tente pas de deviner le pays autrement (pas de géolocalisation IP).

### Hypothèses techniques

- **H1** : La table `emission_factors` est étendue par F17 d'une colonne `year: Integer NOT NULL` (migration Alembic dédiée). Les autres colonnes restent comme dans F01 (`code`, `label`, `category`, `country`, `value`, `unit`, `source_id`, `publication_status`, `account_id`, `created_by_user_id`). On utilise `country` (pas `country_code`) comme nom de colonne pour rester cohérent avec F01.
- **H2** : L'année est stockée dans une colonne dédiée `year: Integer NOT NULL` (clarification Q1 du 2026-05-07). Le service `get_emission_factor` interroge la BDD avec un index composite `(category, country, year)`. Cette décision améliore les performances de lookup et évite le parsing de chaîne.
- **H3** : La cohérence multi-tenant est assurée par F02 (RLS) ; les facteurs `emission_factors` ont `account_id NULL` (catalogue commun) et restent accessibles en lecture à toutes les PME, comme le sont les autres entités catalogue F01.
- **H4** : Le tool `cite_source` (F01) est déjà dans la `GLOBAL_WHITELIST` du `carbon_node`. Il n'y a pas besoin d'ajouter ce tool ; on s'assure simplement que le LLM l'appelle après chaque facteur affiché (via le prompt enrichi).
- **H5** : Les factors « approximatifs » sont signalés par un flag `is_approximate: bool` dans le retour du service `get_emission_factor` (en mémoire, pas en BDD). Ce flag est propagé au LLM via le résultat JSON du tool `save_emission_entry`, qui peut alors prévenir l'utilisateur.
- **H6** : Pour la conversion FCFA → tonnes (US3 scénario 2), on réutilise exclusivement la table `simulation_factors` de F01 (clarification Q2 du 2026-05-07). On ne pollue pas `emission_factors` avec des valeurs économiques. Le tool `save_emission_entry` interroge `simulation_factors` dès qu'un montant FCFA est fourni.
- **H7** : Le test E2E Playwright `F17-carbone-mix-uemoa-source.spec.ts` mocke le backend pour les scénarios déterministes (pas de vrai LLM en E2E), conformément à la convention projet « Mock par défaut, vrai LLM uniquement pour `tests/llm_eval/` ».
- **H8** : Les valeurs concrètes des facteurs (par exemple `electricity_ci_2024 = 0.456`) sont déterminées au moment de la rédaction du seed et basées sur les sources publiques ADEME/IEA. Les valeurs précises sont inscrites dans la migration/seed et documentées dans `data-model.md` (Phase Plan).
- **H9** : La numérotation SpecKit attribuée par le script (`024-carbone-mix-uemoa-source`) entre potentiellement en collision avec d'autres features développées en parallèle (notamment F12 qui peut aussi recevoir le numéro 021 sur sa propre branche, F03/F04 qui pourraient prendre 021/022/023). L'orchestrateur résoudra la collision avant Phase B en renommant le dossier spec et la migration Alembic. La branche git réelle reste `feat/F17-carbone-mix-uemoa-source`.

### Hors-scope (post-MVP, exclus de F17)

- **HS1** : Mix électrique horaire (variations selon heure de consommation) — repoussé post-MVP.
- **HS2** : Facteurs custom par PME validés par admin — repoussé post-MVP (workflow d'approbation hors scope).
- **HS3** : Détection automatique du pays via géolocalisation IP — repoussé post-MVP.
- **HS4** : Calcul Scope 3 complet (achats indirects upstream/downstream chaîne d'approvisionnement) — F17 couvre uniquement les achats directs déclarés (Scope 3.1 simplifié).
- **HS5** : Reporting GHG Protocol formel — repoussé post-MVP.
- **HS6** : Intégration plateformes carbone Verra / Gold Standard pour compensation — repoussé post-MVP.

### Risques connus et garde-fous (rappel)

- **R1** : Facteurs ADEME pas tous applicables à l'Afrique. **Garde-fou** : prioriser IEA Africa Energy Outlook pour mix électrique, ADEME pour le reste. Documenté dans `data-model.md` (Phase Plan).
- **R2** : Données pays manquantes pour certains pays UEMOA. **Garde-fou** : fallback sur année antérieure ou facteur global, signal explicite « approximatif » via `is_approximate`.
- **R3** : Changement de version ADEME casse les anciens calculs. **Garde-fou** : `factor_id` snapshot sur les entries (le facteur utilisé au moment du calcul est conservé) ; les nouveaux bilans utilisent la version courante.
- **R4** : Migration backfill peut être longue sur des bases existantes volumineuses. **Garde-fou** : la migration commence par ajouter les colonnes en NULL, fait le backfill par lot, puis applique la contrainte NOT NULL ; testée up/down/up.
