# Feature Specification: F15 — Génération de Dossiers de Candidature par Offre (FR/EN, Union Documents)

**Feature Branch**: `feat/F15-generation-dossiers-par-offre`
**Spec Number**: 041
**Created**: 2026-05-08
**Status**: Draft
**Input**: User description: "F15 — Génération de Dossiers par Offre. Génération de dossiers de candidature par offre F07 (couple Fonds × Intermédiaire), templates Jinja2 multilingues FR/EN, checklist union docs fonds+intermédiaire dédupliquée, intégration attestation F08, snapshot immuable F04, sourçage F01, Skills F23 par template. Inclut correctifs bugs : (1) company_context hardcodé, (2) AttributeError fund.max_amount, (3) doublon tool create_fund_application."
**Spec source** : `documents_et_brouillons/features_a_implementer/F15-generation-dossiers-par-offre.md`

## Contexte métier

Module 3.3 — Générateur de Dossiers de Candidature. Une candidature ne se fait jamais directement « vers un fonds », mais **vers une offre** (= couple Fonds × Intermédiaire). Chaque offre impose un format documentaire (langue acceptée, ton, sections, pièces obligatoires) qui est aujourd'hui appauvri par 4 valeurs `target_type` génériques. F15 introduit l'entité **Template Dossier** liée à une offre F07, à une Skill F23 et à une source F01 vérifiée.

Trois bugs critiques bloquent par ailleurs la qualité de la génération actuelle :
1. `company_context` est codé en dur (`"Aucun profil d'entreprise disponible."`) — le LLM ne reçoit jamais le profil PME.
2. `_simulate_financing` lève `AttributeError` sur `fund.max_amount` (le champ réel est `max_amount_xof` ou la paire Money typed F04).
3. Deux tools `create_fund_application` co-existent dans `financing_tools.py` et `application_tools.py`, ce qui rend l'orchestration LangGraph imprévisible.

## Clarifications

### Session 2026-05-08 (mode autonome — décisions inscrites sans interaction)

- Q : Politique de fallback lorsqu'aucun template `published` n'existe pour une offre F07 cible ? → A : **Bloquer la candidature avec message explicite + lien « demander à un admin de publier un template »**, plutôt que d'utiliser un template fallback générique non sourcé. Justification : un template sans `source_id` F01 vérifiée violerait FR-001/FR-008 (sourçage obligatoire). Les templates fallback par instrument restent disponibles uniquement comme ébauches admin (statut `draft`), pas pour génération PME directe.
- Q : Format DOCX en MVP ou seulement PDF ? → A : **PDF uniquement en MVP** (réutilisation directe pipeline WeasyPrint F06). DOCX reporté post-MVP (rétro-compat conservée pour python-docx existant côté legacy `application_tools.export_to_docx`, mais pas de nouveau code F15). Justification : éviter de doubler la surface de tests sur un format secondaire ; ce ré-arbitrage met à jour FR-029.
- Q : Comportement exact du widget de sélection de langue quand l'offre accepte 2 langues ? → A : **Widget QCU bloquant** (pas de défaut implicite). La PME doit choisir explicitement avant que `FundApplication.language` ne soit créé. Pré-sélection visuelle = langue UI courante de la PME, mais réponse obligatoire. Justification : éviter les candidatures EN soumises par erreur quand la PME parle FR.
- Q : Idempotence sur `(project_id, offer_id)` — comportement attendu sur tentative de doublon ? → A : **Renvoyer la candidature existante** (HTTP 200 + ressource existante avec header `X-Mefali-Idempotent: replay`), pas de 409 Conflict. Justification : UX optimale + cohérent avec le pattern FR-023 « idempotence sur création ». La PME peut continuer à éditer la candidature existante.
- Q : `down_revision` exact pour la migration 041 ? → A : **`down_revision = '040_carbon_report_dashboard'`** (dernière migration mergée avant F21 qui n'a pas de migration ; F22 et F23 n'ont pas modifié l'arbre Alembic au-delà de 040 hormis F23 = `033_create_skills` qui descend de `032_add_validation_error_tool_call_logs`, hors de la chaîne 03x récente). À reconfirmer techniquement en phase Plan via `alembic heads` mais le defaut sain pointe sur la dernière migration appliquée en prod (vérifier avec `alembic history` au début de l'implémentation). Si la chaîne `03x` montre un autre head, ajuster vers le head courant — la spec acte le principe : `down_revision = <head courant au moment du merge F15>`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Générer un dossier sourcé avec contexte PME complet (Priority: P1)

