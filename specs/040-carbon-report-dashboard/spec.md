# Feature Specification: F21 — Dashboard par Offre + Carte Intermédiaires + Rapport Carbone PDF

**Feature Branch**: `feat/F21-dashboard-par-offre-rapport-carbone`
**Spec Number**: 040
**Created**: 2026-05-08
**Status**: Draft
**Input**: F21 — Compléter le dashboard PME (granularité par Offre Fonds×Intermédiaire, carte UEMOA des intermédiaires actifs, scores cliquables vers sources F01) et créer un rapport carbone PDF parallèle au rapport ESG F06.

## Clarifications

### Session 2026-05-08

- Q: Mode de clarification autonome (Recommended/defaults) — toutes les catégories du scan d'ambiguïté ressortent Clear. → A: Aucune ambiguïté critique détectée ; spec prête pour `/speckit.plan`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Cards de candidatures par Offre sur le dashboard (Priority: P1)

En tant que PME, je veux voir sur mon tableau de bord une carte distincte par candidature active (granularité par Offre = couple Fonds × Intermédiaire), affichant l'étape courante, la prochaine échéance et le prochain rappel. Au lieu d'un compteur global « 3 candidatures soumises », je veux 3 cards : (1) GCF via BOAD — étape « Instruction » — J-15 ; (2) SUNREF via Ecobank — étape « Préparation dossier » — sans deadline ; (3) FEM via PNUD — étape « Dossier déposé » — attente.

**Why this priority** : visibilité immédiate du portefeuille de candidatures, hiérarchisation des actions PME, complétion du Module 7.1 (Dashboard Principal) attendu par les utilisateurs depuis F11.

**Independent Test** : peut être testée en créant 3 candidatures actives liées à 3 offres distinctes pour un compte PME et en vérifiant que `/dashboard` affiche 3 cards avec les noms de fonds, d'intermédiaires, statuts et deadlines corrects, sans toucher au reste de la feature.

**Acceptance Scenarios** :

1. **Given** une PME avec 3 candidatures actives liées à 3 offres distinctes, **When** elle ouvre `/dashboard`, **Then** elle voit 3 cards `<ApplicationStatusCard>` avec `fund_name`, `intermediary_name`, statut traduit en libellé d'étape, `next_deadline` au format `DD/MM/YYYY` ou « Aucune échéance » si null.
2. **Given** une PME avec 7 candidatures actives, **When** elle ouvre `/dashboard`, **Then** seules les 5 premières cards (triées par `last_activity_at` desc) sont affichées avec un lien « Voir toutes mes candidatures ».
3. **Given** une PME sans candidature, **When** elle ouvre `/dashboard`, **Then** la section affiche un état vide avec lien vers le catalogue d'offres.
4. **Given** une PME, **When** elle clique sur le bouton « Voir détail » d'une card, **Then** elle est redirigée vers la fiche de la candidature correspondante.

---

### User Story 2 — Rapport Carbone PDF téléchargeable avec annexe Sources (Priority: P1)

En tant que PME ayant finalisé un bilan carbone, je veux générer un rapport PDF complet (synthèse, breakdown par catégorie, comparaison sectorielle, plan de réduction, équivalences pédagogiques, méthodologie, annexe sources) que je peux télécharger et présenter à un financeur. Tous les chiffres doivent être traçables à une source vérifiée (F01).

**Why this priority** : promesse explicite du Module 7.2 (Rapports) jamais livrée. Sans ce livrable, la valeur perçue du module Carbone reste limitée et la PME ne peut pas valoriser son bilan auprès des fonds verts.

**Independent Test** : peut être testée en finalisant un bilan carbone, en cliquant sur « Générer rapport carbone PDF », en téléchargeant le PDF produit et en vérifiant la présence des 9 sections, des chiffres avec sources cliquables et de l'annexe « Sources et références » auto-générée.

**Acceptance Scenarios** :

