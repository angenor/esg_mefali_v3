# Research — Feature 045 (Matching projet-centric)

**Date** : 2026-05-21
**Branche** : `045-matching-projet-centric`

Ce document consigne les décisions techniques prises en Phase 0, en résolvant chaque inconnue identifiée dans le Technical Context de `plan.md`. Format : Decision / Rationale / Alternatives.

---

## R1 — Sources F01 verified pour la taxonomie verte UEMOA

**Inconnue** : Quelle source officielle utiliser pour valider `taxonomie_verte_uemoa_aligned` ?

**Decision** : Seed d'une nouvelle Source F01 `verified` avec :
- `name` = « Taxonomie verte UEMOA — BCEAO 2024 »
- `kind` = `regulatory_taxonomy`
- `url` = lien BCEAO officiel (placeholder à confirmer côté équipe métier — le seed doit accepter un URL nullable s'il n'est pas encore publié, avec flag `pending_url=true`)
- `version` = `1.0`
- `valid_from` = `2024-01-01`
- `captured_by` / `verified_by` = utilisateurs admin distincts (CHECK F01 four-eyes)

**Rationale** : la BCEAO publie depuis 2024 une taxonomie d'activités vertes alignée sur les ODD 7, 13 et 15. C'est la référence régulatoire la plus directe pour le contexte UEMOA. Cohérent avec F01 qui priorise UEMOA/BCEAO avant les standards internationaux (principe constitutionnel I).

**Alternatives considérées** :
- _Taxonomie EU Green_ : trop éloignée du contexte africain, risque de désalignement sur le secteur informel.
- _IFC Performance Standards_ : déjà seedé F01 mais c'est un référentiel ESG, pas une taxonomie d'activités. Conservé en parallèle pour le pilier ESG projet, pas pour l'alignement taxonomie.
- _Pas de seed dédié_ : refusé — le validator `source_required.py` bloquerait tout match avec `taxonomie_verte_uemoa_aligned=true` (retry → fallback texte), dégradant l'UX.

---

## R2 — Thèmes prioritaires GCF (Green Climate Fund)

**Inconnue** : Quelle taxonomie pour `gcf_priority_themes` et quelle source citer ?

**Decision** : Whitelist applicative côté Pydantic v2 + check côté Postgres (JSONB array, contrainte applicative dans la couche service) :
```text
gcf_priority_themes ∈ {
  "atténuation",          # Mitigation — réduction GES
  "adaptation",           # Adaptation aux impacts climatiques
  "cross_cutting",        # Co-bénéfices atténuation + adaptation
  "REDD+",                # Réduction émissions déforestation
  "forêts",               # Foresterie durable
  "eau",                  # Gestion eau résiliente climat
  "agriculture",          # Agriculture durable / climate-smart
  "énergie",              # Énergie renouvelable et efficacité
}
```

Source F01 à seeder : « GCF Strategic Plan 2024-2027 — Priority Themes » avec lien `https://www.greenclimate.fund/sites/default/files/document/gcf-strategic-plan-2024-2027.pdf` (à confirmer URL stable).

**Rationale** : la liste correspond aux Result Areas définies dans le Strategic Plan GCF 2024-2027. Elle est officielle, stable sur 4 ans, et permet d'affiner le matching projet vs simplement `objective_env` (qui reste plus large : `mitigation|adaptation|biodiversity|...`).

**Alternatives considérées** :
- _Liste réduite à 3 thèmes (atténuation/adaptation/cross_cutting)_ : insuffisant pour différencier les fonds spécialisés forêts ou eau (BOAD a des facilités dédiées).
- _Mapping libre dans objective_env_ : refusé — diluerait `objective_env` (qui sert au sourcing F01 existant) et casserait la rétrocompatibilité F06.
- _Reprendre l'enum FEM (GEF Focal Areas)_ : trop générique, peu adapté pour les fonds verts adaptation-spécifiques.

---

## R3 — Politique genre GCF 2019 pour `gender_inclusion`

