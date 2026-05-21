# Feature Specification: Catalogue d'administration du financement vert

**Feature Branch**: `044-admin-catalog-financing`
**Created**: 2026-05-21
**Status**: Draft
**Input**: User description: "il faut creer la page /admin/catalog de sorte qu'on puisse retrouver les éléments enregistré dans /financing"

## Clarifications

### Session 2026-05-21

- Q: Stratégie d'affichage pour les grands volumes par onglet ? → A: Charger la liste complète tant que <2 000 lignes, basculer en pagination serveur (50/page) au-delà.
- Q: Granularité du journal d'audit pour `/admin/catalog` ? → A: Aucun audit — le catalogue est une donnée de référence globale, hors périmètre F03.
- Q: Comportement de l'onglet « Liaisons fonds × intermédiaires » au clic ? → A: Fiche liaison dédiée affichant la paire, les bornes d'accréditation, le plafond et la source, avec liens vers les fiches fonds et intermédiaire.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Vue unifiée du catalogue de financement (Priority: P1)

En tant qu'administrateur de la plateforme, j'accède à une page unique `/admin/catalog` qui regroupe l'ensemble des éléments du catalogue de financement vert actuellement publiés côté PME dans `/financing` (fonds, intermédiaires, offres effectives et liaisons fonds × intermédiaires). Cette page me permet de retrouver rapidement n'importe quel élément du catalogue par recherche, filtre ou navigation par onglet, puis d'ouvrir sa fiche détaillée pour consulter ses caractéristiques sourcées.

**Why this priority**: Sans vue centralisée, l'administrateur doit aujourd'hui naviguer entre l'unique page `/admin/funds` existante et la vue publique `/financing` pour vérifier ce qui est effectivement exposé aux PME. C'est la base indispensable de gouvernance du catalogue (cohérence, complétude, sourçage F01) avant toute opération d'édition ou de modération.

**Independent Test**: Connecter un compte ADMIN, ouvrir `/admin/catalog`, vérifier que les compteurs (nombre de fonds, intermédiaires, offres, liaisons) correspondent exactement à ce qui est listé dans `/financing` (index + onglets), et qu'une recherche par nom retrouve un élément attendu en moins de 3 secondes.

**Acceptance Scenarios**:

