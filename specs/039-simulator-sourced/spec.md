# Feature Specification: F16 — Simulateur Financement Sourcé + Comparateur Multi-Offres

**Feature Branch**: `feat/F16-simulateur-finance-source`
**Created**: 2026-05-08
**Status**: Draft
**Input**: F16 — Simulateur Financement Sourcé + Comparateur Multi-Offres. Réutilise F01 (sources) / F04 (Money typed) / F06 (Project) / F07 (Offer). NO MIGRATION métier (les `simulation_factors` existent déjà via F01).

## Clarifications

### Session 2026-05-08

Mode autonome (utilisateur a explicitement demandé une exécution sans questions interactives). Décisions prises avec valeurs par défaut raisonnables et tracées ci-dessous :

- Q: Persistance des résultats de simulation ? → A: Aucune persistance — calcul à la demande, in-memory, durée de vie = requête (déjà couvert par FR-012 et SC-006).
- Q: Comportement lorsqu'une offre du comparatif échoue à se calculer (facteur manquant, source obsolète bloquante) ? → A: La colonne de l'offre est rendue avec un état explicite « calcul indisponible » et la cause synthétique ; le comparatif global continue à s'afficher pour les autres offres (pas d'échec global).
- Q: Cohérence des facteurs au sein d'un même appel de comparaison multi-offres ? → A: Les facteurs sont chargés une fois au début de l'appel et appliqués de manière cohérente à toutes les offres comparées (snapshot logique unique par appel).
- Q: Règles d'accès pour la simulation et la comparaison ? → A: Le projet doit appartenir au compte appelant et chaque offre sélectionnée doit être visible par ce compte selon F02 ; en cas de violation, l'appel est refusé sans révéler d'information sur l'offre ou le projet (cohérent FR-013).
- Q: Limite anti-abus sur l'endpoint multi-simulate ? → A: Pas de limite spécifique pour le MVP au-delà de l'authentification standard et de la borne de 5 offres par appel (FR-014) ; toute limite supplémentaire sera décidée après mesure réelle.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Coût total réel sourcé (Priority: P1)