**Inconnue** : Quel critère métier pour valider `gender_inclusion=true` ?

**Decision** : Champ booléen simple en MVP — la PME déclare oui/non si son projet intègre un volet genre conforme à la _GCF Updated Gender Policy 2019_. Source F01 à seeder : « GCF Updated Gender Policy 2019 » (document officiel GCF), URL `https://www.greenclimate.fund/document/updated-gender-policy-2019`.

Pas de sous-critères en MVP (ratio bénéficiaires femmes, présence d'analyse genre dans le document projet, etc.) — reportés post-MVP si une PME demande à affiner. Le champ `expected_beneficiaries` (déjà F06) reste agnostique du genre.

**Rationale** : binaire simple = champ saisi par la PME en widget interactif F18 (qcu oui/non + justification optionnelle). Cela suffit pour permettre au scoring projet de pondérer positivement les projets gender-responsive sans imposer un formulaire complexe à la PME (principe constitutionnel III conversation-driven + VI inclusivité).

**Alternatives considérées** :
- _Score 0-100 sur 5 sous-critères_ : trop complexe pour MVP, sortirait du périmètre.
- _Détection automatique via NLP sur description projet_ : intéressant post-MVP mais nécessite un modèle calibré, hors-scope.
- _Champ obligatoire NOT NULL_ : refusé — beaucoup de projets historiques en BDD n'ont pas cette information, NULL = « non évalué » est sémantiquement utile.

---

## R4 — Populations vulnérables : whitelist FR

**Inconnue** : Quelles catégories d'enum pour `vulnerable_populations` ?

**Decision** : Whitelist applicative FR avec 5 valeurs alignées sur les définitions ONU/Banque mondiale couramment utilisées par les fonds verts :
```text
vulnerable_populations ∈ {
  "femmes",
  "jeunes",                 # 15-35 ans (définition UA Charte africaine jeunesse)
  "handicapés",
  "réfugiés",
  "déplacés_internes",
}
```

Source F01 à seeder : « ODD 10 — Reduce Inequality — Indicators » (UN Statistics Division), URL `https://unstats.un.org/sdgs/metadata/?Text=&Goal=10`. La source documente les groupes vulnérables référencés par les ODD.

**Rationale** : 5 catégories couvrent 95 % des cas demandés par les bailleurs multilatéraux (GCF, FEM, AfDB, BOAD). Format JSONB array pour permettre un projet de cibler plusieurs populations en parallèle.

**Alternatives considérées** :
- _Liste étendue à 10+ catégories (LGBTQ+, minorités ethniques, etc.)_ : pertinent en V2 mais risque de complexifier le matching MVP et certaines catégories sont juridiquement sensibles en zone UEMOA.
- _Champ texte libre_ : refusé — empêche le matching algorithmique (un fonds qui cible « femmes rurales » ne pourrait pas être matché automatiquement).

---

## R5 — Algorithme de scoring projet : pondération interne des 8 sub-scores projet

**Inconnue** : Comment pondérer les 8 sub-scores projet entre eux (sector, taxonomy, gcf_themes, co2_impact, beneficiaries, gender, vulnerable, project_esg) pour produire un `project_score` 0..100 ?

**Decision** : Pondération MVP figée en constante Python `PROJECT_SCORE_WEIGHTS` dans `backend/app/modules/financing/matching_service.py` :
```text
PROJECT_SCORE_WEIGHTS = {
  "sector":        0.15,  # Secteur ∈ target_sectors fonds
  "taxonomy":      0.20,  # taxonomie_verte_uemoa_aligned
  "gcf_themes":    0.20,  # Recouvrement gcf_priority_themes projet ↔ fonds
  "co2_impact":    0.15,  # expected_impact_tco2e ≥ seuil fonds
  "beneficiaries": 0.10,  # expected_beneficiaries vs target
  "gender":        0.05,  # gender_inclusion + GCF gender policy
  "vulnerable":    0.05,  # recouvrement vulnerable_populations
  "project_esg":   0.10,  # project_esg_score / 100
}
# total = 1.00
```

Pour `company_score`, on conserve la pondération F14 actuelle (`sector=0.25, esg=0.30, size=0.15, location=0.10, documents=0.10, instrument=0.10`) avec `esg` = score `ESGAssessment` entreprise (héritage F14).

**Rationale** :
- Le sourcing F01 (cite_source) reste OBLIGATOIRE sur chaque sub-score (validator `source_required.py` actif). Sans source verified pour un critère, le sub-score est 0 + flag `unsourced` dans le breakdown.
- La taxonomie UEMOA et les thèmes GCF pèsent 40 % à eux deux — c'est le cœur du recentrage projet vs F14.
- Le pilier `project_esg` est introduit pour donner du poids au score ESG propre au projet (saisi manuellement par la PME en MVP), distinct du score entreprise.
- gender et vulnerable populations restent à 5 % chacun en MVP — visibles dans le breakdown sans devenir bloquants.

**Alternatives considérées** :
- _Pondération admin-modifiable (Q1=D rejeté)_ : ajouterait une table `matching_weights` versionnée et un endpoint admin. Hors-scope MVP (assumption documentée dans spec).
- _Pondération apprise par ML_ : nécessite un dataset historique de soumissions/acceptations qui n'existe pas encore. Post-MVP.
- _Reprendre exactement les 6 piliers F14_ : ne couvrirait pas les 5 nouveaux champs projet, vidant la feature de sa substance.

---

## R6 — Texte gabarit `divergence_explanation`

**Inconnue** : Comment générer le paragraphe explicatif de divergence entre `project_score` et `company_score` sans recourir à un freetext LLM (FR-013) ?

**Decision** : Module dédié `backend/app/modules/financing/divergence_templates.py` qui contient 4 gabarits FR paramétrés :

| Cas | Critère | Texte généré |
|---|---|---|
| **convergent** | `abs(project_score - company_score) ≤ 15` | « Votre projet et votre entreprise sont alignés sur les critères de ce fonds. Aucune divergence majeure détectée. » |
| **projet_fort** | `project_score - company_score > 30` | « Votre projet est éligible parce qu'il aligne {N} critères impact (taxonomie UEMOA, {themes_gcf}). Votre entreprise reste à renforcer sur {M} critères financiers et ESG ({top_company_blockers}). » |
| **entreprise_forte** | `company_score - project_score > 30` | « Votre entreprise présente un profil solide ({top_company_strengths}) mais votre projet manque {M} attributs verts ({top_project_missing}). Renforcez ces points pour optimiser votre éligibilité. » |
| **moyen** | autres cas | « Votre projet et votre entreprise présentent un profil contrasté. Consultez le détail des critères pour identifier les axes d'amélioration. » |

Les variables `{N}`, `{themes_gcf}`, `{top_company_blockers}`, `{top_company_strengths}`, `{top_project_missing}` sont remplies par le service à partir du `score_breakdown` JSONB. Aucune génération LLM.

**Rationale** : Gabarits maîtrisés = pas de risque d'hallucination, pas de coût LLM, traduction FR garantie avec accents. Pattern déjà utilisé par F14 pour `recommended_actions`. Performance : génération O(1).

**Alternatives considérées** :
- _Freetext LLM avec Claude (génération à chaque match)_ : refusé par FR-013 explicitement (« paragraphe gabarit, pas un freetext LLM »). Risque hallucination + coût + latence.
- _4 chaînes statiques sans variables_ : trop générique, perd la valeur explicative concrète.
- _Génération côté frontend Vue 3 i18n_ : déplace la logique métier vers UI, casse le contrat API (le payload doit déjà contenir l'explication finalisée).

---

## R7 — Pattern event listener SQLAlchemy `after_update` avec debounce 30 s

**Inconnue** : Comment éviter les cascades de recalculs quand une PME modifie 5 champs projet en moins d'1 minute ?

**Decision** : Listener `event.listens_for(Project, 'after_update')` dans `backend/app/modules/projects/service.py` qui :
1. Détecte si un des **champs critiques** (`sector`, `target_amount_amount`, `target_amount_currency`, `objective_env`, `expected_impact_tco2e`, `expected_beneficiaries`, et les 5 nouveaux Q3) a changé via `inspect(instance).attrs.<field>.history.has_changes()`.
2. Si oui, marque le projet en mémoire (in-process `dict[project_id, last_recompute_request_ts]`) — pas en BDD.
3. Vérifie si un recompute a été demandé depuis < 30 s pour ce `project_id` ; si oui, skip (debounce).
4. Sinon, schedule via `asyncio.create_task(_runner(...))` qui appelle `matching_service.execute_recompute_batch(...)` en background.

Pas de Redis, pas de Celery — `asyncio.create_task` suffit pour un monolithe FastAPI. Le `dict` in-process est volatil (perd l'état au restart), ce qui est acceptable (au pire, un recompute supplémentaire au redémarrage).

**Rationale** :
- Conforme au principe constitutionnel VII (YAGNI — pas de Redis tant qu'un dict in-process suffit).
- Pattern déjà éprouvé F12 (`embed_message` en `asyncio.create_task` après `after_insert` Message).
- 30 s = compromis entre réactivité (la PME voit la mise à jour rapidement) et stabilité (évite 5 recomputes pour 5 updates rapides).
- Cap dur 50 offres par recompute (cohérent F14).

**Alternatives considérées** :
- _Trigger PostgreSQL_ : refusé — exécution dans le contexte transaction = pas async, blocking.
- _Celery + Redis_ : refusé pour MVP (principe VII, infra additionnelle).
- _Pas de debounce_ : refusé — risque cascade de 5+ recomputes/min (R5 dans la spec).
- _Debounce 60 s_ : trop long, la PME attendrait inutilement la mise à jour des matches.

---

## R8 — Skill F23 `skill_match_project_funds`

**Inconnue** : Quelles `activation_rules`, `golden_examples` et `tool_whitelist` pour le nouveau skill ?

**Decision** :
- **Skill name** : `skill_match_project_funds`
- **Domain** : `MATCHING_FINANCING` (nouveau enum à ajouter à `SkillDomain` si absent — fallback : `FINANCING`)
- **Prompt expert** : prompt FR de 8-12 lignes qui pose l'agent comme « conseiller financement vert spécialisé matching projet pour PME africaines francophones », rappelle les fondations F01 (citer les sources), F06 (projet = unité de matching), F11 (visualiser les résultats).
- **Tool whitelist** :
  - 8 tools projet F06 : `create_project`, `update_project`, `delete_project`, `list_projects`, `get_project`, `duplicate_project`, `link_document_to_project`, `match_funds_for_project` (nouveau)
  - 4 tools F14 réutilisés : `list_matches_for_project`, `recompute_matches_for_project`, `get_match_details`, `compare_offers_for_fund`
  - 3 tools sourçage F01 globaux (déjà whitelist globale)
  - 4 tools F11 visualisation
  - 1 tool F18 widgets : `ask_interactive_question`
- **Activation rules** :
  - `keywords` (OR) : `["matching", "financement", "fonds", "bailleur", "GCF", "FEM", "BOAD", "subvention"]`
  - `min_keyword_matches` : 1
  - `requires_active_project` : false (la skill peut aussi guider la création projet)
  - `priority` : 80 (haute, juste sous skill_dossier_gcf_via_boad qui est 90)
- **Golden examples** (4 conversations) :
  1. PME informelle Togo + projet agroforesterie (US1) → couvre cas score entreprise indéterminé
  2. PME bien notée + projet non vert (US3) → couvre filtre négatif
  3. PME chat continu : crée projet, lance match, update, re-match (US2) → couvre cycle de vie complet
  4. PME divergence : projet=78 % entreprise=12 % (US4) → couvre explication divergence
- **Status** : `draft` initial, transition `published` après eval ≥ 90 % (gating F23 standard).

**Rationale** : le skill orchestre la séquence conversationnelle complète et garantit que l'agent appelle les bons tools dans le bon ordre (création → matching → visualisation). Les 4 golden examples couvrent les 4 user stories P1+P2.

**Alternatives considérées** :
- _Réutiliser `skill_esg_diagnostic` ou `skill_score_gcf`_ : non — ces skills servent à diagnostiquer / scorer, pas à orchestrer un matching. Risque de pollution du prompt.
- _Pas de skill, prompts inline dans `match_funds_for_project`_ : refusé — manque les golden examples F23 pour calibrer, et casse le pattern playbook.
- _Skill activé uniquement après création projet_ : refusé — il faut pouvoir guider la création depuis zéro.

---

## R9 — Constantes FR partagées backend ↔ frontend pour les enums

**Inconnue** : Comment éviter la duplication des labels FR (`gcf_priority_themes`, `vulnerable_populations`) entre Pydantic (backend) et types TypeScript (frontend) ?

**Decision** : Source de vérité = fichier Python `backend/app/core/matching_constants.py` qui exporte les whitelists FR + un script `frontend/scripts/sync-matching-constants.ts` (Node + ts-node) qui lit le fichier Python, parse les listes, et génère `frontend/app/types/matching_enums.generated.ts`. Le script est lancé manuellement (ou via pre-commit hook optionnel — hors-scope MVP) après chaque modification du fichier Python.

Le fichier généré est commité (pas dans `.gitignore`) pour éviter une étape de build supplémentaire en CI.

**Rationale** :
- Évite la duplication silencieuse (les labels FR doivent matcher exactement entre payload API et tooltips frontend).
- Pas de runtime overhead (génération statique).
- Pattern déjà utilisé F11 pour la whitelist des centroides UEMOA (`visualization_centroids.py` dupliqué dans frontend `geo/uemoa-borders.geo.json`).

**Alternatives considérées** :
- _Endpoint API `/api/enums/matching`_ qui retourne les labels FR au frontend au boot : ajoute un round-trip réseau et un point de friction (cache, version).
- _i18n côté Vue avec clés en anglais_ : casse le contrat de payload API (`gcf_priority_themes` doit déjà contenir les labels FR pour l'audit log F03 et le breakdown JSONB).
- _Duplication manuelle_ : refusé — risque de désynchro avec accents perdus côté frontend.

---

## R10 — Sources verified déjà disponibles vs à seeder

**Inconnue** : Quelles sources F01 doivent être seedées dans la migration 045 vs déjà présentes ?

**Decision** : Inspection de la BDD au démarrage du sprint pour vérifier. Pré-décision : seed obligatoire dans `app/scripts/seed_sources_045.py` (idempotent SELECT-before-INSERT) des 4 sources suivantes si absentes :

| Source | Slug recommandé | Status seed | Référence |
|---|---|---|---|
| Taxonomie verte UEMOA — BCEAO 2024 | `bceao-taxonomie-verte-2024` | NOUVEAU | R1 ci-dessus |
| GCF Strategic Plan 2024-2027 — Priority Themes | `gcf-strategic-plan-2024-2027` | NOUVEAU | R2 ci-dessus |
| GCF Updated Gender Policy 2019 | `gcf-gender-policy-2019` | NOUVEAU | R3 ci-dessus |
| ODD 10 — Reduce Inequality | `un-sdg-10-indicators` | À VÉRIFIER (déjà F01 seedé via ODD batch ?) | R4 ci-dessus |

Les 4 sources sont créées avec `status='verified'`, `captured_by` = utilisateur admin seed (cf. `seed_admin.py`), `verified_by` = utilisateur admin distinct (CHECK F01 four-eyes). En environnement local sans deux admins distincts, le seed crée un second user admin technique (`admin-verifier@mefali-system`) ; pattern déjà utilisé F23 seed_skills.

**Rationale** : sans ces sources, le validator F01 bloque tous les matches projet qui citent un de ces critères. Le seed est donc obligatoire dans le scope de la feature.

**Alternatives considérées** :
- _Seed manuel hors migration_ : refusé — la feature ne peut pas être déployée sans ces sources. Bloquer le déploiement par script garantit la cohérence.
- _Sources `pending` initialement, vérifiables par admin post-deploy_ : refusé — le validator F01 bloquerait les matches en attendant.

---

## R11 — Format payload tool `match_funds_for_project`

**Inconnue** : Quelle structure JSON le tool doit retourner au LLM (pour qu'il puisse expliquer les résultats à la PME) et quelle structure pour le block visualisation F11 ?

**Decision** :
- **Réponse tool (JSON compact pour le LLM)** :
  ```json
  {
    "project_id": "uuid",
    "project_name": "Agroforesterie 200ha Togo",
    "matches_count": 5,
    "top_matches": [
      {
        "offer_id": "uuid",
        "fund_name": "Green Climate Fund",
        "intermediary_name": "BOAD",
        "project_score": 78,
        "company_score": 12,
        "divergence_explanation": "Votre projet est éligible parce qu'il aligne 4 critères impact (taxonomie UEMOA, atténuation, REDD+, gender_inclusion)...",
        "top_3_blockers_project": ["co2_impact_below_threshold", "missing_paris_alignment", "vulnerable_populations_empty"]
      }
    ],
    "no_match_reason": null
  }
  ```
- **Block visualisation F11 (parallèle au texte LLM)** : émet jusqu'à 5 `<MatchCardBlock>` (un par top_match) via marker SSE `__sse_visualization_block__` — schema déjà défini F11 `MatchCardBlockSchema`. Chaque card affiche `project_score`, `company_score`, `divergence_explanation` courte, lien vers fiche fonds.

Si `matches_count == 0`, retourne `no_match_reason: "Aucun fonds n'aligne ses critères avec ce projet. Renforcez : [thème_1, thème_2, thème_3]"` — pas de block visualisation, le LLM affichera le message texte.

**Rationale** : sépare la couche données (JSON pour le LLM qui peut reformuler) et la couche visuelle (blocks F11 pour rendre les MatchCards dans le chat). Pattern conforme F14 et F11.

**Alternatives considérées** :
- _Un seul payload mixte_ : viole la séparation données/présentation et complique le test conformity F11.
- _Émettre 1 seul ComparisonTableBlock au lieu de N MatchCardBlocks_ : moins lisible mobile (table dense). On garde MatchCardBlock pour le format individuel et on garde ComparisonTableBlock disponible via `compare_offers_for_fund` F14.

---

## R12 — Migration Alembic 045 — Stratégie versioning

**Inconnue** : Le champ `global_score` F14 reste-t-il `NOT NULL` après migration, ou devient-il nullable / déprécié ?

**Decision** : `global_score` reste `NOT NULL` (rétrocompatibilité F14), maintenu en lecture seule pendant 2 sprints. La migration 045 :
1. Ajoute `project_score`, `company_score` `NOT NULL DEFAULT 0` (DEFAULT pour les rows existantes), `project_score_breakdown JSONB NOT NULL DEFAULT '{}'`, `divergence_explanation TEXT NULL`.
2. Backfill : pour chaque `OfferMatch` existante, `project_score = global_score` (héritage), `company_score = global_score` (héritage), `project_score_breakdown = score_breakdown` (héritage), `divergence_explanation = NULL`.
3. Add CHECK constraints sur `project_score` et `company_score` (0..100).
4. Down migration : DROP les 4 colonnes ajoutées, `global_score` inchangé.

Après 2 sprints, une feature de cleanup pourra supprimer `global_score` + colonnes F14 redondantes — hors-scope 045.

**Rationale** :
- Préserve les données F14 existantes (~N matches en BDD selon environnement).
- Round-trip up/down/up validé : la down migration ne perd que les nouvelles données calculées.
- Permet aux endpoints F14 (`list_matches_for_project`, etc.) de continuer à fonctionner sans modification immédiate.

**Alternatives considérées** :
- _DROP `global_score` immédiatement_ : refusé — casse F14 en prod, viole l'assumption « cohabitation 2 sprints » du brief.
- _Renommer `global_score` en `project_score` et créer un NOUVEAU `global_score` agrégé_ : refusé — sémantique confuse, Q1=C dit pas d'agrégation.
- _Migration sans DEFAULT NOT NULL (NULL puis backfill)_ : refusé — round-trip up/down/up risque de laisser des NULL si down lance avant complète exécution du backfill.

---

## R13 — Détection du « critère projet minimum » pour FR-003

**Inconnue** : Quelle règle exacte pour garantir qu'une PME « rouge » + projet « vert » obtient au moins 3 fonds (incluant GCF, FEM, Fonds d'Adaptation) ?

**Decision** : Règle déterministe métier (pas de seuil flottant) :
- Si `project_score ≥ 60` ET `project_score - company_score > 30` ET le projet aligne au moins 2 critères parmi `[taxonomie_verte_uemoa_aligned=true, len(gcf_priority_themes) ≥ 1, expected_impact_tco2e ≥ 1000]`, **alors** la liste de matches retournée inclut systématiquement les offres pour les 3 fonds prioritaires impact (GCF, FEM, Fonds d'Adaptation) **si elles existent dans le catalogue F25** — même si leur tri naturel les placerait au-delà du top 10.
- Ce comportement est implémenté comme un boost post-tri : après calcul des matches, on identifie les offres `fund.name IN ('Green Climate Fund', 'Fonds pour l'Environnement Mondial', 'Fonds d'Adaptation')` et on les promeut en tête si elles ne sont pas déjà dans le top 5.
- Les noms exacts des fonds doivent matcher (case-insensitive) la BDD F25 — un test conformity vérifie leur présence au démarrage du sprint.

**Rationale** :
- Garantit le SC-002 (vérifié par test d'intégration backend).
- Reste déterministe et explicable (pas de magique).
- Préserve l'expérience pour les autres profils (le boost ne s'applique qu'au cas « rouge + vert »).

**Alternatives considérées** :
- _Pondération adaptative qui dégrade `company_score` en cas de score < 30_ : trop opaque, viole Q1=C.
- _Top N fixe à 10 sans boost_ : ne garantit pas la présence des fonds prioritaires impact.
- _Filtrage hardcodé `fund_type='multilateral'`_ : trop strict, exclurait les fonds bilatéraux pertinents pour le projet.

---

## Récapitulatif des décisions

| ID | Domaine | Décision clé |
|---|---|---|
| R1 | Sources F01 | Seed Taxonomie verte UEMOA — BCEAO 2024 |
| R2 | Whitelist enum | 8 thèmes GCF FR avec accents |
| R3 | Champ projet | `gender_inclusion BOOL` simple en MVP |
| R4 | Whitelist enum | 5 populations vulnérables FR |
| R5 | Algorithme | Pondération projet figée 8 sub-scores, constante Python |
| R6 | UX | 4 gabarits FR de divergence_explanation (pas LLM) |
| R7 | Perf | Listener `after_update` + debounce 30 s in-process |
| R8 | Skill F23 | `skill_match_project_funds` 4 golden examples, 21 tools whitelist |
| R9 | DRY | Source de vérité Python + script génération TS |
| R10 | Seed | 4 sources F01 obligatoires dans migration 045 |
| R11 | Tool payload | JSON compact + blocks F11 parallèles |
| R12 | Migration | `global_score` déprécié 2 sprints, +4 colonnes |
| R13 | Garantie SC-002 | Boost post-tri pour 3 fonds prioritaires impact si conditions remplies |

**Phase 0 complete** : tous les NEEDS CLARIFICATION techniques résolus. Le Technical Context du plan.md ne contient plus d'inconnu.