En tant que PME inscrite à ESG Mefali, lorsque je clique sur « Préparer mon dossier » pour l'offre **GCF via BOAD — Mitigation**, je veux que l'assistant rédige un dossier qui s'appuie sur mon profil entreprise réel, mon projet F06 sélectionné, le template officiel de cette offre (avec sources F01) et la Skill métier dédiée F23. Le résultat doit être un dossier structuré section par section, dont chaque chiffre cite une source, et non un texte générique.

**Why this priority** : sans ce socle (corriger le bug `company_context` + brancher Templates par offre + Skills F23), aucune génération de qualité n'est possible. C'est la valeur cœur de F15.

**Independent Test** : créer un compte PME avec un profil rempli, rattacher un projet F06, choisir une offre F07 disposant d'un template, déclencher la génération d'une section, vérifier que le rendu cite le profil (secteur, taille, pays) et au moins une source vérifiée F01.

**Acceptance Scenarios** :

1. **Given** une PME avec profil complet et un projet F06 lié à une offre F07 disposant d'un template publié, **When** elle déclenche la génération d'une section, **Then** le dossier produit cite au moins le secteur, le pays et le chiffre d'affaires de la PME, et chaque chiffre est rattaché à une source F01 cliquable.
2. **Given** une PME sans profil rempli, **When** elle déclenche une génération, **Then** le système l'invite à compléter son profil avant de lancer la génération (pas de prompt fantôme « Aucun profil… »).
3. **Given** un appel à `simulate_financing`, **When** le tool est invoqué pour une offre dont le fonds a `max_amount_xof = 5 000 000 000`, **Then** le tool ne lève pas d'`AttributeError` et retourne un montant simulé valide.

---

### User Story 2 — Choisir la langue du dossier selon les langues acceptées par l'offre (Priority: P1)

En tant que PME francophone candidatant pour une offre dont les langues acceptées sont `fr` et `en` (ex : GCF Direct Access via Acumen), je veux choisir explicitement la langue du dossier au démarrage et que toutes les sections soient générées dans cette langue, y compris les hints de la Skill F23 et les libellés du template.

**Why this priority** : impossible de candidater à des offres anglophones sans support EN ; bloque les fonds Direct Access internationaux.

**Independent Test** : créer une offre acceptant `["fr", "en"]`, démarrer un dossier, choisir `en`, vérifier qu'au moins 3 sections sont générées en anglais et que la checklist + l'export PDF utilisent les libellés EN.

**Acceptance Scenarios** :

1. **Given** une offre F07 avec `accepted_languages = ["fr", "en"]`, **When** la PME démarre une candidature, **Then** un widget interactif (F10) lui demande la langue avant d'instancier l'application.
2. **Given** une offre F07 mono-langue (`["en"]`), **When** la PME démarre une candidature, **Then** la langue est forcée à `en` sans question.
3. **Given** une candidature en cours en `fr`, **When** la PME bascule la langue après génération partielle, **Then** un avertissement explicite annonce que les sections déjà générées resteront dans la langue d'origine ou devront être régénérées (audit log F03 trace le changement).

---

### User Story 3 — Voir une checklist documentaire union (fonds + intermédiaire) dédupliquée (Priority: P1)

En tant que PME, je veux voir une **seule** checklist consolidée qui combine les pièces exigées par le fonds **et** par l'intermédiaire, sans doublons, en signalant l'origine de chaque pièce (fonds / intermédiaire / les deux), avec son caractère obligatoire et sa source F01.

**Why this priority** : la checklist actuelle est statique par `target_type` et trompeuse — la PME découvre des pièces manquantes au moment de la soumission via l'intermédiaire.

**Independent Test** : sélectionner une offre dont le fonds exige `["business_plan", "etude_impact"]` et l'intermédiaire exige `["business_plan", "kbis"]`, vérifier que la checklist affiche 3 pièces (`business_plan` marquée `both`), pas 4.

**Acceptance Scenarios** :