En tant que dirigeant·e de PME, lorsque je simule un financement pour un projet vert, je veux voir le **coût total réel** décomposé (principal, frais d'instruction, frais cumulés sur durée, garantie immobilisée, marge de change), exprimé dans la devise du fonds **et** dans ma devise PME (FCFA), avec **chaque chiffre cliquable** vers sa source vérifiée (taxonomie UEMOA, ADEME, intermédiaire, etc.).

**Why this priority**: C'est le cœur de la crédibilité du produit. Aujourd'hui, les constantes sont inventées (`0.15`, `1.7`, `0.03`) et la PME ne peut pas justifier ses chiffres face à son banquier ou à un comité d'investissement. Sans ce flux, la valeur ajoutée du simulateur s'effondre.

**Independent Test**: Sélectionner un projet existant (montant cible 5 M FCFA) et une offre (Fonds × Intermédiaire), lancer la simulation : la PME voit la décomposition complète, chaque ligne porte un libellé de source cliquable qui ouvre la fiche source F01.

**Acceptance Scenarios**:

1. **Given** un projet à 5 M FCFA et une offre Fonds×Intermédiaire de type prêt concessionnel, **When** la PME ouvre le simulateur et lance le calcul, **Then** elle voit principal + frais dossier + frais cumulés sur durée + garantie + marge FX, chacun avec son équivalent FCFA et un lien source cliquable.
2. **Given** un calcul terminé, **When** la PME clique sur le taux d'intérêt affiché, **Then** la fiche source F01 s'ouvre (publisher, date de publication, statut vérifié).
3. **Given** une offre dont la devise du fonds = devise PME, **When** la simulation s'exécute, **Then** la marge FX est égale à zéro et le composant la masque ou l'affiche explicitement à 0.
4. **Given** un facteur de simulation marqué « en attente de vérification », **When** la PME visualise la simulation, **Then** un avertissement « estimation en attente de vérification » accompagne le chiffre concerné.

---

### User Story 2 - Comparateur multi-offres côte-à-côte (Priority: P1)

En tant que dirigeant·e de PME, je veux comparer **jusqu'à 5 offres concurrentes** pour un même projet (par exemple GCF via BOAD vs GCF via UNDP vs SUNREF Ecobank), affichées côte-à-côte sur une même page, et identifier en un coup d'œil **la moins chère** et **la plus rapide**.

**Why this priority**: La différenciation entre offres est aujourd'hui invisible (un don à 100 % et un prêt à 12 % donnent le même résultat). Sans comparateur, la PME prend ses décisions à l'aveugle. C'est aussi le différenciateur produit revendiqué.

**Independent Test**: Sélectionner un projet, choisir 3 offres distinctes, lancer la comparaison : un tableau côte-à-côte s'affiche avec coût total, durée totale (timeline), taux de succès, score de compatibilité, et highlight visuels « moins chère » / « plus rapide ».

**Acceptance Scenarios**:

1. **Given** un projet et 3 offres distinctes sélectionnées, **When** la PME lance la comparaison, **Then** un tableau présente une colonne par offre avec coût total, timeline totale (en semaines), taux de succès et score de compatibilité.
2. **Given** un tableau comparatif rendu, **When** une offre a le coût total minimal, **Then** elle est mise en évidence avec un badge « Moins chère ».
3. **Given** un tableau comparatif rendu, **When** une offre a la timeline totale minimale, **Then** elle est mise en évidence avec un badge « Plus rapide ».
4. **Given** une seule offre sélectionnée, **When** la PME lance la comparaison, **Then** le système affiche la simulation détaillée d'une seule offre sans badges comparatifs.
5. **Given** plus de 5 offres sélectionnées, **When** la PME tente de lancer, **Then** le système refuse explicitement et invite à réduire la sélection.

---

### User Story 3 - Impact carbone et timeline non inventés (Priority: P1)

En tant que dirigeant·e de PME, je veux que l'**impact carbone estimé** du projet et la **timeline de décaissement** affichés dans le simulateur soient calculés à partir de données vérifiées (facteur d'émission par secteur sourcé ADEME/IPCC, délais réels de l'intermédiaire et du fonds), et non à partir de constantes hardcodées.

**Why this priority**: La crédibilité environnementale et opérationnelle du simulateur dépend de la fin des constantes inventées. Une PME qui présente « réduction 12 tCO2e/an » à un comité doit pouvoir pointer vers ADEME Base Carbone ; une PME qui voit « 8 semaines de décaissement » doit savoir que c'est l'intermédiaire choisi qui fixe ce délai.

**Independent Test**: Lancer une simulation pour deux offres différentes (intermédiaires distincts) sur le même projet : la timeline et l'impact carbone affichés diffèrent, chacun avec un libellé de source cliquable.

**Acceptance Scenarios**:

1. **Given** un projet avec impact carbone estimé renseigné, **When** la simulation s'exécute, **Then** la valeur affichée provient du projet et est qualifiée par un facteur sectoriel sourcé (et non un multiplicateur uniforme).
2. **Given** deux offres avec des intermédiaires différents, **When** la PME compare, **Then** la timeline (préparation + instruction + validation + décaissement) diffère entre les colonnes et chaque étape porte sa source.
3. **Given** une offre sans données de délai d'intermédiaire renseignées, **When** la simulation s'exécute, **Then** l'étape correspondante affiche un message clair (« délai non disponible — à compléter ») au lieu d'une valeur par défaut inventée.

---

### User Story 4 - ROI différencié par instrument (Priority: P2)

En tant que dirigeant·e de PME, je veux que le **retour sur investissement** affiché soit différencié selon l'instrument financier (subvention, prêt concessionnel, equity, blending), parce qu'un don n'a pas de remboursement et qu'un prêt à 2 % n'a pas la même charge qu'un prêt à 12 %.

**Why this priority**: Aujourd'hui le ROI est calculé arbitrairement (`payback ≈ 80 mois` peu importe l'instrument). Sans différenciation, la PME ne peut pas comparer rationnellement subvention vs prêt vs blending.