1. **Given** un administrateur authentifié, **When** il ouvre `/admin/catalog`, **Then** la page affiche quatre onglets — Fonds, Intermédiaires, Offres, Liaisons fonds × intermédiaires — avec un compteur d'éléments par onglet.
2. **Given** un onglet sélectionné, **When** l'administrateur saisit un terme dans la barre de recherche, **Then** la liste filtre en moins de 500 ms sur le nom, le code ou les mots-clés métier de l'élément.
3. **Given** un élément de la liste, **When** l'administrateur clique dessus, **Then** une fiche détaillée s'ouvre avec toutes les caractéristiques métier (critères d'éligibilité, montants, instruments, secteurs, documents requis, statut de publication, version, sources F01).
4. **Given** un utilisateur non administrateur, **When** il tente d'accéder à `/admin/catalog`, **Then** l'accès est refusé et il est redirigé hors de l'espace admin.

---

### User Story 2 — Filtres par statut de publication et version (Priority: P2)

En tant qu'administrateur, je filtre le catalogue par statut de publication (publié / brouillon / déprécié), par type ou catégorie pertinents selon l'onglet, et je trie par date de mise à jour ou par version. Cela me permet de repérer en un coup d'œil les éléments obsolètes, à compléter ou à valider.

**Why this priority**: Le catalogue est versionné (F04) et exige un workflow 4-yeux (F01). Filtrer par statut/version est indispensable pour le suivi quotidien sans toutefois être bloquant pour l'usage de base couvert par US1.

**Independent Test**: Filtrer sur statut « brouillon » et vérifier qu'aucun élément de la liste n'apparaît côté `/financing` public ; filtrer sur « déprécié » et vérifier que ces éléments portent bien une référence vers leur version successeur.

**Acceptance Scenarios**:

1. **Given** l'onglet Fonds, **When** l'administrateur sélectionne le filtre « Statut = brouillon », **Then** seuls les fonds non publiés s'affichent.
2. **Given** un élément déprécié, **When** la fiche détaillée s'ouvre, **Then** un lien permet de naviguer vers la version qui le remplace.

---

### User Story 3 — Export du catalogue courant (Priority: P3)

En tant qu'administrateur, j'exporte la vue courante (onglet + filtres appliqués) au format tabulaire pour partager le catalogue avec des parties prenantes externes (auditeurs, équipe métier) ou pour archivage.

**Why this priority**: Confort opérationnel utile mais non bloquant pour la valeur métier de la page.

**Independent Test**: Appliquer un filtre, déclencher l'export, vérifier que le fichier téléchargé contient exactement les lignes affichées avec les colonnes principales.

**Acceptance Scenarios**:

1. **Given** une liste filtrée, **When** l'administrateur clique sur « Exporter », **Then** un fichier tabulaire est téléchargé contenant les éléments affichés.

---

### Edge Cases

- Catalogue vide pour un onglet : afficher un état vide explicite (« Aucun élément enregistré dans cette catégorie ») plutôt qu'une liste blanche.
- Élément déprécié dont la version successeur est introuvable (chaîne rompue) : afficher un badge d'alerte sur la fiche.
- Recherche ne retournant aucun résultat : afficher un message « Aucun résultat » avec la requête saisie et un bouton « Réinitialiser les filtres ».
- Volume d'un onglet : tant que le nombre d'éléments est inférieur à 2 000, la liste est chargée intégralement côté serveur ; au-delà, la liste bascule automatiquement en pagination serveur (50 éléments par page, sélecteur 25/50/100).
- Élément accessible côté `/financing` mais introuvable dans `/admin/catalog` (incohérence statut/visibilité) : afficher un badge « Incohérence détectée » signalant le problème.
- Accès par un compte PME ou non authentifié : redirection sécurisée hors de l'espace admin.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: La page `/admin/catalog` MUST être accessible uniquement aux utilisateurs portant le rôle ADMIN ; tout autre accès MUST être refusé.
- **FR-002**: La page MUST exposer en onglets les quatre familles d'éléments du catalogue de financement vert : Fonds, Intermédiaires, Offres effectives, Liaisons fonds × intermédiaires.
- **FR-003**: Chaque onglet MUST afficher l'ensemble des éléments enregistrés, indépendamment de leur statut de publication, afin que l'administrateur retrouve aussi les brouillons et dépréciés non visibles côté `/financing`.
- **FR-004**: Chaque liste MUST proposer une recherche plein-texte couvrant au minimum le nom, le code et les mots-clés métier de l'élément.
- **FR-005**: Chaque liste MUST proposer des filtres par statut de publication, par type ou catégorie pertinents selon l'onglet, et un tri par date de mise à jour ou par version.
- **FR-006**: Chaque élément listé MUST exposer une fiche détaillée affichant ses caractéristiques métier complètes, sa version, son statut et les sources F01 attachées. Pour l'onglet « Liaisons fonds × intermédiaires », la fiche détaillée MUST afficher la paire fonds–intermédiaire, les bornes d'accréditation (début/fin), le plafond par fonds, la source d'accréditation, et MUST inclure des liens navigables vers la fiche du fonds et celle de l'intermédiaire concernés.
- **FR-007**: Les éléments dépréciés (avec successeur renseigné) MUST afficher un lien navigable vers leur version successeur quand celle-ci existe.
- **FR-008**: La page MUST afficher pour chaque onglet un compteur du nombre total d'éléments et du nombre d'éléments correspondant aux filtres courants.
- **FR-009**: La page MUST respecter le mode sombre obligatoire (parité claire/sombre sur fonds, textes, bordures, états de survol).
- **FR-010**: La page MUST permettre d'exporter la vue courante (onglet + filtres) sous forme tabulaire téléchargeable.
- **FR-012**: La page MUST afficher un état vide explicite lorsqu'un onglet ne contient aucun élément et un message « Aucun résultat » lorsqu'une recherche ou un filtre ne retourne rien.
- **FR-013a**: Tant que le nombre total d'éléments d'un onglet est inférieur à 2 000, la page MUST charger la liste complète en une seule requête ; au-delà de ce seuil, elle MUST basculer en pagination serveur (taille de page 50 par défaut, options 25/50/100) en préservant les filtres et le tri.
- **FR-013**: La page MUST être en lecture seule dans ce périmètre ; toute édition, création ou changement de statut reste hors-scope de cette feature et MUST renvoyer vers les écrans d'édition existants ou à créer ultérieurement.

### Key Entities

- **Fonds** : organisme bailleur (multilatéral, bilatéral, régional, national, privé, marketplace carbone) avec instruments, thèmes, mode de soumission, statut de publication, version et source.
- **Intermédiaire** : entité accréditée (banque, fonds national, ONG…) qui sert de relais pour soumettre un dossier à un fonds, avec frais, délais, documents requis, statut et source.
- **Offre effective** : combinaison fonds × intermédiaire (ou fonds direct via le singleton DIRECT) effectivement proposée à une PME, avec critères intersectés, documents unionés, frais et délais agrégés.
- **Liaison fonds × intermédiaire** : relation d'accréditation entre un fonds et un intermédiaire, bornée dans le temps, avec plafond par fonds et source d'accréditation.
- **Statut de publication** : attribut commun aux fonds et intermédiaires (publié, brouillon, déprécié) déterminant la visibilité côté `/financing` public.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un administrateur retrouve n'importe quel élément du catalogue (par nom ou code) en moins de 5 secondes depuis l'ouverture de la page.
- **SC-002**: 100 % des éléments listés côté `/financing` public sont également présents dans `/admin/catalog` sur l'onglet correspondant, sans écart.
- **SC-003**: L'administrateur identifie en moins de 30 secondes la liste des éléments en statut « brouillon » ou « déprécié » nécessitant une revue.
- **SC-004**: Les temps de chargement initial et de filtrage restent inférieurs à 2 secondes pour des volumes jusqu'à 1 000 éléments par onglet.
- **SC-005**: Zéro accès non autorisé : tout utilisateur non ADMIN tentant `/admin/catalog` est refoulé dans 100 % des cas.

## Assumptions

- Les données de fonds, intermédiaires, offres et liaisons sont déjà persistées par les fondations F06/F07 ; aucune nouvelle structure de données n'est introduite par cette feature.
- Le périmètre est strictement la lecture/consultation : l'édition, la publication/dépublication et le workflow 4-yeux restent gérés par les écrans dédiés (existants ou à venir).
- L'utilisateur ADMIN dispose déjà du layout `admin.vue` et du middleware `admin.ts` pour l'authentification et l'autorisation.
- Le catalogue est considéré comme donnée de référence globale (non rattachée à un compte PME) ; les consultations administratives ne sont pas tracées dans le journal d'audit F03.
- L'export tabulaire suit le format standard déjà utilisé pour les exports d'audit (CSV).
- La page complète, et ne remplace pas, l'écran existant `/admin/funds` ; une future itération pourra fusionner les deux ou rediriger l'un vers l'autre.