1. **Given** une offre dont le fonds et l'intermédiaire partagent une pièce identique (même titre normalisé), **When** la PME ouvre l'écran candidature, **Then** la pièce apparaît une seule fois avec un badge « exigé par les deux ».
2. **Given** une pièce marquée `mandatory: true` côté fonds et `mandatory: false` côté intermédiaire, **When** la checklist est calculée, **Then** la pièce est marquée `mandatory: true` (le plus restrictif gagne, cohérence F07).
3. **Given** une pièce avec `source_id` différent côté fonds et intermédiaire, **When** la checklist est calculée, **Then** les deux sources sont conservées et affichées dans la modale détail.

---

### User Story 4 — Joindre automatiquement l'attestation ESG (F08) au dossier exporté (Priority: P2)

En tant que PME ayant obtenu une attestation crédit ESG Mefali signée Ed25519 (F08), je veux pouvoir cocher « Joindre mon attestation » dans l'écran candidature pour que l'export PDF du dossier inclue l'attestation avec QR vérifiable.

**Why this priority** : différenciateur produit — la PME signale immédiatement à l'intermédiaire qu'elle a un score ESG indépendant et vérifiable. Mais reste optionnel : un dossier reste valide sans.

**Independent Test** : générer une attestation F08 active, créer un dossier, cocher « Joindre attestation », exporter en PDF, vérifier que le PDF contient l'attestation avec QR scannable redirigeant vers l'endpoint de vérification publique.

**Acceptance Scenarios** :

1. **Given** une PME avec une attestation F08 active (non révoquée, non expirée), **When** elle ouvre la section « Pièces jointes » d'une candidature, **Then** une option « Joindre mon attestation crédit ESG Mefali » est disponible.
2. **Given** la PME coche cette option et exporte en PDF, **When** le bundle est produit, **Then** l'attestation est annexée en dernière page avec QR code, ID public et signature lisible.
3. **Given** la PME a révoqué son attestation, **When** elle tente de la joindre, **Then** l'option est désactivée avec message explicatif.

---

### User Story 5 — Candidater pour un même projet vers plusieurs offres en parallèle (Priority: P2)

En tant que PME ayant un projet « ferme solaire 5 MW Saint-Louis », je veux pouvoir créer en quelques clics 3 candidatures distinctes (GCF via BOAD, FEM via UNDP, SUNREF via AFD), chacune avec son template, sa langue et son contenu propre, en partant du même socle projet F06.

**Why this priority** : optimisation utilisateur — réduit la friction de la candidature multiple. Sans ce P2, la PME peut quand même créer une candidature à la fois (P1 reste fonctionnel).

**Independent Test** : depuis la page projet, sélectionner 3 offres compatibles, déclencher « Créer en lot », vérifier que 3 candidatures distinctes sont créées avec leur template respectif et que leur contenu n'est pas mélangé.

**Acceptance Scenarios** :

1. **Given** un projet F06 et 3 offres F07 éligibles, **When** la PME sélectionne les 3 offres et clique « Candidater », **Then** 3 candidatures distinctes sont créées (clé `(project_id, offer_id)` unique).
2. **Given** une candidature déjà existante pour `(project, offer)`, **When** la PME tente de la recréer, **Then** le système la redirige vers l'existante (idempotence) plutôt que de créer un doublon.
3. **Given** 3 candidatures créées en lot, **When** la PME ouvre la page projet, **Then** elle voit la liste des 3 candidatures avec statut, template et langue de chacune.

---

### User Story 6 — Snapshot immuable au moment de la soumission (Priority: P2)

En tant qu'auditeur ou intermédiaire, je veux qu'au moment où une candidature passe au statut « soumise », un snapshot immuable du template, de l'offre, du projet, du profil et des scores soit capturé, pour pouvoir rejouer plus tard la décision de scoring même si le template ou l'offre évolue.

**Why this priority** : conformité et traçabilité (versioning F04). MVP-critical car sans snapshot, toute évolution du template casse l'audit.

**Independent Test** : créer une candidature, la soumettre, modifier le template original (nouvelle version F04), vérifier que la candidature soumise conserve l'ancien template via son `snapshot_data`.

**Acceptance Scenarios** :

1. **Given** une candidature en `draft`, **When** elle passe à `submitted_to_intermediary` ou `submitted_to_fund`, **Then** un `snapshot_data` JSONB autoportant est créé (template + offer + project + profil + scores + source_ids).
2. **Given** un template publié v1.0 utilisé pour une candidature soumise, **When** un admin publie v2.0 du template (nouvelle version F04), **Then** la candidature soumise pointe toujours sur v1.0 via son snapshot.
3. **Given** un snapshot existant, **When** quelqu'un tente de muter `snapshot_data`, **Then** un garde-fou applicatif refuse la mutation (cohérent avec F04).

