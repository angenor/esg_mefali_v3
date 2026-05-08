# Feature Specification: F18 — Mobile Money + Photos IA + Données Publiques (avec Consentements)

**Feature Branch**: `feat/F18-mobile-money-photos-ia-public-data` (numéro spec `037`)
**Created**: 2026-05-08
**Status**: Draft
**Input**: User description: F18 — Module 5.1 (Collecte de Données Non-Conventionnelles) avec 3 sources alternatives (Mobile Money, Photos IA, Données publiques) gardées par consentements granulaires F05, alimentant le scoring crédit vert (Module 5.2) et exposant une méthodologie publique sourcée.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Importer son historique Mobile Money pour enrichir son score crédit (Priority: P1)

Une PME informelle, sans comptabilité formelle, souhaite faire valoir la régularité de ses flux Mobile Money (Wave, Orange Money, MTN MoMo, Moov Money) auprès des financeurs. Elle exporte un fichier CSV/Excel depuis son application Mobile Money, donne son consentement explicite (lié à F05) puis dépose le fichier dans la plateforme. Après analyse, elle voit apparaître des indicateurs (volume mensuel moyen, régularité, croissance, solde estimé) et son score crédit combiné est ajusté en intégrant la nouvelle catégorie « Mobile Money — flux ».

**Why this priority**: c'est le différenciateur principal du « scoring crédit vert inclusif » et le seul levier rapide pour les PME informelles qui n'ont aucune trace bancaire formelle. Sans cette story, la promesse produit n'est pas tenue.

**Independent Test**: déposer un CSV Wave fictif valide après avoir donné le consentement « mobile_money_analysis » ; constater que ≥ 5 KPIs sont calculés et que le score combiné évolue. Sans consentement, l'upload est refusé avec un message explicite.

**Acceptance Scenarios**:

1. **Given** une PME connectée sans consentement Mobile Money actif, **When** elle tente d'uploader un CSV Wave, **Then** la requête est refusée (403) et un message « Consentement Mobile Money requis » est affiché avec un bouton vers le centre de consentements F05.
2. **Given** une PME ayant accordé le consentement « mobile_money_analysis », **When** elle dépose un export CSV de 90 jours, **Then** au moins 5 KPIs (volume mensuel moyen, écart-type, taux de régularité 30 j, solde moyen approximatif, tendance 12 mois) sont calculés, persistés et restitués dans son interface.
3. **Given** des KPIs Mobile Money calculés, **When** le scoring crédit est recomputé, **Then** la catégorie « Mobile Money — flux » apparaît dans la ventilation, son poids est dynamique selon la disponibilité des autres données et chaque chiffre affiché est rattaché à une source vérifiée (F01).
4. **Given** une PME ayant donné puis révoqué le consentement, **When** elle relance le calcul du score, **Then** la catégorie « Mobile Money — flux » est exclue avec redistribution dynamique des poids et les transactions importées sont marquées « non exploitées » (suppression effective sous 30 jours selon F05).

---

### User Story 2 — Faire analyser des photos d'exploitation par l'IA pour valoriser ses pratiques (Priority: P2)

Une PME souhaite valoriser visuellement la qualité de son site (matériel entretenu, organisation, hygiène, signaux verts comme tri, panneaux solaires, gestion eau). Elle donne son consentement « photo_analysis », téléverse jusqu'à 10 photos JPG/PNG (≤ 5 Mo l'unité), déclenche l'analyse IA, et obtient des scores par dimension (état matériel, organisation, hygiène/sécurité, pratiques environnementales, activité observée) avec observations, points forts et points d'attention. Ces scores alimentent la nouvelle catégorie « Photos IA » du score crédit.

**Why this priority**: forte différenciation produit, mais coût IA non trivial et risques privacy → P2 (après le levier MM).

**Independent Test**: téléverser 3 photos après consentement, déclencher analyse, vérifier que des scores numériques par dimension et une synthèse qualitative sont produits, persistés, et que la catégorie « Photos IA » apparaît dans la ventilation du score combiné. Sans consentement, l'upload est refusé.