1. **Given** une PME avec un bilan carbone finalisé, **When** elle clique sur « Générer rapport carbone PDF » sur `/carbon/results`, **Then** un job de génération asynchrone démarre, un message « Rapport en cours de génération » s'affiche et un toast la notifie quand le PDF est prêt.
2. **Given** un PDF carbone généré, **When** la PME le télécharge et l'ouvre, **Then** elle trouve les 9 sections (Cover, Synthèse, Breakdown, Comparaison sectorielle, Évolution multi-années, Plan de réduction, Équivalences, Méthodologie, Annexe Sources) avec dates en `DD/MM/YYYY`.
3. **Given** un PDF carbone généré, **When** la PME consulte la section Synthèse, **Then** chaque chiffre clé (empreinte totale tCO2e, intensité, scope 1/2/3) est suivi d'une référence numérotée `[n]` qui pointe vers une entrée de l'annexe Sources avec libellé, éditeur, version, date et URL.
4. **Given** un PDF carbone généré, **When** la PME consulte la section Plan de réduction, **Then** chaque action chiffrée mentionne sa source ou la mention « Recommandation générale (non sourcée) ».
5. **Given** une PME sans bilan carbone finalisé, **When** elle tente de générer un rapport, **Then** le système refuse avec un message explicite et propose de finaliser le bilan d'abord.

---

### User Story 3 — Carte UEMOA des intermédiaires actifs (Priority: P2)

En tant que PME, je veux voir sur mon dashboard une carte de la zone UEMOA avec un marqueur par intermédiaire avec lequel j'ai une candidature ou un projet en cours. Au clic, le popup affiche le nom, le pays, le type, la liste des accréditations et le nombre de mes candidatures via cet intermédiaire, plus un lien vers sa fiche complète.

**Why this priority** : visualisation géographique attendue par le Module 7.1, mais utile uniquement quand au moins une candidature existe (donc dépendante du flux US1).

**Independent Test** : peut être testée en associant une PME à 2 intermédiaires actifs (BOAD/Lomé, PNUD/Abidjan) et en vérifiant que le dashboard affiche 2 marqueurs aux bonnes positions, avec popups complets et liens fonctionnels.

**Acceptance Scenarios** :

1. **Given** une PME avec 2 intermédiaires actifs aux coordonnées renseignées, **When** elle ouvre `/dashboard`, **Then** la carte UEMOA affiche 2 marqueurs aux coordonnées correctes avec l'overlay des 8 pays UEMOA.
2. **Given** un intermédiaire actif sans coordonnées (lat/lon manquantes), **When** la carte est rendue, **Then** le marqueur est positionné sur la capitale du `country` de l'intermédiaire (fallback documenté dans le popup).
3. **Given** une PME sans intermédiaire actif, **When** elle ouvre `/dashboard`, **Then** la section affiche le message « Vous n'avez pas encore d'intermédiaire actif » avec un lien vers `/financing/intermediaries`.
4. **Given** un marqueur intermédiaire, **When** la PME clique dessus, **Then** un popup s'ouvre avec `name`, `type`, `country`, accréditations, `applications_count`, et un bouton « Voir la fiche » qui mène à `/financing/intermediaries/{id}`.

---

### User Story 4 — Scores du dashboard cliquables vers leurs sources (Priority: P2)

En tant que PME, je veux que chaque score affiché en card du dashboard (ESG, carbone, crédit) soit cliquable et m'ouvre la modale détaillant les sources et la version du référentiel utilisé (F01 + F13).

**Why this priority** : exigence de transparence transverse héritée de F01. Améliore la confiance utilisateur sans bloquer les autres user stories.

**Independent Test** : peut être testée en chargeant le dashboard d'une PME ayant un score ESG finalisé, en cliquant sur l'icône source à côté du score, et en vérifiant que la modale s'ouvre avec la liste des sources F01 utilisées pour ce score.

**Acceptance Scenarios** :