---

### Edge Cases

- **Pas de template publié pour une offre** : la PME tente de candidater sur une offre F07 dont aucun template n'est `published`. Le système doit afficher un message explicite (« cette offre n'a pas encore de template officiel ») et proposer un template générique fallback (par `instrument_type` : subvention / prêt / equity / blending) marqué `draft`.
- **Profil PME incomplet au moment de la génération** : champs critiques manquants (secteur, pays, taille). Le système refuse la génération et liste les champs manquants.
- **Attestation expirée pendant la rédaction** : la PME a coché « Joindre attestation » puis l'attestation expire. Au moment de l'export, l'attestation est exclue avec avertissement.
- **Documents joints en plusieurs langues** : la PME joint un business plan en EN à un dossier FR. Le système accepte mais signale le mismatch.
- **Soumission concurrente** : deux clics simultanés sur « Soumettre » ne doivent créer qu'un seul snapshot (verrou optimiste sur `status`).
- **Template référencé sans Skill F23** : interdiction au niveau base (FK NOT NULL). Détection par seed et tests.
- **Migration backfill** : applications existantes sans `template_id`. La migration doit créer un template fallback par `target_type` et le lier à toutes les candidatures héritées (marqué `legacy_backfill = true`).
- **Génération bilingue interrompue** : la PME change de langue après 3 sections générées sur 7. Le système doit conserver les 3 premières dans la langue initiale et générer les 4 suivantes dans la nouvelle langue, en marquant la candidature `language_mixed = true` (alerte UI).
- **Doublon tool LangGraph** : si l'orchestrateur appelle `create_fund_application` pendant la phase de transition, un seul tool doit être enregistré côté graphe (résolution du bug #3).

## Requirements *(mandatory)*

### Functional Requirements

#### Bloc bugs critiques (correctifs immédiats)

- **FR-BUG-001** : Le service de génération de dossier MUST récupérer le profil entreprise réel de la PME (via `account_id` multi-tenant F02) et l'injecter dans chaque prompt de section, en remplacement du texte codé en dur.
- **FR-BUG-002** : Le tool de simulation financière MUST lire les champs Money typed F04 (`max_amount_money` / `min_amount_money`) avec fallback sur les colonnes legacy `*_xof`, et ne plus lever `AttributeError`.
- **FR-BUG-003** : Le système MUST n'exposer qu'un seul tool LangChain `create_fund_application`, capable de prendre `project_id`, `offer_id` et `language`. L'ancien tool dupliqué doit être retiré du graphe et de la whitelist.

#### Bloc Templates Dossier

- **FR-001** : Le système MUST gérer une entité `Template_dossier` rattachée à une offre F07, à une Skill F23 et à une source F01 (FK NOT NULL sur les trois).
- **FR-002** : Chaque template MUST déclarer une langue par défaut (`fr` ou `en`), une liste ordonnée de sections (clé, titre, instructions, longueur cible, ton, obligatoire), une liste de pièces requises, un ton imposé, des hints de vocabulaire, des anti-patterns, et hériter du versioning F04 (`version`, `valid_from`, `valid_to`, `superseded_by`) et du statut de publication F09 (`draft` / `published`).
- **FR-003** : Le système MUST permettre à un administrateur (F09) de créer, mettre à jour, publier et déprécier un template via le back-office, en respectant le contrôle 4-yeux (verified_by != captured_by) hérité de F01.
- **FR-004** : Une candidature `FundApplication` MUST porter une référence `template_id` (FK NOT NULL post-backfill) et une `language` issue de l'offre.
- **FR-005** : Lorsqu'aucun template `published` n'existe pour l'offre cible, le système MUST bloquer la génération côté PME et afficher un message explicite avec une action « notifier un admin pour publier un template ». Des templates fallback par `instrument_type` (subvention / prêt concessionnel / equity / blending) PEUVENT exister à l'état `draft` pour faciliter le travail admin, mais ne sont jamais exposés en génération PME (cohérence FR-008 sourçage obligatoire — clarification 2026-05-08).
- **FR-006** : Le système MUST stocker l'historique complet des templates (versioning F04) sans suppression physique.