**Independent Test**: Lancer la simulation sur la même offre une fois en supposant subvention pure et une fois en supposant prêt concessionnel : la décomposition du ROI et le payback diffèrent visiblement.

**Acceptance Scenarios**:

1. **Given** une offre subvention, **When** la simulation s'exécute, **Then** le ROI est présenté comme « pas de remboursement » (ou symbole équivalent) et la durée d'amortissement n'est pas applicable.
2. **Given** une offre prêt concessionnel, **When** la simulation s'exécute, **Then** le ROI est exprimé comme un ratio gains estimés / coût total et le payback en mois est dérivé du flux différencié.
3. **Given** une offre blending (mixte don + prêt), **When** la simulation s'exécute, **Then** le ROI combine la part don (sans charge) et la part prêt (avec charge) avec ventilation visible.

---

### User Story 5 - Tool conversationnel `compare_simulations` (Priority: P2)

En tant que dirigeant·e de PME en conversation avec l'assistant IA, je veux pouvoir dire « compare GCF via BOAD et SUNREF pour mon projet » et voir un tableau comparatif rendu dans le chat, sans quitter la conversation.

**Why this priority**: Le canal conversationnel est central. Sans ce tool, la PME doit naviguer manuellement vers la page simulateur, brisant le flux d'usage.

**Independent Test**: Dans une conversation de chat, demander la comparaison de 2-3 offres : un bloc visuel `ComparisonTable` apparaît dans le fil avec les chiffres clés cliquables vers leurs sources.

**Acceptance Scenarios**:

1. **Given** une conversation active avec un projet identifié, **When** la PME demande à comparer 2-3 offres nommément, **Then** l'assistant invoque le tool de comparaison et un tableau s'affiche dans le chat avec les sources cliquables.
2. **Given** une demande sans projet identifié, **When** la PME demande la comparaison, **Then** l'assistant pose une question interactive (widget) pour choisir le projet avant de lancer la comparaison.

---

### Edge Cases