1. **Given** une PME avec un score ESG finalisé, **When** elle ouvre `/dashboard`, **Then** la card score ESG affiche le chiffre suivi d'une icône source cliquable (composant `<SourceLink>` F01).
2. **Given** une PME, **When** elle clique sur l'icône source à côté du score, **Then** une modale `<SourceModal>` s'ouvre avec l'identité de la source, l'éditeur, la version, la date et l'URL.
3. **Given** un score sans source rattachée, **When** la card est rendue, **Then** un badge « Non sourcé » remplace l'icône source.

---

### User Story 5 — Rapports Carbone listés à côté des rapports ESG (Priority: P2)

En tant que PME, je veux retrouver mes rapports carbone PDF sur la page `/reports`, dans un onglet distinct des rapports ESG, et pouvoir les télécharger à nouveau.

**Why this priority** : extension naturelle de US2 — sans cette page, les rapports carbone seraient générés mais non re-téléchargeables. Faible coût après US2.

**Independent Test** : peut être testée en générant un rapport carbone (US2) puis en ouvrant `/reports`, en cliquant sur l'onglet « Carbone » et en re-téléchargeant le PDF.

**Acceptance Scenarios** :

1. **Given** une PME avec 2 rapports ESG et 1 rapport carbone, **When** elle ouvre `/reports`, **Then** elle voit deux onglets « ESG » et « Carbone » avec les compteurs (2/1) et la liste correspondante dans chaque onglet.
2. **Given** un rapport carbone listé, **When** la PME clique sur « Télécharger », **Then** le PDF s'ouvre/téléchargement démarre via l'endpoint de téléchargement existant.

---

### Edge Cases

- **Bilan carbone non finalisé** : tentative de génération de rapport → refus explicite avec instruction de finaliser le bilan.
- **Rapport en cours de génération** : un seul job actif par bilan à la fois — second clic sur « Générer » désactivé jusqu'à complétion ou erreur.
- **Erreur de génération PDF** : statut du `Report` passe à `failed` avec message d'erreur visible dans `/reports` et bouton « Réessayer ».
- **Sources F01 absentes** : si un chiffre ne dispose pas d'une source vérifiée, il est marqué « Recommandation générale (non sourcée) » ou substitué par le fallback texte du validator F01 ; aucun chiffre nu non sourcé ne paraît dans le PDF.
- **Intermédiaire sans coordonnées ni `country`** : marqueur omis et avertissement loggé côté serveur (ne casse pas le rendu de la carte).
- **PME avec 50+ candidatures actives** : page complète paginée (réutilise la liste existante) — le dashboard reste limité à 5 cards.
- **Rapport généré il y a 6 mois** : reste téléchargeable tant que le fichier physique existe ; sinon affiche « Fichier expiré, régénérer ».
- **Score sans `source_id`** mais issu d'un référentiel publié : afficher le badge `ReferentialBadge` (F13) sans `<SourceLink>` individuel.
- **Multi-tenant (F02)** : aucun rapport ni candidature d'un autre `account_id` ne doit apparaître, RLS garantit l'isolation.
- **Audit (F03)** : la génération de rapport carbone, l'accès au dashboard et le téléchargement du PDF sont tracés (action et `source_of_change` adéquats).

## Requirements *(mandatory)*

### Functional Requirements

#### Dashboard granularité par Offre

- **FR-001** : Le système MUST exposer pour chaque candidature active de la PME une vue carte contenant `application_id`, `offer_id`, `fund_name`, `intermediary_name`, logos optionnels, statut, libellé d'étape courante en français, prochaine échéance, prochain rappel, dernière activité.
- **FR-002** : Le dashboard MUST afficher au plus 5 cards triées par `last_activity_at` décroissant et MUST exposer un lien « Voir toutes mes candidatures » au-delà.
- **FR-003** : Le système MUST mapper le statut technique d'une candidature vers un libellé d'étape humain en français (par exemple `submitted_to_intermediary` → « Instruction par {intermédiaire} »).
- **FR-004** : Une candidature sans intermédiaire (accès direct) MUST afficher « Accès direct » comme valeur d'intermédiaire.