#### Bloc Génération sourcée

- **FR-007** : La génération d'une section MUST charger : profil entreprise, projet F06, offre F07 effective, template, Skill F23 (`prompt_expert`, `procedure`, `tool_whitelist`, `sources`).
- **FR-008** : Chaque chiffre produit dans le dossier MUST être rattaché à une source F01 vérifiée (réutilisation du validator `source_required` F01) ou marqué explicitement comme déclaratif.
- **FR-009** : Le système MUST permettre à la PME de relancer la génération section par section ou de passer en édition manuelle.
- **FR-010** : Toute génération MUST être tracée dans `audit_log` (F03) avec `source_of_change = 'llm'`.

#### Bloc Multilingue

- **FR-011** : Si l'offre accepte plusieurs langues, le système MUST poser la question via widget interactif QCU bloquant F10 avant d'instancier la candidature (pas de défaut implicite ; pré-sélection visuelle = langue UI courante mais réponse obligatoire — clarification 2026-05-08).
- **FR-012** : Le système MUST router le bon `prompt_expert` (FR ou EN) de la Skill F23 selon la langue choisie.
- **FR-013** : Les libellés UI, la checklist et l'export MUST suivre la langue du dossier.
- **FR-014** : Le système MUST permettre de changer de langue après création, en avertissant la PME du risque de mixage et en traçant l'événement (audit F03).

#### Bloc Checklist union

- **FR-015** : Le système MUST calculer une checklist union des `required_documents` du fonds et de l'intermédiaire (cohérent avec `compute_effective_offer` F07), dédupliquée par titre normalisé (lowercase, accents retirés, espaces normalisés).
- **FR-016** : En cas de conflit `mandatory`, la valeur la plus restrictive (`true`) MUST l'emporter.
- **FR-017** : En cas de conflit de source F01, les deux sources MUST être conservées et affichées.
- **FR-018** : Chaque pièce de la checklist MUST porter un badge d'origine (`fund` / `intermediary` / `both`).
- **FR-019** : Le système MUST permettre à la PME d'attacher un document pour cocher la pièce correspondante de la checklist.

#### Bloc Attestation F08

- **FR-020** : Le système MUST permettre d'attacher au plus une attestation F08 active à une candidature (champ `attestation_id` nullable).
- **FR-021** : Au moment de l'export PDF/DOCX, l'attestation jointe MUST être annexée au bundle avec QR code, ID public et signature visibles.
- **FR-022** : Si l'attestation est révoquée ou expirée au moment de l'export, le système MUST l'exclure du bundle et journaliser un avertissement.

#### Bloc Génération multi-offres

- **FR-023** : Le système MUST imposer une contrainte d'unicité applicative sur `(project_id, offer_id)` pour `FundApplication`. En cas de tentative de création d'un doublon, le système MUST renvoyer la candidature existante (HTTP 200 + header `X-Mefali-Idempotent: replay`) plutôt que de lever 409 Conflict (clarification 2026-05-08).
- **FR-024** : Le système MUST permettre de créer plusieurs candidatures en lot pour un même projet (UI batch).
- **FR-025** : La page projet F06 MUST lister les candidatures rattachées avec leur statut, template, langue et offre.

#### Bloc Snapshot immuable F04

- **FR-026** : Au passage de `draft` à `submitted_to_intermediary` ou `submitted_to_fund`, le système MUST créer un `snapshot_data` JSONB autoportant contenant : template (id + version + sections), offer (id + version + effective criteria), project (id + version), profil PME (snapshot des champs critiques), scores ESG/carbone du moment, source_ids cités.
- **FR-027** : Le système MUST refuser toute mutation post-soumission de `snapshot_data` via une garde applicative + log d'audit F03.
- **FR-028** : Le système MUST exposer un endpoint « rejouer le scoring contre snapshot » qui recalcule la décision avec les données figées (cohérent avec F04 existant).

#### Bloc Export

- **FR-029** : Le système MUST produire un export PDF (réutilisation WeasyPrint F06) du dossier, dans la langue du dossier. L'export DOCX reste disponible via le code legacy `application_tools.export_to_docx` mais n'est pas étendu en F15 (clarification 2026-05-08 — DOCX = post-MVP).
- **FR-030** : Les fichiers exportés MUST être stockés sous `/uploads/applications/<account_id>/<application_id>/` avec format de nom `dossier-<offer_code>-<YYYY-MM-DD>.<ext>` et dates au format français pour le contenu.
- **FR-031** : Tout export MUST inclure une annexe « Sources et références » F01 (réutilisation du partial existant).