- **Aucune offre sélectionnée** : le simulateur affiche un état vide explicatif avec invitation à sélectionner.
- **Offre dont le fonds n'a pas de taux ou de durée publiés** : le système affiche le champ comme « non renseigné » et n'invente aucune valeur ; les colonnes dépendantes sont marquées.
- **Devise du fonds différente de celle de la PME, sans taux de change disponible récent** : la marge FX affiche un avertissement explicite et la conversion équivalent FCFA est désactivée pour ce chiffre.
- **Facteur de simulation absent (non encore migré)** : la simulation refuse de produire un chiffre fictif et affiche un message de mode dégradé pour la métrique concernée.
- **Project sans `expected_impact_tco2e`** : la section impact carbone affiche « non estimé » au lieu d'inventer.
- **Plus d'une offre identique sélectionnée** : le système dédoublonne avant calcul.
- **Simulation lancée pendant qu'un facteur change de version (F04)** : la simulation utilise la version courante au moment du calcul ; un nouveau lancement affichera le nouveau résultat.
- **Source d'un chiffre devenue « obsolète »** : le chiffre est tout de même affiché mais la fiche source signale l'obsolescence et invite à interpréter avec prudence.
- **Calcul lancé par un compte sans accès à l'une des offres** : le système refuse la simulation (cohérence avec l'isolation multi-tenant).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT supprimer toute constante numérique de calcul codée en dur dans le module de simulation et ne lire les facteurs (taux par défaut, ratios d'impact, frais par défaut, durée d'amortissement par défaut) qu'à partir d'un référentiel dédié de facteurs sourcés.
- **FR-002**: Chaque facteur de simulation utilisé DOIT être lié à une source vérifiable identifiable par la PME et accessible en un clic.
- **FR-003**: Tant qu'un facteur n'a pas été validé par un administrateur, il DOIT être marqué « en attente de vérification » et signalé visuellement à la PME au moment de son usage.
- **FR-004**: Le coût total d'une simulation DOIT être présenté comme une agrégation décomposée incluant principal, frais d'instruction, frais cumulés sur la durée, garantie exigée et marge de change, chacun exprimé avec sa devise nominale et son équivalent dans la devise PME.
- **FR-005**: Le retour sur investissement DOIT être calculé différemment selon le type d'instrument financier (subvention, prêt concessionnel, equity, blending) et la formule retenue DOIT être tracée vers ses sources.
- **FR-006**: L'impact carbone affiché DOIT provenir des données du projet (impact tCO₂e estimé) modulé par un ratio sectoriel sourcé, et ne JAMAIS résulter d'un multiplicateur appliqué linéairement au montant.
- **FR-007**: La timeline de la simulation DOIT être construite à partir des délais réels de l'offre sélectionnée (préparation, instruction intermédiaire, validation fonds, décaissement), chaque étape portant la source de son délai. Lorsque l'offre n'a pas de délai pour une étape, le système le déclare explicitement sans inventer.
- **FR-008**: Le système DOIT permettre à la PME de comparer entre 1 et 5 offres pour un même projet en un appel unique et obtenir un tableau comparatif côte-à-côte.
- **FR-009**: Le tableau comparatif DOIT mettre en évidence l'offre la moins chère (coût total minimal) et l'offre la plus rapide (timeline totale minimale) dès que deux offres ou plus sont comparées.
- **FR-010**: Les chiffres présentés dans le tableau comparatif DOIVENT rester cliquables vers leurs sources individuelles et conserver les libellés de devise.
- **FR-011**: Le système DOIT exposer un canal conversationnel permettant à la PME, depuis le chat, de déclencher une comparaison nommée d'offres et d'obtenir le bloc visuel correspondant rendu dans la conversation.
- **FR-012**: Les simulations NE DOIVENT PAS être persistées en base au-delà de la requête courante : chaque nouvelle simulation est calculée à la demande à partir de l'état courant du catalogue et du projet.
- **FR-013**: Toute simulation rejetée par les règles d'accès (compte non autorisé sur une offre, projet d'un autre tenant) DOIT échouer explicitement sans révéler d'information sur l'offre ou le projet.
- **FR-014**: Le système DOIT refuser une comparaison portant sur plus de 5 offres et indiquer clairement la limite à la PME.
- **FR-015**: La page de simulation DOIT être pleinement utilisable en mode sombre et accessible (contrastes, libellés, navigation clavier sur sélection d'offres et tableau).
- **FR-016**: Lorsqu'une offre individuelle d'une comparaison multi-offres ne peut pas être calculée (facteur introuvable, source bloquante), le système DOIT rendre la colonne correspondante avec un état explicite « calcul indisponible » accompagné d'une cause synthétique, sans interrompre le rendu des autres colonnes.
- **FR-017**: Au sein d'un même appel de comparaison multi-offres, les facteurs de simulation chargés DOIVENT former un snapshot logique unique appliqué de manière cohérente à toutes les offres comparées dans cet appel.

### Key Entities *(include if feature involves data)*

- **Facteur de simulation** : valeur numérique paramétrant un calcul (taux par défaut, ratio d'impact, frais par défaut, durée d'amortissement par défaut). Attributs essentiels : nom logique, valeur, unité, statut de vérification (brouillon, en attente, vérifié, obsolète), source rattachée. Détenu par le catalogue (entité existante introduite par F01) — pas de création de table dans cette feature.
- **Source vérifiée** : référentiel public ou réglementaire (taxonomie UEMOA, BCEAO, ADEME, IPCC, IEA, fonds, intermédiaire, etc.) attaché à un facteur ou à un délai. Entité existante (F01).
- **Projet** : initiative verte de la PME portant un montant cible et un impact carbone estimé. Entité existante (F06).
- **Offre** : couple Fonds × Intermédiaire qui matérialise les conditions effectives (taux, durée, frais, délais, devise). Entité existante (F07).
- **Résultat de simulation (volatile)** : agrégat calculé à la demande, non persisté, comprenant la décomposition du coût total, le ROI, l'impact carbone qualifié, la timeline jalonnée, et la liste des sources mobilisées. Volatile = inexistant après la requête.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % des chiffres affichés dans une simulation (taux, durée, frais, garantie, marge FX, ratio d'impact, durée d'amortissement) sont cliquables vers une source identifiée.
- **SC-002**: La revue manuelle du module de simulation par un humain ne trouve aucune constante numérique de calcul codée en dur (linter / inspection structurée).
- **SC-003**: Pour deux offres distinctes appliquées au même projet, au moins l'un des trois éléments suivants — coût total, ROI, timeline totale — diffère dans 95 % des cas testés en comparaison.
- **SC-004**: 90 % des PME interrogées en test utilisateur identifient en moins de 30 secondes l'offre « la moins chère » et l'offre « la plus rapide » dans un comparatif à 3 offres.
- **SC-005**: La comparaison côte-à-côte de 5 offres pour un projet renvoie un résultat utilisable en moins de 5 secondes pour une PME en condition normale.
- **SC-006**: Aucune simulation ne reste persistée en base au-delà de la durée de la requête (vérifiable par audit de la base après séance de test).
- **SC-007**: Un facteur en statut « en attente de vérification » ou « obsolète » est signalé visuellement dans 100 % de ses occurrences à l'écran.
- **SC-008**: Couverture des tests automatisés du module de simulation et des points d'entrée associés ≥ 80 %.

## Assumptions

- Les facteurs de simulation requis (taux par défaut, ratio d'impact, frais par défaut, durée d'amortissement par défaut, ratios sectoriels d'émission) seront introduits dans le catalogue F01 avec FK source obligatoire dès le démarrage de la feature ; certains pourront rester en statut « en attente » jusqu'à validation administrateur, sans bloquer la livraison technique.
- Les offres (F07) exposent déjà les délais d'instruction et de décaissement de l'intermédiaire ainsi que le calendrier typique du fonds source ; lorsqu'une donnée manque, le simulateur la marque « non renseignée » au lieu d'inventer.
- La conversion entre devise du fonds et devise de la PME repose sur le mécanisme de devises et taux de change introduit par F04, avec sa cohérence d'horodatage et son fallback FCFA-EUR ; le simulateur n'introduit pas de logique FX propre.
- Les simulations ne sont pas un objet métier traçable individuellement : la traçabilité repose sur le catalogue versionné (F01 + F04) et l'audit log existant (F03), pas sur un historique propre des simulations.
- Le tableau comparatif s'appuie sur le composant visuel introduit par les tools de visualisation typés (F11) ; cette feature n'invente pas un nouveau composant tabulaire.
- Le score de compatibilité affiché dans le comparatif est consommé depuis le module de matching projet-offre (F14) lorsqu'il est disponible ; en absence de matching, le score est masqué plutôt que fabriqué.
- L'isolation multi-tenant et les rôles existants (F02) couvrent la sécurité d'accès aux projets et aux offres ; cette feature ne crée pas de mécanisme d'autorisation dédié.

## Dependencies

- Catalogue de sources et de facteurs sourcés (F01) — fournit la table `simulation_factors` et les sources attachées.
- Devises typées et conversion (F04) — fournit la représentation des montants et la conversion vers la devise PME.
- Entité Projet (F06) — fournit le périmètre du projet, son montant cible et son impact estimé.
- Entité Offre Fonds×Intermédiaire (F07) — fournit les conditions effectives (taux, durée, délais, devise, frais).
- Tools de visualisation typés (F11) — fournit le composant tableau comparatif côte-à-côte.
- Mix carbone UEMOA sourcé (F17) — fournit les ratios sectoriels d'émission utilisés dans le calcul d'impact carbone.
- Matching projet-offre (F14, optionnel) — fournit le score de compatibilité affiché dans la colonne d'une offre.
- Multi-tenant et rôles (F02) — fournit l'isolation et le contrôle d'accès.
- Audit log (F03) — assure la traçabilité indirecte via les mutations du catalogue (les simulations elles-mêmes ne sont pas auditées).