#### Carte intermédiaires actifs

- **FR-005** : Le système MUST exposer la liste des intermédiaires actifs pour la PME courante, c'est-à-dire ceux liés à au moins une candidature non clôturée OU à un projet ouvert. Chaque entrée MUST inclure identifiant, nom, type, pays, latitude, longitude, accréditations actives (noms de fonds), nombre de candidatures de la PME via cet intermédiaire.
- **FR-006** : Si un intermédiaire n'a pas de coordonnées renseignées, le système MUST utiliser comme fallback le centroïde de la capitale de son `country` (table de référence des 8 capitales UEMOA bundlée localement).
- **FR-007** : Le composant carte MUST afficher l'overlay GeoJSON UEMOA (réutilise l'asset F11), un marqueur par intermédiaire et un popup au clic conforme à US3 #4.
- **FR-008** : En l'absence d'intermédiaire actif, l'interface MUST afficher un état vide explicite avec lien vers l'annuaire.

#### Scores cliquables vers sources

- **FR-009** : Chaque score affiché sur le dashboard (ESG, carbone, crédit) MUST exposer à proximité une icône `<SourceLink>` cliquable conforme F01 lorsqu'au moins une source est rattachée au score.
- **FR-010** : Au clic sur l'icône source, le système MUST ouvrir la modale `<SourceModal>` (composant existant F01) avec les détails de la ou des sources.
- **FR-011** : Lorsqu'aucune source n'est rattachée à un score, le système MUST afficher un badge « Non sourcé » à la place de l'icône.

#### Rapport Carbone PDF