#### Bloc Sécurité, audit, multi-tenant

- **FR-032** : Toutes les opérations MUST respecter Row-Level Security PostgreSQL F02 (`account_id` filtré).
- **FR-033** : Toute mutation sur `FundApplication` ou `Template_dossier` MUST être tracée dans `audit_log` F03 avec champ `source_of_change` (`manual` / `llm` / `admin` / `import`).
- **FR-034** : Le back-office admin (F09) MUST exposer la gestion CRUD des templates avec workflow draft/published et 4-yeux.

### Key Entities *(include if feature involves data)*

- **Template Dossier** : modèle officiel de dossier pour une offre donnée. Attributs principaux : nom, offre liée (F07), langue par défaut, sections ordonnées (titre, instructions, longueur cible, ton, obligatoire), pièces requises union, ton, vocabulaire, anti-patterns, Skill liée (F23), source officielle (F01), versioning (F04), statut publication (F09).
- **Candidature (FundApplication)** : enrichie de `template_id`, `language` (`fr` ou `en`), `attestation_id` (lien optionnel F08), `snapshot_data` immuable (post-soumission), `project_id` (F06 — déjà présent), `offer_id` (F07 — déjà présent).
- **Snapshot de candidature** : capture autoportante au moment de la soumission ; contient template figé, offer figée, profil figé, scores du moment, source_ids cités. Immuable.
- **Pièce de checklist** : titre normalisé, obligatoire, source F01, origine (`fund` / `intermediary` / `both`), document attaché (le cas échéant).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : 100 % des dossiers générés contiennent les champs critiques du profil PME (secteur, pays, taille) — vérifié par échantillonnage de 30 dossiers post-livraison. Régression bug #1 = 0.
- **SC-002** : 100 % des appels `simulate_financing` sur les 12 fonds seed F07 réussissent sans `AttributeError`. Régression bug #2 = 0.
- **SC-003** : Un seul tool `create_fund_application` est enregistré dans le graphe LangGraph (assertion automatisée dans la suite de tests). Régression bug #3 = 0.
- **SC-004** : 100 % des candidatures soumises possèdent un `snapshot_data` non vide et résistant à la mutation (test d'intégrité sur 20 cas).
- **SC-005** : La checklist union dédupliquée renvoie un nombre de pièces ≤ `len(fonds) + len(intermédiaire)` et ≥ `max(len(fonds), len(intermédiaire))` sur 100 % des paires testées (10 paires seed).
- **SC-006** : 100 % des sections générées pour une offre EN-only sont rédigées en anglais (vérifié sur 5 offres EN seed via détection langue automatique).
- **SC-007** : Le temps moyen entre « clic Préparer mon dossier » et première section générée est ≤ 15 secondes p95 sur les 10 templates seed.
- **SC-008** : 95 % des PME testant la génération multi-offres en lot (3 offres simultanées) obtiennent 3 candidatures distinctes sans erreur.
- **SC-009** : 100 % des exports PDF avec attestation jointe contiennent un QR code scannable redirigeant vers l'endpoint de vérification publique F08.
- **SC-010** : Couverture de tests sur le périmètre F15 ≥ 80 %.
- **SC-011** : Migration Alembic 041 round-trip `up/down/up` validée sur PostgreSQL et sur SQLite (suite tests).
- **SC-012** : 100 % des templates seed publiés disposent d'une source F01 vérifiée et d'une Skill F23 active.

## Assumptions

- L'offre F07 (entité couple Fonds × Intermédiaire) est mergée et stable. Les templates s'appuient sur `offer_id` et sur le calculateur `compute_effective_offer`.
- Skills F23 sont mergées et chaque template peut référencer une Skill publiée existante (`skill_dossier_gcf_via_boad`, `skill_score_gcf`, `skill_esg_diagnostic` au minimum).
- F08 (attestation Ed25519) est mergée — l'intégration au PDF se contente de joindre l'attestation existante via QR.
- F06 (Project) est mergée — chaque candidature pointe sur un projet réel.
- F04 (Money typed + versioning) est mergée — la migration F15 réutilise les mixins `VersioningMixin` et le pattern `superseded_by`.
- F01 (sourçage) est mergée — chaque template référence une source F01 et le validator post-tour s'applique.
- F02 (multi-tenant + RLS) est mergée — toutes les nouvelles tables/colonnes héritent de l'isolation `account_id`.
- F03 (audit log) est mergée — tous les CRUD sur templates et candidatures sont auditables.
- F10 (widgets bottom sheet) est mergé — la sélection de langue passe par `ask_interactive_question`.
- Storage local sous `/uploads/applications/<account_id>/<application_id>/` est acceptable en MVP. Migration MinIO/S3 post-MVP, hors scope F15.
- Le LLM (Claude via OpenRouter) est suffisamment performant en EN pour produire des sections de qualité. Garde-fou : tester explicitement 5 cas EN.
- Les langues supportées en MVP sont strictement `fr` et `en`. Autres langues hors scope.
- La déduplication de pièces se fait par titre normalisé (lowercase + accents retirés + espaces normalisés). Une déduplication sémantique (LLM) est hors scope MVP.
- Le format des dates dans le contenu généré et dans les libellés UI est français (jj/mm/aaaa) en mode `fr`, ISO ou format anglo-saxon en mode `en`.
- La migration Alembic est numérotée **041** (`041_templates_and_application_refactor`) avec `down_revision` pointant sur la dernière migration mergée à finaliser en phase Plan.
- Le seed initial fournit au moins 4 templates publiés couvrant les 4 instruments principaux (subvention, prêt concessionnel, equity, blending) et au moins 2 offres GCF/BOAD prioritaires.
- La couverture cible est ≥ 80 % sur le périmètre F15.

## Hors-scope (post-MVP)

- Templates pré-générés par IA avec validation admin (création assistée).
- Co-rédaction multi-utilisateurs sur la même section.
- Versioning des sections individuelles (track changes).
- Bibliothèque de réponses-types réutilisables cross-projets.
- Génération automatique 100 % sans intervention user.
- Validation grammaticale automatique avant export.
- Templates communautaires (consultants tiers).
- Langues autres que `fr` / `en`.
- Migration storage MinIO/S3.
- Déduplication sémantique des pièces de checklist par LLM.

## Dépendances

| Feature | Statut | Usage F15 |
|---------|--------|-----------|
| F01 (sourçage) | Mergée | `source_id` FK NOT NULL sur templates ; validator post-tour |
| F02 (multi-tenant + RLS) | Mergée | `account_id` sur toutes les nouvelles tables/colonnes |
| F03 (audit log) | Mergée | mixin `Auditable` sur Template et FundApplication ; `source_of_change` |
| F04 (Money + versioning) | Mergée | versioning F04 sur templates + snapshot immuable |
| F06 (Project) | Mergée | `project_id` déjà présent sur FundApplication |
| F07 (Offer = Fonds × Intermédiaire) | Mergée | `offer_id` FK template ; `compute_effective_offer` checklist union |
| F08 (attestation Ed25519) | Mergée | `attestation_id` FK nullable sur FundApplication ; export PDF |
| F09 (back-office admin) | Mergée | CRUD Templates avec workflow draft/published + 4-yeux |
| F10 (widgets bottom sheet) | Mergée | sélection de langue via `ask_interactive_question` |
| F23 (Skills) | Mergée | `skill_id` FK NOT NULL sur templates ; `prompt_expert` + `tool_whitelist` |

## Risques & garde-fous

- **Risque** : la migration backfill crée des templates orphelins. **Garde-fou** : seed admin de templates pour les 10 offres prioritaires, link manuel pour le reste, marquer les autres `draft`.
- **Risque** : multilingue dégrade la qualité. **Garde-fou** : test explicite EN sur 5 cas avec assertion langue détectée.
- **Risque** : la checklist union peut être longue. **Garde-fou** : grouper par catégorie, marquer mandatory/optional, progress bar UI.
- **Risque** : changement de template après génération partielle écrase le contenu. **Garde-fou** : versioning F04 sur sections, demande de confirmation explicite, audit log F03.
- **Risque** : confusion sur le sens de la suppression de bug #3 (doublon) — tests de régression peuvent casser. **Garde-fou** : couvrir explicitement chaque chemin avec un test dédié avant de supprimer le code mort.
