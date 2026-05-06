# ESG Mefali - Fonctionnalités Complètes

## Vision du Projet

**Nom proposé :** ESG Mefali / Conseiller ESG IA

**Pitch :** Une plateforme conversationnelle IA qui démocratise l'accès à la finance durable pour les PME africaines francophones en combinant analyse de conformité ESG **multi-référentiels et entièrement sourcée**, conseil en financement vert via les **intermédiaires accrédités** du terrain, et scoring de crédit alternatif. La plateforme est **fermée aux intermédiaires** (accès réservé aux PME et aux administrateurs ESG Mefali) — les intermédiaires reçoivent les dossiers et les attestations vérifiables que la PME leur transmet par leurs propres canaux.

---

## Modèle Conceptuel (à respecter par toute l'application)

### Entités principales

- **Entreprise** = qui est la PME (identité, secteur, taille, gouvernance, pratiques actuelles). Sert de **contexte porteur** et alimente le scoring crédit (Module 5) et la conformité ESG globale (Module 2). 1 par compte.
- **Projet vert** = ce que la PME veut financer (objectif environnemental, montant, impact attendu). C'est l'objet réel de la candidature au financement. 0..N par entreprise.
- **Fonds source** = institution qui décaisse l'argent in fine (GCF, FEM, AFD, BAD, etc.). Définit ses propres critères d'éligibilité et son propre référentiel.
- **Intermédiaire accrédité** = entité qui relaie l'accès à un fonds (banque locale partenaire, agence d'implémentation, NIE/RIE/MIE, développeur de projet carbone, etc.). **En Afrique, la plupart des fonds verts ne sont pas accessibles directement aux PME** — il faut passer par un intermédiaire qui rajoute ses propres règles, documents, frais et délais.
- **Offre** = couple (Fonds source × Intermédiaire) — c'est le **produit réel** auquel une PME peut souscrire. Critères effectifs = fonds ∩ intermédiaire ; documents = fonds ∪ intermédiaire ; frais = fonds + marges intermédiaire ; délais = fonds + intermédiaire.
- **Candidature** = soumission d'un Projet à une Offre (donc à un couple Intermédiaire-Fonds). 0..N par projet.
- **Indicateur** = unité atomique de mesure ESG (ex : "% de déchets recyclés", "Émissions Scope 1 en tCO2e"). Possède une définition unique et **au moins une `Source`** vérifiée.
- **Référentiel** = collection d'indicateurs avec seuils et pondérations. Définit comment un score est calculé. Versionné. Possède **au moins une `Source`** officielle (taxonomie UEMOA, critères GCF, IFC PS, politique BOAD, etc.).
- **Source** = **entité de premier rang**. Toute affirmation factuelle (indicateur, formule, critère, seuil, facteur d'émission, document requis) **doit pointer vers une `Source` vérifiée**. Sans source vérifiée, l'objet reste en `draft` et le LLM ne peut pas s'en servir. Voir Module 0.1.

### Relations

```
Entreprise 1—N Projets 1—N Candidatures
Candidature N—1 Offre
Offre N—1 Intermédiaire
Offre N—1 Fonds source
Intermédiaire N—N Fonds source (relation d'accréditation, datée)

Indicateur N—1 Source (au moins une)
Référentiel N—N Indicateurs (avec seuils et poids) ; N—1 Source (au moins une)
Critère d'Offre N—N Indicateurs ; N—1 Source
Facteur d'émission N—1 Source
Formule de calcul N—1 Source
Document requis N—1 Source
```

### Conséquences structurantes

- Un même projet peut faire l'objet de **plusieurs candidatures** à des offres différentes : multi-fonds en parallèle, ou même fonds via plusieurs intermédiaires (ex : GCF via BOAD vs GCF via UNDP — stratégies très différentes en termes de critères, délais, frais, taux de succès).
- Le matching n'est jamais "Projet ↔ Fonds" mais toujours "Projet ↔ Offre". L'intermédiaire est souvent le **vrai filtre** : un projet peut être éligible GCF mais incompatible BOAD.
- Une PME peut chercher du financement de plusieurs façons : financement entreprise global (rare en finance verte), financement projet (cas standard), co-financement / blending (un projet financé par plusieurs offres simultanées).
- **Aucun chiffre, aucun critère, aucune formule présenté à l'utilisateur ne peut exister sans `Source` vérifiée.** C'est une règle d'intégrité au niveau base de données et un comportement obligatoire du LLM.

### Mapping UI

Les entités Entreprise et Projets sont regroupées sous une **section "Profil"** unique de l'application, avec deux vues distinctes :
- **Profil → Entreprise** : édition des champs de l'entité Entreprise (singulier, 1 par compte).
- **Profil → Projets** : liste, création, édition, duplication et suppression des projets (pluriel, 0..N).

Toute mention de "page Profil" dans la suite du document désigne cette section unifiée — jamais l'entreprise seule.

---

## Architecture Technique

### Stack Technologique
- **Frontend :** Nuxt 4 (dernière version) + Composition API + Pinia (state management) + TailwindCSS v4 (dernière version) + chart.js + mermaid + Leaflet + gsap + driver.js + fontawesome + toast-ui/editor + LangGraph (avec LangChain en couche utilitaire) + etc.
- **Backend :** FastAPI (Python)
- **LLM :** minimax-m2.7 via OpenRouter (afin de pouvoir changer facilement de modèle)
- **Base de données :** PostgreSQL + pgvector (embeddings) + Row-Level Security (multi-tenant)
- **Stockage documents :** stockage local (MinIO / S3 plus tard)
- **File d'attente :** traitement synchrone (Redis + Celery plus tard)
- **Hébergement :** présence Europe ou Afrique de l'Ouest (OVH, Scaleway, AWS Cape Town, Africa Data Centres) — **pas USA** pour conformité données personnelles UEMOA / loi ivoirienne 2013-450 / RGPD européen.

---

## Module 0 : Fondations Transversales

> Ce module regroupe les invariants **techniques et opérationnels** qui s'appliquent à tous les autres modules. Aucune fonctionnalité métier ne peut s'en affranchir.

### 0.1 Sourçage et Anti-Hallucination (cœur de la crédibilité)

> **Principe** : en finance verte/ESG, une affirmation non sourcée n'a aucune valeur. Un fund officer, un auditeur ou la PME elle-même doit pouvoir **cliquer et vérifier** chaque chiffre, chaque critère, chaque formule, chaque seuil. C'est l'avantage compétitif majeur de la plateforme.

**Entité `Source` (premier rang) :**
- `url` — URL officielle du document
- `title`, `publisher` (GCF, BOAD, IPCC, ADEME, IFC, UEMOA, etc.)
- `version`, `date_publi` — version du document au moment de la capture
- `page`, `section` — localisation exacte de l'extrait
- `captured_at`, `captured_by` — quand et par qui la source a été enregistrée
- `verified_by`, `verification_status` — un autre admin valide la pertinence (`pending` / `verified`)
- (post-MVP) `archived_url` — snapshot Wayback / archive interne ; `hash_contenu` pour détecter les changements

**Tools LLM dédiés (exposés via OpenRouter function-calling) :**
- `cite_source(source_id)` — référencer une source de la base vérifiée
- `search_source(query)` — rechercher dans le catalogue indexé
- `flag_unsourced(claim)` — marquer explicitement une assertion qu'on ne peut pas sourcer

**Règles d'instruction système au LLM (non négociables) :**
- *"Toute affirmation portant sur un critère, une formule, un seuil, un facteur d'émission ou une exigence d'un fonds/intermédiaire/référentiel DOIT être accompagnée d'un appel à `cite_source`. Sinon, dire explicitement : 'je ne dispose pas d'une source vérifiée pour cette information' et utiliser `search_source` ou `flag_unsourced`."*

**Validation backend stricte :**
- Tout message LLM contenant des chiffres de scoring, des descriptions de critères ou des assertions factuelles ESG/financières **sans `cite_source` correspondant** est **rejeté** ; le LLM doit retry. Pas négociable.

**Règles d'intégrité base de données :**
- Contrainte `NOT NULL` sur `source_id` pour : `Indicateur`, `Critère`, `Formule`, `Seuil`, `Facteur d'émission`, `Document requis`, `Référentiel`.
- Un objet du catalogue est en `draft` tant que sa source n'est pas marquée `verified` par un admin. Le LLM ne peut pas s'en servir tant qu'il est en `draft`.

**UI :**
- Picto "Source" cliquable sur **chaque** chiffre, score, critère, recommandation affiché à l'utilisateur → modal avec liste des sources, deep-links, version, date de capture, statut de vérification.
- Annexe **"Sources et références"** auto-générée dans tous les rapports PDF (cohérent avec un rapport scientifique ou d'audit).
- Badges visuels : `Source vérifiée` / `Source non vérifiée` / `Source obsolète`.

### 0.2 Authentification et Rôles (MVP simple)

- **Auth** : email + mot de passe uniquement. Hash bcrypt. JWT (24h) + refresh token rotatif.
- **2 rôles seulement** :
  - `PME` — utilisateur d'un compte PME (tous les utilisateurs d'une même PME ont les mêmes droits, équivalents).
  - `Admin` — équipe ESG Mefali, accès au back-office (Module 9), gestion catalogue/sources/PME en support.
- **Multi-tenant** : `account_id` sur chaque table métier + Row-Level Security PostgreSQL (isolation stricte entre PME).
- **Hors-scope MVP** (post-MVP) : OTP SMS, magic link, 2FA, RBAC granulaire (Owner/Member/Viewer).

### 0.3 Conformité Données Personnelles (minimum vital)

- **Page "Mes données"** par compte : voir, exporter (JSON), supprimer ses données.
- **Consentements granulaires** par usage (Mobile Money flux ≠ photos exploitation ≠ génération d'attestation).
- **Hébergement** : présence Europe ou Afrique de l'Ouest (cf. Architecture Technique).
- **Chiffrement** : TLS 1.3 in-transit ; at-rest via le chiffrement natif du fournisseur Postgres managé.
- **Politique de confidentialité** publiée + email de contact (`privacy@esg-mefali.com`).
- **Cadre légal** : RGPD européen + loi ivoirienne 2013-450 sur la protection des données + règlement UEMOA n°20/2010/CM/UEMOA.
- **Hors-scope MVP** : DPO formalisé, purge automatique granulaire fine.

### 0.4 Audit Log

- Table `audit_log` **append-only** : `{user_id, account_id, timestamp, entity_type, entity_id, field, old_value, new_value, source_of_change: manual|llm|import}`.
- MVP : log les éditions importantes (profil entreprise, projet, candidature, score, attestation, mutations LLM).
- Visible dans Module 7.2 "Historique des actions".
- Export CSV/JSON pour audit externe.
- Quasi-réglementaire en finance pour défense en cas de litige.

### 0.5 Versioning des Référentiels et Candidatures

- **Référentiels et critères versionnés** : champs `version`, `valid_from`, `valid_to`. Les évolutions de la taxonomie GCF, BOAD, etc. ne cassent pas l'historique.
- **Candidature** stocke un **snapshot JSON immuable** des entités au moment de la soumission (projet, critères de l'offre, référentiel actif, scores calculés). Permet de défendre la candidature si l'offre évolue après dépôt.
- Score recalculable contre snapshot historique pour audit.
- UI : badge **"Évalué selon Référentiel GCF v2.3 du 15/03/2026"** affiché sur chaque score persisté.

### 0.6 Devises et Taux de Change

- Toute valeur financière typée **`Money = {amount, currency}`**.
- **FCFA-EUR** : peg fixe **655,957** (pas d'API nécessaire).
- **USD et autres** : API gratuite (exchangerate-api.com tier gratuit, snapshot quotidien).
- Affichage : devise PME (FCFA par défaut) + devise du fonds en parallèle. Le simulateur 3.4 différencie devise d'emprunt et devise de remboursement (risque de change explicite).

### 0.7 Mapping ESG (cohérence transversale 2.2 ↔ 2.3 ↔ 3.1)

- Chaque entité est définie via la couche `Indicateur` (atomique, sourcé).
- `Référentiel` = collection d'indicateurs + seuils + poids + sources.
- `Critère d'Offre` = condition logique paramétrable sur un ou plusieurs indicateurs (ex : `indicateur_id ≥ seuil`).
- `Grille ESG` (Module 2.2) = projection pédagogique du catalogue d'indicateurs principaux par pilier (E/S/G).
- **Une seule réponse de la PME alimente potentiellement plusieurs scores** (ESG Mefali + GCF + IFC + BOAD…) sans duplication de saisie.

---

## Module 1 : Agent Conversationnel Principal

### 1.1 Interface de Chat Multimodale
- Chat en langage naturel en français (langues locales et anglais plus tard)
- Historique des conversations persistant
- Interface de chat flottant accessible depuis toutes les pages
- Les données utilisateur se mettent à jour de façon réactive : lorsque l'utilisateur est sur une page dont une donnée est modifiée par le LLM, il le voit en temps réel.
- Le LLM doit savoir sur quelle page l'utilisateur se trouve (chat flottant, contexte de page).

#### 1.1.1 Chat Interactif — Tools de Réponse en Bottom Sheet

> **Principe** : le chat n'est pas qu'un échange textuel. Quand le LLM doit poser une question fermée (choix unique, choix multiples, sélection dans une liste, confirmation, sélection de date, etc.), il invoque un **tool dédié de réponse**. La **question** reste affichée normalement dans la bulle du LLM (texte). La **zone de réponse**, elle, prend la forme d'un **bottom sheet qui remplace temporairement la barre de saisie** en bas de l'écran : l'utilisateur y trouve les options cliquables (radios, cases à cocher, sélecteurs, etc.) et un bouton "Valider". Le widget interactif n'est **jamais rendu à l'intérieur de la bulle du LLM** — il est toujours en bas, à la place de l'input.
>
> Inspiration UX : à la manière de l'extension Claude Code dans VS Code (réponses guidées par composants), mais avec une séparation stricte question (haut, dans la conversation) / réponse (bas, à la place de l'input).

**Tools de réponse à exposer au LLM (liste évolutive) :**
- `ask_qcu` — Question à Choix Unique (QCU) : bottom sheet avec liste de boutons radio + bouton "Valider". Ex : "Quelle est votre forme juridique ?" → SARL / SA / SAS / Coopérative / Autre.
- `ask_qcm` — Question à Choix Multiples (QCM) : bottom sheet avec liste de cases à cocher + bouton "Valider". Ex : "Quels piliers ESG vous concernent ?" → Environnement / Social / Gouvernance.
- `ask_yes_no` — Confirmation binaire : bottom sheet avec deux boutons "Oui" / "Non" (variantes : Confirmer/Annuler, Continuer/Plus tard).
- `ask_select` — Sélection dans une liste longue avec recherche (pays, secteur d'activité, fonds, intermédiaire, source, ...).
- `ask_number` — Saisie numérique avec unité et bornes (CA, effectifs, montant, tCO2e).
- `ask_date` / `ask_date_range` — Sélecteur de date(s).
- `ask_rating` — Échelle (1-5, 1-10) pour auto-évaluation de pratiques.
- `ask_file_upload` — Bouton d'upload contextualisé.
- `show_form` — Mini-formulaire multi-champs (ex : créer un projet en une fois).
- `show_summary_card` — Carte récapitulative actionnable (ex : "Voici les infos extraites de votre document — corriger / valider").

**Comportement attendu (UX) :**
- **Question** : rendue en texte normal dans la bulle du LLM, dans le fil de conversation.
- **Zone de réponse** : la barre de saisie textuelle est masquée et remplacée par un **bottom sheet** contenant l'UI interactive du tool. Aucun composant interactif n'est rendu dans la bulle du LLM elle-même.
- **Bascule "Répondre librement"** : un bouton toujours visible dans le bottom sheet permet à l'utilisateur de fermer le widget et de revenir à la saisie textuelle libre. Le LLM s'adapte alors à une réponse en texte libre.
- **Validation** : après clic sur "Valider" (ou saisie libre), la réponse de l'utilisateur apparaît comme un **message utilisateur normal** dans le fil de conversation (avec une représentation textuelle lisible du/des choix : ex : "✓ SARL", ou "✓ Environnement, Gouvernance"). Le bottom sheet est ensuite dismissed et la barre de saisie textuelle réapparaît.
- **Traçabilité** : le payload structuré de la réponse est conservé en métadonnée du message utilisateur, pour permettre au LLM de retraiter la réponse sans réinterpréter du texte.
- **Pas de réponse dans le widget LLM** : règle stricte — l'UI de saisie est toujours en bas (zone d'input), jamais inline dans la bulle du LLM. Cohérence : "haut = ce que dit l'autre, bas = ce que je dis/choisis".
- **Cohérence visuelle** : composants alignés avec le design system de la plateforme (TailwindCSS v4 + gsap pour les transitions d'apparition/disparition du bottom sheet).
- **Instruction système au LLM** : préférer le tool de réponse adapté à toute question fermée plutôt qu'une question ouverte.

#### 1.1.2 Réponses Graphiques + Textuelles

> **Principe** : un message du LLM ne se limite pas à du texte. Quand une visualisation clarifie le propos (chiffre clé, évolution, comparaison, répartition, processus), le LLM invoque un **tool de visualisation** qui rend un composant graphique inline dans le fil de conversation. Le rendu est piloté par du **JSON structuré et validé** (pas de code généré par le LLM), ce qui garantit la robustesse, la cohérence visuelle avec le design system et l'interactivité (drill-down, hover, mise à jour réactive).

**Approche : hybride (catalogue de tools typés + Mermaid en fallback ad-hoc)**

- Pour les visualisations récurrentes et critiques (scores, KPI, évolutions, comparaisons) → **tool dédié typé** : le LLM remplit un payload JSON validé côté backend (Pydantic), le frontend rend un composant Vue stylé avec le design system.
- Pour les diagrammes ad-hoc non couverts par le catalogue (processus, décisions, organigrammes) → **`show_mermaid`** : le LLM produit du code Mermaid, validé côté backend (parse avant envoi front, fallback texte si invalide).
- Instruction système au LLM : *"si un tool de visualisation existe pour ce que tu veux montrer, utilise-le ; sinon utilise `show_mermaid` ; sinon réponds en texte. Préfère un visuel + une phrase d'analyse à un long paragraphe descriptif."*

**Catalogue de tools de visualisation à exposer au LLM (liste évolutive) :**

| Tool | Quand l'utiliser | Lib de rendu |
|---|---|---|
| `show_kpi_card` | Chiffre clé + delta (ex : "45 tCO2e ↓12% vs 2024") | Vue + Tailwind |
| `show_progress_bar` | Avancement vers un objectif/seuil (ex : score ESG vs seuil GCF) | Vue + Tailwind |
| `show_radar_chart` | Scores E/S/G par pilier, comparaison multi-référentiels | chart.js |
| `show_bar_chart` | Benchmarking sectoriel, scores par référentiel, ventilation | chart.js |
| `show_line_chart` | Évolution score ESG / empreinte carbone dans le temps | chart.js |
| `show_pie_chart` / `show_donut_chart` | Répartition (sources d'émissions, allocation budget) | chart.js |
| `show_timeline` | Étapes d'une candidature, roadmap projet, échéances offres | composant Vue dédié |
| `show_comparison_table` | Offres A vs B vs C sur critères, intermédiaires concurrents | Vue + Tailwind |
| `show_match_card` | Carte "Projet X ↔ Offre Y, compatibilité 78%" cliquable (renvoie au Module 3) | Vue dédiée |
| `show_map` | Localisation projets/entreprise/zones d'impact | Leaflet |
| `show_mermaid` | Diagramme libre (processus, décision, flux) — fallback ad-hoc | mermaid |

**Anatomie d'un message LLM "graphique + textuel" :**

```
[Texte d'introduction explicatif + cite_source(...) si chiffres présents]
[Tool de visualisation invoqué → composant rendu inline dans le fil]
[Texte d'analyse / interprétation après le visuel]
[Optionnel : tool QCU/QCM de 1.1.1 pour la suite "Voulez-vous explorer X ou Y ?"]
```

Le LLM peut chaîner **plusieurs tools dans un même tour** (ex : un radar + une barre de progression + une question QCU) → une seule réponse, mise en page riche.

**Comportement attendu :**
- Chaque tool reçoit un **payload JSON typé** validé par Pydantic côté backend ; tout payload invalide est rejeté avant envoi au frontend.
- Les visualisations sont **réactives** : si la donnée sous-jacente évolue (ex : score ESG recalculé après upload d'un nouveau document), le composant rendu dans l'historique se met à jour en temps réel.
- Les visualisations restent **interactives dans l'historique** : hover/clic possibles même sur des messages anciens (pas de gel après envoi).
- Cohérence visuelle stricte avec le design system (palette, typographies, animations gsap).
- **Accessibilité** : chaque visualisation est accompagnée d'un **alt-text textuel généré par le LLM** décrivant ce qu'elle montre.
- **Sourçage** : tout chiffre affiché dans une visualisation a une source cliquable (Module 0.1).

**Architecture technique :**
- **Backend FastAPI** : tools déclarés via function-calling OpenRouter, schéma de payload défini par modèles Pydantic. Validation systématique.
- **Frontend Nuxt 4** : composant `<ChatMessageRenderer>` qui switche sur `payload.type` → composant Vue dédié par tool.
- **Persistance** : le payload JSON de chaque tool invocation est stocké avec l'historique de conversation, pour permettre le re-rendu fidèle des messages anciens (et l'export de rapports).

#### 1.1.3 LLM Moteur d'Action sur la Plateforme

> **Principe** : le LLM ne fait pas que répondre — il peut **effectuer toute action métier** sur la plateforme via des **tools de mutation** dédiés. L'utilisateur peut tout faire en langage naturel ("crée un projet de panneaux solaires", "marque la candidature BOAD comme acceptée", "génère le dossier pour l'offre GCF/BOAD"), avec confirmation systématique pour les actions destructives ou irréversibles.

**Tools de mutation à exposer au LLM (liste évolutive, MVP) :**
- `update_company_profile(fields)` — modifier le profil entreprise
- `create_project(fields)` / `update_project(id, fields)` / `delete_project(id)`
- `create_candidature(project_id, offre_id)` / `update_candidature_status(id, status)` / `delete_candidature(id)`
- `attach_document(entity_type, entity_id, doc_id)`
- `recompute_score(entity_id, referentiel_id)`
- `generate_attestation(score_id)` / `revoke_attestation(id)`
- `generate_dossier(candidature_id, language)`

**Garde-fous obligatoires :**
- Toute action **destructive** (delete, revoke, écrasement majeur) → confirmation via `ask_yes_no` (Module 1.1.1) avant exécution.
- Toute action est **journalisée** dans l'audit log (Module 0.4) avec `source_of_change = llm`.
- Le LLM ne peut **JAMAIS** modifier le catalogue (Fonds, Intermédiaires, Référentiels, Indicateurs, Sources, Templates) — réservé aux admins via le back-office (Module 9).
- Les mutations sont **scoped au compte** : Row-Level Security garantit qu'un LLM agissant pour une PME ne peut jamais toucher les données d'une autre PME.

### 1.2 Profilage Intelligent de l'Entreprise

Décrit **l'entité Entreprise** uniquement.

- Questions conversationnelles du LLM pour comprendre l'activité
- Extraction automatique des champs :
  - Secteur d'activité (agriculture, énergie, recyclage, transport, etc.)
  - Taille de l'entreprise (CA, effectifs)
  - Localisation géographique (siège, zones d'opération)
  - Pratiques environnementales actuelles
  - Structure de gouvernance
- Création d'un profil entreprise enrichi au fil des conversations
- **Édition manuelle** : tous les champs renseignés automatiquement par le LLM doivent également être consultables et modifiables manuellement depuis la vue **Profil → Entreprise**. L'utilisateur peut corriger, compléter ou écraser les valeurs extraites par le LLM à tout moment. Toute modification manuelle est synchronisée avec le contexte du LLM (Module 1.4) pour éviter les régressions au prochain échange. Toute édition est journalisée (Module 0.4).

### 1.3 Profilage des Projets Verts

Décrit **l'entité Projet** uniquement (le matching projet ↔ offre est géré par le Module 3).

- Questions conversationnelles du LLM pour formaliser chaque projet vert porté par l'entreprise
- Extraction et structuration des champs par projet :
  - **Identité** : nom, description, objectif environnemental
  - **Type d'impact** : mitigation carbone, adaptation, biodiversité, économie circulaire, eau, énergies renouvelables, agriculture durable, etc.
  - **Maturité** : phase (idéation / pré-faisabilité / pilote / scale / réplication)
  - **Aspects financiers** : montant recherché, durée, structure de financement souhaitée (subvention, prêt concessionnel, equity, blending)
  - **Indicateurs d'impact attendus** : tCO2e évitées/séquestrées, emplois verts créés, bénéficiaires, hectares restaurés, etc.
  - **Localisation du projet** (peut différer du siège de l'entreprise)
  - **Statut** : brouillon / en recherche de financement / financé / en exécution / clôturé
  - **Documents projet** : étude de faisabilité, business plan vert, étude d'impact, lettres de soutien
- Comportements proactifs du LLM :
  - Identifier les projets verts potentiels à partir des activités décrites en 1.2
  - Reformuler une activité existante en projet finançable
  - Découper un grand projet en sous-projets adaptés à différentes offres
- **Édition manuelle** : tous les champs sont consultables et modifiables depuis la vue **Profil → Projets** (création, édition, duplication, suppression d'un projet). L'utilisateur peut corriger, compléter ou écraser les valeurs extraites par le LLM. Toute modification est synchronisée avec le contexte LLM (1.4) et journalisée (0.4).

### 1.4 Mémoire Contextuelle (MVP simplifié)

- **Profil entreprise + projets** : injectés systématiquement à chaque tour du LLM (budget tokens contrôlé).
- **15 derniers messages** : conservés en clair dans le contexte.
- **Historique ancien** : indexé via **pgvector** (RAG basique), récupéré à la demande via le tool `recall_history(query)`.
- Synchronisation bidirectionnelle avec les éditions manuelles du Profil (1.2 + 1.3) pour éviter les régressions.
- **Hors-scope MVP** : digest périodique automatique, snapshot mensuel du profil (post-MVP).

---

## Module 2 : Analyseur de Conformité ESG

### 2.1 Upload et Analyse de Documents
- Upload de documents (PDF, images, Word, Excel)
- OCR intégré pour les documents scannés (les documents peuvent être en anglais ou français — l'OCR doit comprendre les deux)
- Extraction intelligente des informations via le LLM :
  - Statuts juridiques
  - Rapports d'activité
  - Factures et justificatifs
  - Contrats fournisseurs
  - Politiques internes

### 2.2 Grille d'Évaluation ESG Contextualisée

> **Note (cf. Module 0.7)** : la grille ci-dessous est une **projection pédagogique** des indicateurs principaux par pilier. Chaque sous-thème est une catégorie d'`Indicateurs` atomiques (sourcés Module 0.1) qui alimentent les scores multi-référentiels du 2.3.

- **Environnement (E) :**
  - Gestion des déchets et recyclage
  - Consommation énergétique
  - Émissions carbone estimées
  - Utilisation des ressources naturelles
  - Impact sur la biodiversité locale

- **Social (S) :**
  - Conditions de travail
  - Égalité homme/femme
  - Formation des employés
  - Impact communautaire
  - Santé et sécurité

- **Gouvernance (G) :**
  - Transparence financière
  - Structure de décision
  - Éthique des affaires
  - Conformité réglementaire
  - Lutte anti-corruption

### 2.3 Scoring ESG Dynamique (multi-référentiels)

> **Principe** : un score ESG n'a de sens que par rapport à un référentiel. La plateforme adopte une approche **hybride** : un score synthétique "ESG Mefali" en vitrine pour la lisibilité, complété par des scores détaillés par référentiel (fonds source ET intermédiaires), calculés à partir du même catalogue d'indicateurs (Module 0.7). Chaque score, formule, seuil et pondération est **sourcé** (Module 0.1).

#### 2.3.1 Référentiel propre "ESG Mefali"
- Score global sur 100 points (vitrine principale du tableau de bord)
- Scores détaillés par pilier (E, S, G)
- Pondération adaptée aux PME africaines francophones — **grille auditable et sourcée** (Module 0.1)
- Synthèse pédagogique : un seul chiffre que l'utilisateur peut comprendre et partager
- Badges et certifications virtuelles ESG Mefali

#### 2.3.2 Scores par référentiel externe
À partir du même profil entreprise/projet et des mêmes documents, la plateforme calcule en parallèle des scores selon :

**Référentiels de fonds source :**
- **Taxonomie verte UEMOA / BCEAO** (éligibilité aux fonds régionaux)
- **Critères d'investissement GCF** (Fonds Vert pour le Climat — 8 critères)
- **IFC Performance Standards** (BAD, BOAD, banques internationales)
- **GRI Standards** (reporting volontaire exigé par certains fonds)
- **ODD ONU** (cadre narratif pour les sections qualitatives des dossiers)

**Référentiels propres aux intermédiaires** (couche supplémentaire au-dessus du fonds source) :
- Politique sectorielle BOAD (NIE pour le GCF, le FEM, le Fonds d'Adaptation)
- Politique de sauvegardes ESS de la BAD
- Standards SUNREF (pour les banques locales partenaires AFD)
- Politiques propres des banques commerciales partenaires (Ecobank, NSIA, Orabank…)
- Critères des développeurs de projet carbone (Atmosfair, South Pole…)

> **Important** : un projet peut être "GCF-éligible" et simultanément "BOAD-incompatible". L'intermédiaire est souvent le **vrai filtre**.

Liste évolutive : nouveaux référentiels ajoutables sans refonte (référentiel = configuration sourcée, pas code).

Pour chaque référentiel : score, critères couverts, critères manquants, écart au seuil d'éligibilité — **chaque élément cliquable vers sa source officielle**.

#### 2.3.3 Activation contextuelle des référentiels
- Lorsqu'un projet (Module 1.3) cible une **Offre** spécifique via le matching (Module 3.2), la plateforme calcule et met en avant **deux scores** :
  - Score selon le référentiel du **fonds source**
  - Score selon le référentiel de l'**intermédiaire**
- C'est le **minimum des deux** qui détermine l'éligibilité réelle.
- Exemple : projet ciblant l'Offre "GCF via BOAD" → vue dédiée affichant les deux scores côte-à-côte avec identification du goulot d'étranglement.

#### 2.3.4 Transversal
- Benchmarking sectoriel (comparaison avec d'autres PME du secteur, pour chaque référentiel)
- Évolution du score dans le temps (graphique d'évolution, sélecteur de référentiel) — chaque point versionné (Module 0.5)
- Explicabilité : chaque score est accompagné de la liste des indicateurs et de leur poids, **chaque indicateur cliquable vers sa source**

### 2.4 Rapport de Conformité Généré
- Rapport PDF automatique en français
- **Sélection du/des référentiels** à inclure dans le rapport (ESG Mefali par défaut, plus 1 à N référentiels externes au choix — fonds et/ou intermédiaires)
- Visualisations graphiques (radar charts par référentiel, barres de progression)
- Identification des points forts
- Liste priorisée des lacunes à combler (avec attribution au(x) référentiel(s) concerné(s))
- **Annexe technique** : méthodologie de calcul et table des indicateurs par référentiel
- **Annexe "Sources et références"** auto-générée listant toutes les sources mobilisées dans le rapport (URL, version, date) — Module 0.1

---

## Module 3 : Conseiller en Financement Vert

> **Vérité du terrain** : la plupart des grands fonds verts ne décaissent **jamais directement** aux PME africaines. Le module est structuré autour de **trois entités** — Fonds source, Intermédiaire accrédité, Offre (couple Fonds × Intermédiaire) — où c'est l'Offre qui est l'unité commercialement accessible à une PME.

### 3.1 Catalogue : Fonds, Intermédiaires, Offres

**Maintenu par les admins ESG Mefali via le back-office (Module 9).** Chaque entité du catalogue a au moins une `Source` vérifiée (Module 0.1) et est versionnée (Module 0.5).

#### 3.1.1 Fonds source (la source ultime de l'argent)

Pour chaque fonds, on stocke :
- Identité (nom, organisation, type : multilatéral / bilatéral / régional / national / privé)
- Thématique (mitigation, adaptation, biodiversité, économie circulaire, mixte)
- Instruments (subvention, prêt concessionnel, garantie, equity, blending)
- Plafonds et planchers de financement (Money typé — Module 0.6)
- Éligibilité géographique
- Critères et taxonomie propres (référentiel — voir 2.3) **sourcés**
- Liste des intermédiaires accrédités (datée)
- `submission_mode` : `rolling` (guichet ouvert) ou `call_for_proposals` (avec sessions datées)

Exemples (liste évolutive) :
- **Multilatéraux climat :** GCF, GEF/FEM, Fonds d'Adaptation
- **Bilatéraux :** AFD, KfW, JICA, Norad, USAID
- **Régionaux Afrique :** BAD, BOAD, BIDC, BADEA
- **Marchés carbone :** Verra, Gold Standard, Plan Vivo, REDD+
- **Programmes nationaux :** Fonds National pour l'Environnement (Côte d'Ivoire), équivalents par pays UEMOA/CEDEAO

#### 3.1.2 Intermédiaires accrédités

Pour chaque intermédiaire, on stocke :
- Identité (nom, type : DAE / Implementing Agency / NIE-RIE-MIE / banque locale partenaire / développeur de projet carbone / agence nationale)
- Pays et zone d'opération
- Fonds source pour lesquels il est accrédité (avec dates d'accréditation et plafonds par fonds) — **sourcé**
- Critères propres d'éligibilité (sectoriels, taille PME, géographie, type de projet) — **sourcés**
- Documents propres requis (souvent en plus des documents du fonds) — **sourcés**
- Frais : tarification de dossier, marge sur prêts, garanties exigées, taux de change appliqué — **sourcés**
- Délais moyens (instruction, décaissement)
- Portail de soumission / contact / canal de communication
- Track record (volume mobilisé, taux de succès si disponible)

Exemples (liste évolutive) :
- **DAE/NIE pour le GCF en Afrique de l'Ouest :** BOAD (NIE), AfDB, CDP, Acumen
- **Agences d'implémentation FEM :** PNUD, PNUE, BAD, BOAD, FAO, IUCN
- **Banques locales SUNREF (AFD) :** Ecobank, NSIA, Orabank, Coris Bank — par pays
- **Lignes vertes BAD :** banques commerciales partenaires par pays
- **Développeurs de projet carbone :** Atmosfair, South Pole, ClimatePartner

#### 3.1.3 Offres = couples (Fonds source × Intermédiaire)

Une **Offre** est l'agrégation d'un fonds source et d'un intermédiaire accrédité, calculée :
- **Critères effectifs** = critères fonds ∩ critères intermédiaire (souvent plus restrictifs que le fonds seul)
- **Documents effectifs** = documents fonds ∪ documents intermédiaire
- **Frais effectifs** = frais fonds + marges intermédiaire
- **Délais effectifs** = délais fonds + délais intermédiaire
- **Référentiel effectif** = référentiel fonds + couche supplémentaire intermédiaire (Module 2.3)
- `accepted_languages` : liste des langues acceptées pour le dossier (FR, EN, …) — voir 3.3

C'est **l'Offre** qui est exposée à l'utilisateur dans le matching, le simulateur et la candidature — pas le fonds nu.

### 3.2 Matching Intelligent Projet ↔ Offre

- Analyse d'éligibilité automatique : projet × offre → score de compatibilité
- **Décomposition en deux scores** : compatibilité fonds source ET compatibilité intermédiaire (l'intermédiaire est souvent le vrai filtre)
- Explication des critères manquants pour chaque couche (fonds, intermédiaire) — **chaque critère cliquable vers sa source**
- Recommandations personnalisées d'offres
- **Comparateur d'offres pour un même fonds source via plusieurs intermédiaires** (ex : GCF via BOAD vs GCF via UNDP — délais, frais, exigences, taux de succès) — différenciation majeure vs autres plateformes
- Alertes sur les nouveaux appels à projets (par fonds, par intermédiaire, par offre)

### 3.3 Générateur de Dossiers de Candidature

- Templates pré-remplis **par offre** (un template = un format imposé par un couple Fonds-Intermédiaire) — chaque template référencé par une `Source`
- Génération automatique des sections narratives à partir du profil entreprise + projet
- **Langue de génération** : sélecteur basé sur `accepted_languages` de l'offre (FR par défaut, EN optionnel pour MVP)
- Suggestions de formulation adaptées aux critères de l'offre (ton, vocabulaire, focus)
- Checklist documentaire = union des documents fonds + intermédiaire
- Génération possible **en parallèle** pour plusieurs offres ciblant le même projet (réutilisation des contenus narratifs avec adaptations par offre)
- Export en formats compatibles (Word, PDF) selon les exigences de chaque intermédiaire
- L'attestation ESG Mefali (Module 5.3) peut être incluse dans le dossier

### 3.4 Simulateur de Financement

- Estimation du montant éligible (fonction des plafonds de l'offre — Money typé Module 0.6)
- **Coût total réel pour la PME** = montant emprunté + marges intermédiaire + frais de dossier + garanties (différencie subvention vs prêt concessionnel vs blending)
- Calcul du retour sur investissement vert — méthodologie sourcée (post-MVP : framework IRIS+ ou Verra)
- Projection de l'impact environnemental — facteurs sourcés (Module 0.1 + Module 4)
- Timeline réaliste = délais fonds + délais intermédiaire
- **Comparateur multi-offres** : "Quelle offre vous coûte le moins / vous va le plus vite / a le meilleur taux de succès ?"

---

## Module 4 : Calculateur d'Empreinte Carbone

### 4.1 Questionnaire Conversationnel Simplifié
- Questions adaptées au contexte africain (utilise les tools 1.1.1)
- Exemples concrets et unités locales
- Catégories principales :
  - Énergie (électricité, générateurs, gaz)
  - Transport (véhicules, livraisons)
  - Déchets (volumes, traitement)
  - Achats (matières premières, fournitures)

### 4.2 Calcul et Visualisation
- Empreinte carbone annuelle estimée (tCO2e) — rendue via `show_kpi_card` (1.1.2)
- Répartition par source d'émission — rendue via `show_pie_chart` ou `show_donut_chart`
- Comparaison avec moyennes sectorielles — `show_bar_chart`
- Évolution mensuelle/annuelle — `show_line_chart`
- **Facteurs d'émission sourcés** :
  - Source primaire : **ADEME Base Carbone v23** (français, gratuit, contient facteurs Afrique) + **IPCC AR6** + **IEA Africa Energy Outlook**
  - Mix électrique par pays UEMOA stocké en table de constantes versionnée (8 pays principaux)
  - Affichage utilisateur : "Facteur utilisé : 0,456 kgCO2e/kWh (mix Côte d'Ivoire 2024, source ADEME Base Carbone v23, page 87)" + lien source cliquable

### 4.3 Plan de Réduction
- Recommandations priorisées par impact
- Estimation des économies financières (Money typé Module 0.6)
- Actions quick-wins vs long terme
- Suivi des objectifs de réduction
- Chaque recommandation est sourcée (référentiel ADEME, IEA, BOAD policies, etc.)

---

## Module 5 : Scoring de Crédit Vert Alternatif

### 5.1 Collecte de Données Non-Conventionnelles

**Tous les usages ci-dessous nécessitent un consentement granulaire explicite (Module 0.3).**

- **Intégration Mobile Money :**
  - Analyse des flux (avec consentement spécifique)
  - Régularité des transactions
  - Volume d'activité

- **Données déclaratives enrichies :**
  - Questionnaire sur les pratiques (via tools 1.1.1)
  - Photos de l'exploitation (analysées par IA, consentement spécifique)
  - Témoignages clients/fournisseurs

- **Données publiques :**
  - Présence sur les réseaux sociaux
  - Avis et recommandations
  - Participation à des programmes verts

### 5.2 Algorithme de Scoring Hybride
- Score de solvabilité (0-100)
- Score d'impact vert (0-100)
- Score combiné pondéré
- **Méthodologie publiée et sourcée** (Module 0.1) — la PME et tout tiers peut consulter la formule, les pondérations et leur justification
- Explication transparente des facteurs : chaque facteur cliquable → contribution au score + source

### 5.3 Attestation et Certification du Score

> **Principe** : la plateforme étant **fermée aux intermédiaires**, le partage du score se fait via une **attestation vérifiable** que la PME contrôle et transmet par ses propres canaux (email, portail intermédiaire, dossier de candidature).

- **Attestation PDF** générée par la PME depuis la plateforme, contenant :
  - Score(s) — solvabilité, impact vert, ESG par référentiel sélectionné
  - Référentiel(s) utilisé(s) avec versions (Module 0.5)
  - Date d'émission, identifiant unique, validité
  - **Signature numérique** ESG Mefali (Ed25519 ou équivalent simple, pas besoin de PKI complexe pour MVP)
  - **QR code** pointant vers une URL publique de vérification : `https://esg-mefali.com/verify/{attestation_id}`
- **Page publique de vérification** read-only (`/verify/{id}`) :
  - Affiche : authentique / révoquée + métadonnées non sensibles (date, score, référentiel, hash document conforme)
  - Aucune authentification requise (un fund officer scanne et vérifie)
  - **Aucune donnée sensible** au-delà de ce qui figure déjà sur l'attestation
- **Révocation** possible par la PME (changement majeur du profil) ou par un admin (incident détecté) → la page de vérif affiche "Attestation révoquée le X"
- Historique et évolution du score (interne à la PME et aux admins ESG Mefali)
- L'attestation s'intègre naturellement aux dossiers de candidature générés en 3.3

---

## Module 6 : Plan d'Action et Accompagnement

### 6.1 Générateur de Feuille de Route
- Plan d'action personnalisé sur 6-12-24 mois
- Étapes concrètes et atteignables
- Ressources et outils recommandés (chaque ressource sourcée)
- Estimation des coûts et bénéfices (Money typé)
- Intègre les délais d'instruction des offres ciblées (Module 3.4)

### 6.2 Système de Suivi et Rappels (cron)
- Notifications pour les échéances (appels à projets, dates limites par offre — `submission_mode = call_for_proposals`)
- Rappels pour les actions planifiées
- Rappels de relance auprès des intermédiaires (si silence radio sur une candidature)
- Célébration des progrès (gamification)
- Ajustement dynamique du plan

### 6.3 Bibliothèque de Ressources
- Guides pratiques ESG en français — chaque guide sourcé
- Modèles de documents (politiques, procédures)
- Formations vidéo courtes
- FAQ contextualisées
- **Fiches par intermédiaire** : "Comment soumettre à BOAD", "Comment travailler avec PNUD", etc.

---

## Module 7 : Tableau de Bord PME

### 7.1 Dashboard Principal
- Vue synthétique des scores (ESG Mefali + référentiels actifs) — chaque score cliquable vers sources
- Graphiques d'évolution
- Prochaines actions recommandées
- **Statut des candidatures par offre** (couple Fonds × Intermédiaire) — étape, prochain rappel, prochaine échéance
- Carte des intermédiaires actifs et de leurs accréditations en cours

### 7.2 Rapports, Exports et Audit Log
- Rapport ESG complet téléchargeable (multi-référentiels — Module 2.4)
- Rapport carbone
- Attestation de scoring (Module 5.3)
- Historique des analyses
- Historique des candidatures par offre
- **Historique des actions** (audit log Module 0.4) — visible par les utilisateurs PME pour leur compte
- Page **"Mes données"** (RGPD/UEMOA) : voir, exporter (JSON), supprimer

### 7.3 Multi-utilisateurs (simplifié MVP)
- Tous les utilisateurs d'une PME ont le rôle `PME` et des droits équivalents (Module 0.2)
- Commentaires et notes internes libres sur projets et candidatures
- L'audit log (0.4) trace qui a fait quoi
- **Hors-scope MVP** : workflow d'approbation interne (post-MVP, si demande)

---

## Module 8 : Extension Chrome — Accompagnement sur les Sites de Fonds **et d'Intermédiaires**

> Utilisée par la PME elle-même quand elle navigue sur les sites des intermédiaires/fonds source. Pas un point d'accès pour les intermédiaires.

### 8.1 Détection Automatique
- Détection des sites de **fonds source** (BOAD, GCF, BAD, AFD…)
- Détection des sites des **intermédiaires accrédités** (banques locales SUNREF, portails NIE, plateformes développeurs carbone…) — souvent c'est là que la PME va réellement
- Observation SPA (Single Page Application) pour suivre la navigation
- Bandeau de notification discret informant l'utilisateur qu'une **offre** compatible a été détectée (identification automatique du couple Fonds × Intermédiaire selon le contexte du portail)
- Support des patterns d'URL configurables par fonds ET par intermédiaire

### 8.2 Pré-remplissage Intelligent des Formulaires
- Remplissage automatique des champs à partir du profil entreprise + projet
- Adaptation au format spécifique de l'**intermédiaire** (pas seulement du fonds source)
- Suggestions IA contextuelles pour chaque champ (descriptions de projet, motivations, justifications)
- Remplissage séquentiel animé ("Tout remplir") pour visualiser le processus
- Code couleur des champs : vert (auto-rempli), bleu (suggéré par IA), orange (à remplir manuellement)

### 8.3 Panneau Latéral de Guidage
- Guide pas-à-pas spécifique à l'**offre** (couple Fonds × Intermédiaire), pas seulement au fonds
- Composants dédiés : barre de progression, navigateur d'étapes, aide par champ
- Checklist documentaire = union documents fonds + intermédiaire
- Mini-chat IA contextuel pour poser des questions en temps réel pendant le remplissage

### 8.4 Suivi des Candidatures
- Une candidature = un couple (Projet, Offre)
- Création automatique d'une candidature dès la détection d'une offre
- Sauvegarde de la progression entre les sessions
- Tableau de bord des candidatures en cours dans le popup
- Détail de chaque candidature avec statut, étape chez l'intermédiaire, étapes restantes
- **Mise à jour du statut** : saisie manuelle par la PME OU via une instruction au LLM (qui invoque `update_candidature_status` — Module 1.1.3). Pas d'email parsing pour MVP.

### 8.5 Notifications et Rappels
- Alertes d'échéances (J-30, J-7, J-1 avant date limite de l'offre)
- Rappels pour les candidatures inactives (3+ jours sans activité)
- Déduplication intelligente des notifications
- Cycle d'alarmes automatique (vérification toutes les 6h)

### 8.6 Recommandations d'Offres
- Suggestions d'**offres** (et non de fonds nus) compatibles basées sur le profil et les scores ESG multi-référentiels
- Score de compatibilité pour chaque offre recommandée (décomposé fonds + intermédiaire)
- Comparaison côte-à-côte d'offres concurrentes pour un même fonds source
- Accès direct au site de l'intermédiaire (pas du fonds source) depuis l'extension

### 8.7 Multilingue
- Interface disponible en français et en anglais
- Internationalisation via chrome.i18n
- Français comme langue par défaut

---

## Module 9 : Back-Office Admin (équipe ESG Mefali)

> Sans ce module, **personne ne peut peupler le catalogue → plateforme inutile**. Réservé aux comptes `Admin` (Module 0.2).

### 9.1 Gestion du Catalogue
- CRUD sur : `Fonds source`, `Intermédiaire`, `Offre`, `Référentiel`, `Indicateur`, `Critère`, `Document requis`, `Template de dossier`, `Source`, `Facteur d'émission`
- Workflow simple `draft → published` (un objet n'est `published` que si toutes ses `Sources` sont marquées `verified`)
- Versioning automatique (Module 0.5)
- Interface : formulaires Tailwind simples, pas besoin d'UI fancy pour MVP

### 9.2 Gestion des Sources
- Saisie manuelle d'une source (URL, titre, publisher, version, date, page, …)
- Marquage `pending` → un autre admin valide → `verified`
- Lien vers les entités qui dépendent de cette source (impact analysis avant modification/suppression)

### 9.3 Support PME
- Vue lecture seule des comptes PME (avec audit log de chaque consultation par un admin — traçabilité)
- Outils de réinitialisation mot de passe, déblocage compte
- Régénération/révocation d'attestations (Module 5.3) en cas d'incident

### 9.4 Métriques Admin
- Nombre de sources `pending` / `verified` / `outdated`
- Nombre de PME actives, candidatures en cours, attestations émises
- Coûts LLM agrégés (post-MVP : par PME)

---

## Module 10 : Stratégie de Fiabilité du Tool-Use LLM

> **Problème** : avec un catalogue riche de tools (réponse 1.1.1, visualisation 1.1.2, mutation 1.1.3, lecture/calcul/recherche), un LLM laissé seul face à 30+ outils dégrade rapidement (mauvais tool, mauvais payload, hallucination de schéma). Ce module définit la stratégie pour garantir que **le bon tool est invoqué avec le bon payload, à chaque tour**.

### 10.1 Architecture en couches : routage déterministe + LLM (LangGraph)

Ne pas exposer l'intégralité du catalogue de tools au LLM à chaque tour. Mettre devant lui un **graphe LangGraph** :

```
[Classifier d'intention] → [Sélecteur de sous-ensemble de tools] → [LLM avec tools filtrés] → [Validateur Pydantic] → [Réponse]
```

- Le **classifier** (LLM léger ou règles) détermine la nature de la demande : profilage, mutation, analyse, navigation, question fermée.
- Le **sélecteur** charge **5–10 tools maximum** par tour (jamais plus), choisis selon : intention détectée + page courante + entités actives dans le contexte.
- Règle : un LLM avec 30 tools dégrade vite ; avec 8 tools bien choisis, il est presque infaillible.

### 10.2 Tools auto-descriptifs et discriminants

Chaque tool exposé doit avoir :
- **Nom verbal sans ambiguïté** : `ask_qcu`, `show_radar_chart`, `update_candidature_status` (jamais `display_data`, `do_thing`).
- **Description avec règles "use when / don't use when"** explicites :
  > "Utilise `ask_qcu` UNIQUEMENT si la question a 2–7 réponses mutuellement exclusives. Pour >7 options, utilise `ask_select`. Pour des choix non exclusifs, utilise `ask_qcm`."
- **Exemples positifs et négatifs** dans la description (few-shot inline).
- **Schéma Pydantic strict** : champs requis, enums fermés, bornes numériques, regex sur strings courtes. Un payload invalide = rejet immédiat, pas de "best effort".

### 10.3 System prompt avec arbre de décision explicite

Pas seulement "préfère un tool quand c'est fermé". Le system prompt contient un **decision tree** :

```
Question fermée ? → tool ask_*
Visualisation utile ? → catalogue typé > show_mermaid > texte
Donnée chiffrée clé ? → show_kpi_card obligatoire
Mutation métier ? → tool d'action correspondant + confirmation si destructif
Chiffre/critère/formule ? → JAMAIS sans Source (Module 0.1)
```

Avec **anti-exemples** explicites ("ne fais pas X parce que Y") et exemples de chaînage de tools dans un même tour.

### 10.4 Filtrage contextuel des tools par page

Le LLM connaît la page courante (Module 1.1). Le sélecteur (10.1) injecte uniquement les tools pertinents :
- Page **Profil → Entreprise** : pas de `show_match_card` ni `update_candidature_status`.
- Page **Candidatures** : pas de `show_carbon_pie_chart`.
- Page **Chat flottant global** : sous-ensemble par défaut + tools transverses.

Cela divise par 3 à 5 le nombre de tools concurrents et augmente fortement la précision de sélection.

### 10.5 Validation + boucle de correction

- **Validation Pydantic systématique** côté backend FastAPI avant tout rendu frontend ou toute mutation.
- Si payload invalide → l'erreur structurée est renvoyée au LLM avec **1 ou 2 retry max** ("le champ X doit être un enum parmi [A,B,C], tu as envoyé Y").
- Au-delà de 2 retry → fallback texte ("je n'arrive pas à formaliser cette action, peux-tu reformuler ?") + log d'incident.
- Chaque échec de validation est **loggé** (tool, payload reçu, erreur) pour ajuster les descriptions et le system prompt.

### 10.6 Évaluation continue (eval-driven development)

Constituer un **golden set de 50–100 cas** : `(message utilisateur, contexte de page) → (tool attendu, payload attendu)`.

- Exécuter ce set automatiquement à chaque changement de prompt, de modèle (minimax-m2.7 → autre), ou d'ajout de tool.
- Métriques suivies : taux de bon tool, taux de payload valide, taux d'hallucination de schéma, distribution des fallbacks.
- Sans eval, on corrige à l'aveugle dès qu'on change de modèle.
- Stocké dans `tests/llm_eval/` versionné en git.

### 10.7 Garde-fous UX (post-processeur)

- Si le LLM répond **en texte libre** une question fermée alors qu'un `ask_qcu` aurait convenu (détection par pattern : "préférez-vous A, B ou C ?", énumérations, "oui ou non ?") → un **post-processeur** propose des chips de suggestion ou demande une reformulation.
- Si le LLM produit un chiffre **sans** invoquer de tool sourcé → bandeau d'avertissement "non sourcé" + log.
- Tracer chaque tool call (entrée/sortie/durée) pour analyse a posteriori.

### 10.8 Ordre de priorité d'implémentation (MVP hackathon)

1. **Descriptions de tools béton + schémas Pydantic stricts** — gain massif, 1 jour de travail.
2. **Filtrage des tools par contexte de page** (LangGraph, sélecteur simple) — 1 à 2 jours.
3. **Mini eval set de 30 cas** sur les tools critiques (ask_*, show_kpi_card, mutations Profil) — 0,5 jour.
4. **Boucle de correction Pydantic (1 retry)** — 0,5 jour.
5. **Post-processeur et eval set étendu** → post-MVP.

### 10.9 Hors-scope MVP

- Routage multi-modèle (Haiku pour classifier, MiniMax pour réponse, Sonnet pour analyse complexe) — voir backlog post-MVP "Coûts LLM".
- Cache sémantique des réponses tools.
- Apprentissage en ligne sur les corrections utilisateurs.

---

## Module 11 : Skills (Playbooks Métier)

> **Problème** : un seul system prompt monolithique qui couvre tous les domaines (diagnostic ESG, scoring GCF, génération dossier BOAD, calcul carbone, attestation…) dilue les instructions critiques (sourçage, garde-fous) et fait dériver le LLM hors de son domaine. La rigueur de la **génération de dossiers** (3.3) en particulier exige du vocabulaire, un ton, des sections obligatoires et des sources spécifiques par couple Fonds × Intermédiaire — impossible à tenir dans un prompt global.
>
> **Réponse** : des **Skills** = bundles métier réutilisables qui combinent un prompt expert focalisé, un sous-ensemble de tools autorisés, une procédure pas-à-pas, des sources pré-résolues et des exemples gold. Chargées dynamiquement par le sélecteur LangGraph (Module 10.1) selon le contexte.

### 11.1 Définition

Une **Skill** = unité de compétence métier activable. Différente d'un tool (action atomique) et d'un référentiel (jeu d'indicateurs/seuils) — c'est l'**orchestration** au-dessus.

Composition :
- **Prompt expert** : instructions focalisées (vocabulaire, ton, contraintes, anti-patterns)
- **Procédure** : étapes ordonnées, critères d'entrée/sortie
- **Tool whitelist** : sous-ensemble de tools autorisés (noms définis dans le code)
- **Sources liées** : références `Source` (Module 0.1) pré-résolues, injectées au prompt
- **Activation rules** : conditions de chargement (page, intention, entité active, offre/référentiel ciblé)
- **Golden examples** : 5–15 cas de référence pour l'eval (Module 10.6)

### 11.2 Catalogue MVP (~10 skills)

| Skill | Domaine | Activation | Cœur du contenu |
|---|---|---|---|
| `skill_esg_diagnostic` | Module 2 | Page diagnostic ESG, intent "évaluer ESG" | Procédure d'extraction documents, grille indicateurs, vocabulaire E/S/G |
| `skill_score_gcf` | Référentiel GCF | Offre ciblée = GCF | 8 critères GCF, formules sourcées, jargon GCF |
| `skill_score_boad` | Référentiel BOAD | Offre ciblée via BOAD | Politique sectorielle BOAD, sauvegardes ESS |
| `skill_score_ifc` | Référentiel IFC PS | Offre ciblée IFC/BAD | 8 Performance Standards |
| `skill_carbon_calc` | Module 4 | Intent "empreinte carbone" | Facteurs ADEME/IPCC pré-résolus, mix UEMOA, questions adaptées |
| `skill_dossier_gcf_via_boad` | Génération dossier (3.3) | Candidature à offre GCF×BOAD | Template, sections obligatoires, ton, langue, checklist docs union |
| `skill_dossier_sunref_ecobank` | Génération dossier | Candidature SUNREF via Ecobank | Format SUNREF, ton banque commerciale, garanties |
| `skill_dossier_fem_via_pnud` | Génération dossier | Candidature FEM via PNUD | Format PNUD, project document FEM |
| `skill_intermediaire_boad` | Intermédiaire | Navigation/dialogue autour BOAD | Frais, délais, contacts, jargon, politique secteur |
| `skill_attestation` | Module 5.3 | Génération/révocation attestation | Procédure signature + QR + révocation, mentions légales |
| `skill_credit_score` | Module 5.2 | Calcul scoring crédit vert | Méthodologie sourcée, facteurs, garde-fous Mobile Money |

Liste évolutive — ajout via back-office, pas de déploiement code requis.

### 11.3 Stockage et édition (hybride)

> **Principe directeur** : le **moteur** est en code (logique critique testée) ; le **contenu** vit en BDD éditable depuis le back-office (Module 9), avec la même rigueur que les Sources et les Référentiels.

**Frontière nette :**

| Couche | Où ça vit | Qui édite | Pourquoi |
|---|---|---|---|
| Moteur de skills (loader, sélecteur, fusion prompt, validateur) | Code Git Python/FastAPI | Devs | Logique critique, testée, versionnée |
| Catalogue des **noms de tools** (`ask_qcu`, `update_candidature_status`…) | Code Git | Devs | Un nom inconnu = bug |
| Schémas Pydantic des tools | Code Git | Devs | Contrat de sécurité — JAMAIS éditable depuis l'UI |
| **Contenu de skill** (prompt, procédure, sources liées, exemples) | **BDD** | Admins via back-office | Contenu métier, change souvent |
| **Tool whitelist par skill** | BDD (multi-select sur la liste code) | Admins | Choisi parmi les noms valides |

**Schéma BDD `Skill` :**

```
id, name (unique), version, domain
prompt_expert : text                 ← édité back-office (limite N tokens)
procedure : text                     ← édité back-office
tool_whitelist : [tool_name]         ← multi-select depuis enum code
sources : [source_id]                ← FK vers Sources vérifiées (Module 0.1)
activation_rules : jsonb             ← schéma JSON strict (page, intent, entity)
golden_examples : jsonb              ← édités UI, exportables vers tests/llm_eval/
status : draft | published
created_by, verified_by, valid_from, valid_to
```

### 11.4 Garde-fous (cohérents avec le reste de la plateforme)

1. **Workflow `draft → published`** (cohérent Module 9.1) : une skill n'est servie au LLM que si `published` ET toutes ses sources `verified`.
2. **Versioning** (Module 0.5) : éditer une skill crée une nouvelle version. Les conversations en cours conservent la version active au tour où elles ont été démarrées (snapshot).
3. **Audit log** (Module 0.4) : chaque édition de skill journalisée (`source_of_change = admin`).
4. **Validation au save** :
   - Tools référencés existent dans la liste code (sinon save rejeté)
   - Sources référencées existent et sont `verified`
   - `prompt_expert` ≤ N tokens (budget contrôlé pour cohabiter avec system prompt + contexte)
   - `activation_rules` parse selon un schéma JSON strict
5. **Eval gating obligatoire avant publication** : le back-office propose de **lancer le golden set de la skill** sur la version `draft`. La publication est **bloquée** si régression > seuil défini (lien Module 10.6).
6. **Anti-injection** : le `prompt_expert` est sandboxé. Détection de patterns ("ignore previous instructions", "tu es désormais…", etc.) par règles simples + revue admin obligatoire avant `verified`.
7. **Pas de mutations LLM sur le catalogue Skills** : comme le reste du catalogue (Module 1.1.3), les skills ne peuvent être modifiées que par un Admin via le back-office, jamais par le LLM côté PME.

### 11.5 Chargement dans LangGraph (lien avec Module 10.1)

Le sélecteur du Module 10.1 est étendu :

```
[Classifier d'intention] →
  [Skill loader: 1–2 skills max selon contexte] →
    [Tool selector: 5–8 tools (intersection skill.tool_whitelist + page)] →
      [Fusion prompt: system_prompt_global + skill.prompt_expert + sources injectées] →
        [LLM] → [Validateur Pydantic] → [Réponse]
```

Règles :
- **1 à 2 skills max par tour** (jamais plus — sinon dilution).
- Si plusieurs skills sont candidates, le classifier choisit la plus spécifique (skill dossier > skill scoring > skill diagnostic).
- Une skill activée **réduit** la liste de tools (intersection avec `tool_whitelist`) — pas l'inverse.
- Les sources liées à la skill sont **pré-injectées** dans le contexte (citations prêtes), ce qui réduit les hallucinations et accélère le sourçage (Module 0.1).

### 11.6 Lien fort avec la Génération de Dossiers (Module 3.3)

C'est le **cas d'usage le plus critique** des skills :
- Chaque template de dossier (`Template de dossier`, Module 9.1) est associé à **une skill `skill_dossier_<offre>`** dédiée.
- Cette skill encode : sections obligatoires, ton imposé par l'intermédiaire, langue (FR/EN selon `accepted_languages`), longueur cible, vocabulaire métier, anti-patterns rédactionnels (ex : "ne jamais promettre un impact non quantifié").
- Permet d'avoir des dossiers **réellement adaptés** à chaque couple Fonds × Intermédiaire — pas un texte générique repackagé.
- Une nouvelle offre ajoutée au catalogue (9.1) déclenche la création d'une skill dossier associée — workflow standard pour l'équipe ESG Mefali.

### 11.7 Ordre de priorité d'implémentation (MVP hackathon)

1. **Schéma BDD `Skill`** + CRUD back-office minimal — 1 jour.
2. **Skill loader + fusion prompt + injection sources** — 1 jour.
3. **3 skills critiques codées en seed BDD** : `skill_esg_diagnostic`, `skill_score_gcf`, `skill_dossier_gcf_via_boad` — 1,5 jour.
4. **Eval gating** sur ces 3 skills — 0,5 jour.
5. **5–6 skills additionnelles** progressivement par les admins via back-office.
6. **Workflow `draft → published` + versioning + anti-injection check** — 0,5 jour.

### 11.8 Hors-scope MVP

- Marketplace de skills externes (contributions communautaires de consultants) — backlog post-MVP.
- Skills avec sous-skills (composition récursive).
- A/B testing automatique de versions de skills.
- Génération assistée de skill par le LLM (drafting d'une nouvelle skill à partir d'exemples).

---

## Fonctionnalités Différenciantes pour le Hackathon

### Innovation 1 : Approche Conversationnelle Native
- Pas de formulaires complexes : tout se fait par le chat, y compris **toutes les actions métier** (création/modification/suppression) via les tools de mutation (Module 1.1.3)
- L'IA guide l'utilisateur pas à pas via des tools de réponse en bottom sheet (1.1.1) et des visualisations inline (1.1.2)
- Accessible aux personnes peu familières avec le numérique

### Innovation 2 : Contextualisation Africaine Profonde
- Critères ESG adaptés aux réalités locales
- Prise en compte du secteur informel
- Langue française (langues locales et anglais plus tard)
- Références aux réglementations UEMOA/CEDEAO
- Facteurs d'émission par pays UEMOA (Module 4.2)

### Innovation 3 : Scoring de Crédit Vert Inclusif
- Résout le problème de l'exclusion bancaire
- Plus l'entreprise est verte, meilleur est son accès au crédit
- Crée un cercle vertueux : inclusion + transition écologique
- Méthodologie publique et sourcée (Module 5.2)

### Innovation 4 : Génération Automatique de Dossiers (pilotée par Skills)
- Gain de temps considérable pour les PME
- Qualité professionnelle des documents — chaque dossier généré via une **Skill dédiée au couple Fonds × Intermédiaire** (Module 11.6) avec ton, vocabulaire, sections et longueur cible imposés par cet intermédiaire
- Augmente les chances de succès des candidatures
- Génération multi-offres en parallèle pour un même projet
- Multilingue (FR/EN selon l'offre)
- **Évolutif sans déploiement** : ajout d'une nouvelle Skill dossier depuis le back-office quand une nouvelle offre est ajoutée au catalogue

### Innovation 5 : Approche Holistique
- Une seule plateforme pour tout : diagnostic, financement, suivi
- Cohérence entre les modules (mêmes entités partout)
- Parcours utilisateur fluide

### Innovation 6 : Cartographie réelle des intermédiaires accrédités
- La plupart des plateformes "matching financement vert" listent des **fonds source** que personne ne peut atteindre directement
- ESG Mefali modélise la **réalité du terrain** : c'est l'intermédiaire qui décaisse, donc c'est l'**Offre** (Fonds × Intermédiaire) qui est l'unité utile
- Permet à une PME de **comparer plusieurs voies d'accès au même fonds** (BOAD vs UNDP pour le GCF) — info que personne d'autre ne fournit

### Innovation 7 : Scoring ESG multi-référentiels
- La plateforme calcule en parallèle plusieurs scores (ESG Mefali + GCF + IFC + BOAD + SUNREF + …) sur le même profil
- Une PME découvre qu'elle est éligible chez un intermédiaire et bloquée chez un autre — info actionnable
- Référentiels = configuration sourcée, pas code → ajout de nouveaux référentiels sans refonte

### Innovation 8 : Sourçage de bout en bout (anti-hallucination)
- **Aucun chiffre, aucun critère, aucune formule sans `Source` vérifiée et cliquable** (Module 0.1)
- Le LLM est techniquement empêché de halluciner (validation backend stricte)
- Annexe "Sources" auto-générée dans tous les rapports (qualité scientifique/auditable)
- Avantage compétitif décisif vs les outils ESG "boîte noire" qui ne justifient pas leurs scores

### Innovation 9 : Attestation vérifiable hors-plateforme
- La PME garde le contrôle total : elle décide quand et à qui transmettre son attestation (Module 5.3)
- Le fund officer scanne un QR code pour vérifier l'authenticité — pas besoin de compte
- Conformité RGPD/UEMOA simplifiée : pas de partage automatique de données

### Innovation 10 : LLM moteur d'action complet
- Le LLM ne se contente pas d'expliquer : il **fait** (création/modification/suppression de toute donnée métier en langage naturel — Module 1.1.3)
- Garde-fous systématiques (confirmation pour actions destructives, audit log, isolation par compte)

---

## ODD Ciblés

1. **ODD 8** - Travail décent et croissance économique
2. **ODD 9** - Industrie, innovation et infrastructure
3. **ODD 10** - Inégalités réduites (inclusion financière)
4. **ODD 12** - Consommation et production responsables
5. **ODD 13** - Mesures relatives à la lutte contre les changements climatiques
6. **ODD 17** - Partenariats pour la réalisation des objectifs

---

## Roadmap de Développement

### Phase 1 — MVP Hackathon
**Tout ce qui est documenté ci-dessus, hormis les sections explicitement marquées "Hors-scope MVP" / "post-MVP".**

### Backlog post-MVP (à activer ultérieurement)

| Domaine | Élément différé |
|---|---|
| Sources (0.1) | `archived_url` (Wayback), `hash_contenu`, cron de revalidation, scraper auto sites officiels |
| Auth (0.2) | OTP SMS, magic link, 2FA, RBAC granulaire (Owner/Member/Viewer) |
| Catalogue (3.1, 9.1) | Workflow `pending_review` intermédiaire, contributions communautaires consultants, changelog public |
| Conformité (0.3) | DPO formalisé, purge automatique granulaire fine |
| Mémoire LLM (1.4) | Digest périodique automatique, snapshot mensuel du profil |
| Connectivité | Service Worker / PWA installable / mode offline complet / file d'attente IndexedDB |
| Coûts LLM | Routage multi-modèle (Haiku/MiniMax/Sonnet selon tâche), cache sémantique, budget mensuel par PME |
| Workflow PME (7.3) | Approbation interne, RBAC granulaire intra-PME |
| Statut candidature (8.4) | Email parsing OAuth Gmail/Outlook |
| ROI vert (3.4) | Framework IRIS+ ou Verra complet |
| Exports (7.2) | Compatibilité formats comptables locaux (SYSCOHADA) |
| Modèle économique | Freemium, commission sur financement, partenariats sponsoring |
| Skills (Module 11) | Marketplace skills externes, sous-skills composables, A/B testing de versions, drafting LLM-assisté de nouvelles skills |

---

## Métriques d'Impact à Présenter

- Nombre de PME accompagnées (simulation)
- Nombre d'**intermédiaires** modélisés
- Nombre d'**offres** (couples Fonds × Intermédiaire) modélisées
- Nombre de **sources vérifiées** dans le catalogue
- Montant de financements verts accessibles via les offres modélisées
- Réduction potentielle des émissions CO2
- Temps économisé vs consultant traditionnel
- Coût par PME accompagnée vs tarif consultant

---

## Points Clés pour le Jury

1. **Problème réel et urgent** : Les PME africaines sont exclues de la finance verte
2. **Solution concrète et actionnable** : Pas juste de l'information, mais des dossiers prêts à soumettre **à l'intermédiaire qui peut réellement décaisser**
3. **Réalisme du terrain** : la plateforme modélise les **intermédiaires accrédités** (et pas seulement les fonds source) — différenciation majeure vs solutions existantes
4. **Crédibilité par le sourçage** : chaque chiffre, chaque critère, chaque formule est cliquable vers sa source officielle. Le LLM est techniquement empêché de halluciner
5. **Scoring multi-référentiels** : reflète la réalité que chaque fonds et chaque intermédiaire a son propre cadre d'éligibilité
6. **Technologie appropriée** : Le LLM rend accessible ce qui était réservé aux consultants ; le chat interactif (bottom sheet + visualisations + LLM moteur d'action) abaisse la barrière à l'entrée
7. **Confidentialité préservée** : plateforme fermée aux intermédiaires, attestation vérifiable contrôlée par la PME, conformité RGPD/UEMOA dès le MVP
8. **Impact mesurable** : Métriques claires sur l'inclusion et le climat
9. **Scalabilité** : Applicable à toute la zone francophone africaine
10. **Équipe engagée** : Vision claire et roadmap réaliste