- **FR-012** : Le système MUST exposer un endpoint `POST /api/reports/carbon/{assessment_id}/generate` réservé aux PME propriétaires (auth + RLS F02) qui crée une ligne `Report` avec `report_type='carbon'` et déclenche un job asynchrone de génération.
- **FR-013** : Le job asynchrone MUST produire un PDF stocké dans `/uploads/reports/` réutilisant l'arborescence du module rapports F06 et MUST mettre à jour le statut du `Report` (`pending` → `generating` → `ready` ou `failed`).
- **FR-014** : Le PDF MUST contenir, dans cet ordre, 9 sections : (1) Couverture (logo plateforme, titre, identité PME, période d'évaluation), (2) Synthèse (empreinte totale tCO2e, intensité, scope 1/2/3 avec références sources), (3) Breakdown par catégorie (graphique secteur + tableau), (4) Comparaison sectorielle (barres horizontales), (5) Évolution multi-années si plusieurs bilans, (6) Plan de réduction (actions priorisées avec sources F01), (7) Équivalences pédagogiques (km voiture, vols, foyers, FCFA économisés), (8) Méthodologie (facteurs ADEME/IPCC/IEA utilisés), (9) Annexe « Sources et références » auto-générée numérotée.
- **FR-015** : Toutes les dates affichées dans le PDF MUST être au format `DD/MM/YYYY` (français).
- **FR-016** : Tous les chiffres (totaux carbone, intensités, équivalences, montants FCFA, valeurs de comparaison sectorielle) MUST être assortis d'une référence numérotée `[n]` pointant vers l'annexe sources, OU d'un libellé explicite « Recommandation générale (non sourcée) » lorsqu'aucune source vérifiée n'est disponible. Aucun chiffre nu sans sourçage ni mention explicite ne doit figurer dans le rapport.
- **FR-017** : Le système MUST refuser la génération si le bilan carbone n'est pas finalisé, avec un message explicite et un lien vers la finalisation.
- **FR-018** : Le système MUST empêcher la génération concurrente de deux rapports pour le même bilan (un seul job `generating` à la fois) ; tentatives répétées renvoient une réponse de conflit explicite.
- **FR-019** : Le téléchargement du PDF MUST réutiliser l'endpoint existant `GET /api/reports/{report_id}/download` (F06).
- **FR-020** : Le système MUST exposer un outil conversationnel (LangChain) `generate_carbon_report` permettant à l'assistant IA de déclencher la génération pour le bilan courant de la PME, avec retour structuré incluant l'identifiant du rapport et son statut.

#### Frontend `/reports` et `/carbon/results`

- **FR-021** : La page `/reports` MUST proposer deux onglets « ESG » et « Carbone » avec compteurs et listes dédiées (date, statut, action télécharger/régénérer).
- **FR-022** : La page `/carbon/results` MUST exposer un bouton « Générer rapport carbone PDF » désactivé si le bilan n'est pas finalisé ou si une génération est déjà en cours.

#### Audit log F03

- **FR-023** : Le dashboard MUST exposer une carte « Activité récente » résumant les N (par défaut 5) derniers événements d'audit du compte et un lien vers `/historique` (F03).

#### Endpoint `/api/dashboard/summary`

- **FR-024** : `GET /api/dashboard/summary` MUST retourner un objet contenant : `esg`, `carbon`, `credit`, `financing.applications_by_offer`, `financing.active_intermediaries`, `financing.next_deadlines`, `next_actions`, `recent_activity`, `badges`.
- **FR-025** : L'endpoint MUST honorer le multi-tenant F02 (RLS PostgreSQL) et n'exposer que les données du compte courant.

#### Sourçage et conformité

- **FR-026** : La génération du rapport carbone MUST s'appuyer sur le validator de sourçage F01 (`source_required.py`) pour rejeter ou substituer les chiffres non sourcés ; le tool conversationnel MUST en outre invoquer `cite_source` pour chaque chiffre clé du résumé conversationnel produit.
- **FR-027** : La génération du rapport, le téléchargement et la consultation du dashboard MUST être tracés dans l'audit log F03 avec `source_of_change` adapté (`manual` pour PME, `llm` lorsqu'invoqué par l'assistant via le tool).

#### Performance et observabilité

- **FR-028** : Le rendu du dashboard MUST renvoyer une réponse en moins de 2 secondes au 95e percentile pour une PME standard (≤ 20 candidatures actives, ≤ 10 intermédiaires actifs).
- **FR-029** : La génération PDF carbone MUST aboutir en moins de 10 secondes au 95e percentile pour un bilan standard (≤ 30 entrées d'émission, ≤ 5 années).

### Key Entities *(données existantes uniquement — aucune migration)*

- **Report** : entrée existante, étendue par usage (valeur `report_type='carbon'`). Sert de manifeste pour la génération asynchrone et le téléchargement.
- **CarbonAssessment** : bilan carbone source. Lecture seule pour la génération.
- **CarbonEmissionEntry** : entrées détaillées (catégorie, scope, source). Agrégation pour breakdown.
- **FundApplication** : candidature, exposée par offre via `offer_id` (F07).
- **Offer** : couple Fonds × Intermédiaire (F07). Source de vérité pour les libellés affichés sur les cards.
- **Intermediary** : entité accréditée. Champs `country`, `lat`, `lon` exploités pour la carte ; fallback capitale.
- **Source** (F01) : sources vérifiées rattachées aux scores et aux chiffres carbone.
- **AuditLog** (F03) : journal d'événements consommé par la carte « Activité récente ».
- **EmissionFactor** (F17) : facteurs sourcés référencés dans la méthodologie du PDF.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : Une PME avec 3 candidatures actives liées à 3 offres distinctes voit 3 cards distinctes sur le dashboard en moins de 2 secondes au 95e percentile.
- **SC-002** : 100 % des chiffres présentés dans le PDF carbone sont soit liés à une source vérifiée numérotée dans l'annexe, soit explicitement libellés « Recommandation générale (non sourcée) ».
- **SC-003** : La génération d'un rapport carbone aboutit en moins de 10 secondes au 95e percentile pour un bilan standard.
- **SC-004** : 100 % des intermédiaires actifs renseignés (avec coordonnées ou pays) apparaissent comme marqueurs sur la carte du dashboard pour la PME concernée ; les autres comptes voient zéro.
- **SC-005** : 100 % des scores ESG / carbone / crédit affichés en card sont soit cliquables vers leurs sources, soit explicitement marqués « Non sourcé ».
- **SC-006** : Toutes les générations de rapport carbone, accès au dashboard et téléchargements de PDF apparaissent dans l'audit log F03 avec `source_of_change` correct.
- **SC-007** : Aucune donnée d'un autre `account_id` ne fuite dans les réponses du dashboard ni dans la liste des rapports carbone (vérifié par tests RLS F02).
- **SC-008** : Couverture des tests automatisés sur le périmètre F21 ≥ 80 % (backend + frontend).
- **SC-009** : Le rapport carbone est téléchargeable depuis `/reports` (onglet Carbone) jusqu'à 30 jours après sa génération sans régénération.

## Assumptions

- **Aucune migration de schéma n'est requise** (`alembic_or_migration = false`). La feature lit les tables existantes et utilise la table `Report` et le stockage `/uploads/reports/` déjà en place.
- L'architecture du rapport carbone PDF reproduit celle du rapport ESG F06 (WeasyPrint + Jinja2 + matplotlib SVG + génération asynchrone via FastAPI BackgroundTasks).
- Les visualisations interactives du dashboard (KPICard, MatchCard, MapBlock, ComparisonTable) sont fournies par F11 et réutilisées sans modification.
- Les coordonnées géographiques des intermédiaires sont saisies via le back-office admin F09 et progressivement complétées ; le fallback capitale couvre les manques.
- Les capitales UEMOA utilisées en fallback proviennent d'une table de référence locale (8 entrées) bundlée dans le code applicatif, sans appel externe.
- Les facteurs d'émission sourcés (F17) sont déjà disponibles en base et alimentent la section Méthodologie.
- Le multi-tenant (F02) et l'audit log (F03) sont opérationnels et leurs hooks sont automatiquement déclenchés par les endpoints existants.
- Les équivalences pédagogiques affichées (km voiture, vols, foyers, FCFA économisés) reposent sur des facteurs sourcés F01 (cohérent avec F17) ; à défaut, un libellé « Recommandation générale (non sourcée) » est appliqué.
- Une PME possédant un bilan carbone finalisé peut générer un rapport ; l'absence de bilan finalisé est une condition bloquante explicite.
- La rétention des fichiers PDF générés dans `/uploads/reports/` suit la politique existante du module rapports F06 (≥ 30 jours).
- Le périmètre exclut explicitement le dashboard customisable, la comparaison période M-1, les notifications push browser, le cohort comparison, l'export PDF du dashboard et le partage public anonymisé.

## Dependencies

- **F01** : sources vérifiées + composants `<SourceLink>` / `<SourceModal>` + validator `source_required.py` + tool `cite_source`.
- **F02** : multi-tenant + RLS PostgreSQL.
- **F03** : audit log append-only + page `/historique`.
- **F06** : architecture rapport ESG PDF (WeasyPrint, Jinja2, matplotlib, BackgroundTasks).
- **F07** : entité Offer (couple Fonds × Intermédiaire).
- **F08** : attestations (helpers de signature/intégrité réutilisables si pertinents).
- **F09** : back-office admin (saisie progressive des coordonnées intermédiaires).
- **F11** : `<MapBlock>`, asset GeoJSON UEMOA, composants `<KPICardBlock>`, `<ComparisonTableBlock>`.
- **F13** : multi-référentiels et `<ReferentialBadge>` (lien depuis les scores cliquables).
- **F17** : facteurs d'émission sourcés UEMOA (méthodologie du rapport carbone).