**Acceptance Scenarios**:

1. **Given** une PME sans consentement « photo_analysis », **When** elle ouvre la modale d'upload photos, **Then** le formulaire est désactivé et un encart explicatif l'invite à donner son consentement avant de continuer.
2. **Given** un consentement actif, **When** la PME dépose 10 photos JPG ≤ 5 Mo, **Then** elles sont stockées dans son espace privé, listées dans son interface avec date de capture, et un bouton « Analyser » est disponible par photo et en lot.
3. **Given** une photo téléversée, **When** la PME lance l'analyse, **Then** les scores par dimension, les observations et red/green signals sont produits une seule fois (idempotent), persistés et restitués.
4. **Given** une 11ᵉ photo soumise, **When** l'upload est tenté, **Then** il est refusé avec le message « limite de 10 photos atteinte ».
5. **Given** un fichier > 5 Mo ou de format non autorisé (PDF, vidéo), **When** l'upload est tenté, **Then** la requête est refusée et le motif explicite est restitué.

---

### User Story 3 — Déclarer ses présences publiques (avis, programmes verts) pour les valoriser (Priority: P3)

Une PME visible en ligne (page Facebook, Google My Business, programmes verts labellisés) souhaite déclarer ses URLs et indicateurs publics (note moyenne, nombre d'avis, label PNUE/ADEME/GRI Sustainability) pour enrichir son profil. Elle donne son consentement « public_data_lookup », saisit ses informations en mode déclaratif, peut ajouter une capture d'écran de preuve, et l'analyse de signaux alimente la catégorie « Données publiques » du score crédit avec un poids plafonné.

**Why this priority**: levier complémentaire mais moins distinctif et davantage exposé à la fraude déclarative → poids plafonné, P3.

**Independent Test**: saisir une URL Google My Business + note 4,3 + 27 avis avec capture d'écran, vérifier la création d'une entrée « public_data_source » et l'apparition de la catégorie « Données publiques » dans la ventilation, plafonnée à ≤ 10 % du score combiné.

**Acceptance Scenarios**:

1. **Given** une PME consentante, **When** elle déclare une page publique avec note et nombre d'avis, **Then** l'entrée est persistée avec horodatage, marqueur « déclaratif non vérifié » et option pièce jointe.
2. **Given** plusieurs sources publiques déclarées, **When** le scoring est calculé, **Then** la catégorie « Données publiques » apparaît, son poids est plafonné à 10 % du score combiné et un badge « données déclaratives non vérifiées » est affiché.
3. **Given** une révocation du consentement « public_data_lookup », **When** le scoring est recalculé, **Then** la catégorie est exclue et les déclarations sont marquées « non exploitées ».

---

### User Story 4 — Consulter la méthodologie de scoring publique et sourcée (Priority: P2)

Tout visiteur (sans authentification) peut accéder à une page publique « Méthodologie scoring crédit » qui détaille les facteurs, leur poids, leur catégorie et leur source vérifiée (F01). Cela renforce la confiance, l'auditabilité et la conformité avec le Module 5.2.

**Why this priority**: prérequis de transparence et de conformité, nécessaire dès la P1 pour publier le score sans risque de contestation.

**Independent Test**: ouvrir la page publique sans être connecté, vérifier que la version, les facteurs, les poids et les sources cliquables sont présents et conformes à `GET /api/credit/methodology`.

**Acceptance Scenarios**:

1. **Given** un visiteur non authentifié, **When** il ouvre la page « Méthodologie scoring crédit », **Then** il voit la version courante, la liste des facteurs avec poids, catégorie et sources cliquables (modale Source F01).
2. **Given** un changement de pondération en base, **When** la page est rechargée, **Then** la version, les poids et les sources sont mis à jour de façon cohérente avec l'API.

---

### User Story 5 — Garantir l'auditabilité et la révocabilité des collectes alternatives (Priority: P1)

Un architecte/délégué·e à la protection des données (DPO) doit pouvoir prouver qu'aucune collecte alternative ne démarre sans consentement actif vérifié au runtime, que toutes les collectes/analyses sont auditées (F03) et que toute révocation entraîne l'arrêt immédiat de l'exploitation et la suppression effective sous 30 jours (F05).

**Why this priority**: bloquant juridique et déontologique (RGPD-like UEMOA), conditionne la mise en production.

**Independent Test**: tenter chaque collecte sans consentement (3 cas) → 403. Donner consentement → exécuter une collecte → vérifier dans le journal d'audit (F03) une ligne `source_of_change=manual|llm`, `account_id` correct, et qu'une révocation déclenche un événement `consent_revoked` puis une purge planifiée.

**Acceptance Scenarios**:

1. **Given** un appel à un endpoint de collecte alternative sans consentement actif, **When** l'utilisateur tente l'opération, **Then** le serveur retourne 403 avec un code structuré `consent_required` indiquant le type de consentement attendu.
2. **Given** une opération réussie, **When** le journal d'audit est consulté, **Then** une ligne `audit_log` existe avec entité, account_id, action (create/update/delete) et `source_of_change` adéquat.
3. **Given** une révocation de consentement, **When** elle est enregistrée, **Then** les analyses et entrées rattachées sont marquées « non exploitées », exclues du score, et programmées en suppression sous 30 jours conformément à F05.

---

### Edge Cases

- CSV Mobile Money chiffré ou protégé par mot de passe → rejet « format non supporté ».
- CSV avec séparateurs ambigus (`,` vs `;`) ou encodage non UTF-8 → détection automatique et fallback ; sinon rejet ligne par ligne avec compteur d'erreurs.
- CSV trop gros (> 5 Mo ou > 50 000 lignes) → rejet ; suggestion de split.
- Doublons d'imports (même fenêtre temporelle) → fusion idempotente sur `(account_id, transaction_date, amount, counterparty_hash, type)`.
- Photo contenant un visage humain → l'analyse n'effectue pas de reconnaissance faciale ; conseil de re-prise affiché.
- Photo EXIF géolocalisée → latitude/longitude jamais persistée ni exposée (strip EXIF à l'upload).
- Photo floue ou trop sombre → statut `low_quality`, exclue du score.
- 11ᵉ photo, 6 Mo, format HEIC → rejet avec message dédié.
- Coût IA : la même photo n'est analysée qu'une seule fois (résultat caché via hash de contenu).
- Données publiques : URL malformée, domaines non publics, captures non lisibles → rejet ou statut `pending_review`.
- Consentement révoqué pendant un traitement asynchrone → annulation propre et marquage `unused`.
- Méthodologie : facteur sans source vérifiée → masqué de la page publique et badge interne « non publiable ».

---

## Requirements *(mandatory)*

### Functional Requirements

#### Mobile Money
- **FR-001**: La plateforme MUST permettre à une PME consentante de téléverser un fichier CSV/Excel d'historique Mobile Money issu de Wave, Orange Money, MTN MoMo ou Moov Money (4 formats supportés à minima).
- **FR-002**: La plateforme MUST détecter automatiquement le format et l'encodage, normaliser chaque ligne en `{date, type incoming/outgoing, amount Money typé, counterparty_hash, balance optionnel}` et rejeter les lignes invalides avec un compteur d'erreurs.
- **FR-003**: La plateforme MUST hacher le contre-parti (counterparty) avant persistance afin d'éviter de stocker des identifiants en clair.
- **FR-004**: La plateforme MUST calculer au moins 5 indicateurs analytiques par PME (volume mensuel moyen, écart-type, taux de régularité 30 j, solde moyen approximatif, tendance 12 mois, top contre-parties anonymisées).
- **FR-005**: La plateforme MUST refuser tout import et toute analyse Mobile Money en l'absence de consentement actif « mobile_money_analysis » (gating runtime, 403).
- **FR-006**: La plateforme MUST exposer un endpoint d'analyse en lecture pour restituer les indicateurs courants à l'interface.

#### Photos IA
- **FR-007**: La plateforme MUST permettre à une PME consentante de téléverser jusqu'à 10 photos JPG/PNG de 5 Mo maximum chacune, stockées dans son espace privé `{account_id}/credit/photos/`.
- **FR-008**: La plateforme MUST refuser tout dépôt et toute analyse de photo en l'absence de consentement actif « photo_analysis » (403).
- **FR-009**: La plateforme MUST déclencher une analyse IA par photo qui produit des scores numériques sur 5 dimensions (état du matériel, organisation des espaces, hygiène/sécurité, pratiques environnementales visibles, activité observée), des observations, red flags et green signals.
- **FR-010**: La plateforme MUST garantir l'idempotence de l'analyse (une photo n'est analysée qu'une fois ; relance possible en cas d'échec uniquement).
- **FR-011**: La plateforme MUST nettoyer les métadonnées sensibles (EXIF géolocalisé) avant persistance et n'effectuer aucune reconnaissance faciale.
- **FR-012**: La plateforme MUST signaler les photos de basse qualité (`low_quality`) et les exclure du calcul du score.

#### Données publiques
- **FR-013**: La plateforme MUST permettre à une PME consentante de déclarer en mode déclaratif jusqu'à 5 sources publiques (URL + nature + note moyenne + nombre d'avis + pièce jointe optionnelle).
- **FR-014**: La plateforme MUST refuser toute déclaration et toute analyse en l'absence de consentement actif « public_data_lookup ».
- **FR-015**: La plateforme MUST plafonner le poids cumulé de la catégorie « Données publiques » à ≤ 10 % du score combiné et afficher un badge « données déclaratives non vérifiées ».

#### Scoring & Méthodologie
- **FR-016**: Le moteur de scoring MUST intégrer les 3 nouvelles catégories (`mobile_money_flux`, `photos_ia`, `public_data`) avec pondérations dynamiques selon la disponibilité des données et la présence des consentements.
- **FR-017**: La plateforme MUST exposer un endpoint public (sans authentification) restituant la méthodologie courante (version, facteurs, poids, catégorie, description, source vérifiée F01).
- **FR-018**: Une page publique MUST afficher la méthodologie de manière lisible avec liens vers les sources F01 ouvrant la modale Source.

#### Consentement, audit, sourçage, multi-tenant
- **FR-019**: Toute requête de collecte/analyse MUST passer par un garde-fou serveur réutilisable « require_consent(account_id, type) » qui interroge le module F05.
- **FR-020**: Toute mutation des entités F18 (transactions, photos, sources publiques, scores) MUST être tracée via le journal d'audit F03 avec `source_of_change` correct.
- **FR-021**: Toutes les tables F18 MUST porter un `account_id` et être protégées par RLS multi-tenant F02.
- **FR-022**: Tout chiffre affiché à l'utilisateur (méthodologie, KPI, score) MUST être rattaché à une source vérifiée F01 (badge `<SourceLink>`).
- **FR-023**: Toute révocation de consentement MUST entraîner l'arrêt immédiat de l'exploitation des données concernées et leur suppression effective sous 30 jours (relayée via F05).

#### UX
- **FR-024**: L'interface du score crédit MUST afficher 3 nouvelles sections (Mobile Money, Photos IA, Données publiques) avec, pour chaque section, un état (consentement absent / consentement actif / données présentes), un CTA d'action, et le bouton « Révoquer mon consentement » lorsqu'applicable.
- **FR-025**: Tous les composants F18 MUST être compatibles dark mode et accessibles (rôles ARIA, focus visibles, libellés français avec accents).

### Key Entities *(include if feature involves data)*

- **MobileMoneyTransaction** : représente une transaction Mobile Money importée. Attributs : compte, date, type (entrant/sortant), montant Money typé, contre-parti haché, solde optionnel, fournisseur (wave/om/mtn/moov), import_id. Multi-tenant.
- **MobileMoneyAnalysis** : agrégat analytique courant d'une PME (KPIs + version méthodologie + horodatage + statut consentement à l'instant t). Idempotente, recalculée à chaque import ou révocation.
- **CreditPhoto** : photo téléversée par une PME. Attributs : compte, chemin local, captured_at, analyzed_at, analysis_result (JSON structuré), statut qualité (`ok`/`low_quality`/`failed`), hash de contenu (déduplication), version méthodologie au moment de l'analyse.
- **PublicDataSource** : source publique déclarée par une PME (URL, type, note, nombre d'avis, pièce jointe optionnelle, statut `declared`/`evidence_attached`/`pending_review`).
- **CreditCategoryExtension** : extension du référentiel des catégories de scoring crédit (ajout `mobile_money_flux`, `photos_ia`, `public_data`).
- **CreditMethodology** : version courante de la méthodologie publiée (facteurs, poids, catégorie, description, source F01).
- **ConsentReference** : pointeur logique vers les consentements F05 utilisés (`mobile_money_analysis`, `photo_analysis`, `public_data_lookup`).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % des appels aux endpoints de collecte alternative sans consentement actif retournent 403 avec un code `consent_required`.
- **SC-002**: Les 4 formats Mobile Money sont parsés correctement avec ≥ 95 % de lignes valides exploitées sur des jeux de tests représentatifs.
- **SC-003**: Pour 90 jours d'historique Mobile Money, l'analyse produit ≥ 5 indicateurs distincts et la catégorie apparaît dans le score combiné en moins de 30 secondes après import (P95).
- **SC-004**: L'analyse IA d'une photo aboutit à 5 scores numériques + observations en moins de 60 secondes (P95) et reste idempotente.
- **SC-005**: Le poids de la catégorie « Données publiques » dans le score combiné ne dépasse jamais 10 %.
- **SC-006**: Toute mutation F18 est traçable dans le journal d'audit (≥ 99 % d'événements présents sur un jeu de tests).
- **SC-007**: La méthodologie publique est accessible sans authentification, affiche au moins une source vérifiée F01 par facteur, et reste cohérente avec l'API.
- **SC-008**: La révocation d'un consentement entraîne l'exclusion immédiate de la catégorie correspondante et une purge planifiée sous 30 jours.
- **SC-009**: La couverture de tests F18 est ≥ 80 % (parsers, gating consent, scoring, endpoints, composants UI).
- **SC-010**: Aucun chiffre affiché à l'utilisateur n'est dépourvu de source F01.

---

## Assumptions

- L'utilisateur dispose d'un export CSV/Excel téléchargeable depuis ses applications Mobile Money (pas d'intégration Open Banking côté MVP).
- Le scraping automatique des réseaux sociaux/avis n'est pas couvert (TOS) ; mode déclaratif uniquement, capture d'écran optionnelle.
- L'analyse IA des photos s'appuie sur le modèle vision multimodal accessible par la couche LLM existante du projet ; le coût est borné par photo et par PME (≤ 10 photos analysées 1 fois).
- Le module Consentements (F05) est opérationnel et expose un helper applicatif `require_consent(account_id, type)` ainsi que des événements de révocation.
- Le sourçage F01, l'audit F03, le typage Money F04, le multi-tenant + RLS F02 sont disponibles tels qu'utilisés par les autres features récentes.
- Les libellés UI sont en français avec accents, dark mode obligatoire, ARIA respecté.
- Devise par défaut XOF (peg EUR via constante existante).
- Stockage local sous `/uploads/{account_id}/credit/photos/` et `/uploads/{account_id}/credit/mobile_money/`.
- Caps MVP : 10 photos / PME, 50 000 lignes / import Mobile Money, 5 sources publiques / PME.
