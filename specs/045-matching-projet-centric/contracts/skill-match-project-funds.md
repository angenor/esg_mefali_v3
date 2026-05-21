# Contracts — Skill F23 `skill_match_project_funds` (Feature 045)

**Date** : 2026-05-21
**Branche** : `045-matching-projet-centric`

Ce document décrit le nouveau skill F23 (playbook conversationnel) qui orchestre le matching projet-centric depuis le chat. Le skill respecte le pattern F23 (mig. 033) : versioning, golden examples, tool whitelist, activation rules, gating eval ≥ 90 % avant publication.

---

## 1. Identité du skill

| Champ | Valeur |
|---|---|
| `name` | `skill_match_project_funds` |
| `domain` | `MATCHING_FINANCING` (à ajouter à enum `SkillDomain` si absent, fallback `FINANCING`) |
| `version` | `1.0` |
| `valid_from` | date de déploiement (env var `SKILL_VALID_FROM` ou `now()`) |
| `status` | `draft` initial puis `published` après eval ≥ 90 % (F23 gating) |
| `created_by` | UUID admin seed (cf. `seed_admin.py`) |
| `verified_by` | UUID admin distinct (CHECK F23 four-eyes) |

---

## 2. `prompt_expert`

Prompt FR contextualisé, à insérer dans `seed_skills.py` :

```
Tu es un conseiller financement vert spécialisé dans le matching projet
pour les PME africaines francophones (zone UEMOA/CEDEAO). Tu aides la
PME à :

1. **Décrire son projet vert** en collectant progressivement les
   attributs critiques (secteur, montant cible, impact CO2 estimé,
   alignement taxonomie verte UEMOA, thèmes prioritaires GCF,
   bénéficiaires, populations vulnérables) via widgets interactifs
   F18 (qcu/qcm/justification) — JAMAIS via formulaire externe.

2. **Lancer le matching projet → fonds** via le tool
   `match_funds_for_project` qui calcule un score projet
   INDÉPENDAMMENT du score entreprise. Une PME avec score entreprise
   "rouge" peut tout à fait obtenir des matches verts élevés.

3. **Présenter les résultats** : affiche les top matches avec
   `<MatchCardBlock>` (F11), explique la divergence projet/entreprise
   en français clair, cite les sources F01 (taxonomie UEMOA, GCF
   Strategic Plan) à chaque affirmation factuelle.

4. **Itérer** : si la PME modifie un attribut projet via
   `update_project`, relance automatiquement le matching et présente
   la nouvelle liste — sans demander confirmation, sans handover UI.

Règles ABSOLUES :
- TOUJOURS citer une source F01 verified pour chaque critère métier
  (taxonomie UEMOA, thèmes GCF, seuils GCF, populations vulnérables).
- Utilise tool `cite_source` ou `search_source` si nécessaire.
- JAMAIS de fallback texte sans source — préfère `flag_unsourced` qui
  marque le critère comme à vérifier par l'admin.
- Réponses CONCISES (style instruction F14 — pas de paraphrase).
- Accents é è ê à ç OBLIGATOIRES dans les labels FR.
- Si la PME a un projet en draft, le matching est disponible — pas
  d'attente status='seeking_funding'.
```

Longueur cible : 350-450 tokens (validateur F23 cap à 12 k tokens absolu).

---

## 3. `tool_whitelist` (21 tools)

JSONB array des tool names autorisés au skill :

```jsonc
[
  // Tools projet F06 (7 existants + 1 nouveau 045)
  "list_projects",
  "get_project",
  "create_project",
  "update_project",
  "delete_project",
  "duplicate_project",
  "link_document_to_project",
  "match_funds_for_project",                  // NOUVEAU 045

  // Tools matching F14 (4 existants)
  "list_matches_for_project",
  "recompute_matches_for_project",
  "get_match_details",
  "compare_offers_for_fund",

  // Tools sourçage F01 (3 globaux)
  "cite_source",
  "search_source",
  "flag_unsourced",

  // Tools visualisation F11 (4 existants)
  "show_kpi_card",
  "show_match_card",
  "show_map",
  "show_comparison_table",

  // Tool widget F18 (1)
  "ask_interactive_question",

  // Tool mémoire F12 (1 global)
  "recall_history"
]
```

Total : 21 tools. `MAX_TOOLS_PER_TURN = 29` → reste 8 slots libres pour activation simultanée d'autres skills, cohérent.

---

## 4. `activation_rules`

JSONB schema appliqué par `skill_loader.py` (F23) :

```jsonc
{
  "keywords": [
    "matching", "match", "compatibilité",
    "financement", "fonds", "bailleur",
    "GCF", "FEM", "BOAD", "Fonds d'Adaptation",
    "subvention", "prêt concessionnel",
    "éligibilité", "compatible"
  ],
  "min_keyword_matches": 1,
  "requires_active_project": false,
  "requires_company_profile": false,
  "priority": 80,                              // 0-100, plus haut = priorité supérieure
  "exclusion_keywords": [                       // Désactive ce skill si présents
    "ESG", "diagnostic",                        // → skill_esg_diagnostic
    "dossier", "candidature"                    // → skill_dossier_gcf_via_boad
  ],
  "min_message_length_chars": 5,
  "language": "fr"
}
```

### 4.1 Comportement priorité

- `skill_dossier_gcf_via_boad` (priority 90, F23 existant) > `skill_match_project_funds` (80) : si un message contient « dossier candidature pour GCF », c'est le skill F23 dossier qui s'active, pas matching.
- `skill_match_project_funds` (80) > `skill_esg_diagnostic` (70) : si un message contient « matching ESG », c'est matching qui gagne.
- En cas d'égalité de keywords, le skill avec le plus de keywords matchés gagne. En cas d'égalité totale, tri lexicographique sur `name`.

### 4.2 Test de fallback

Si **aucun skill ne s'active** sur un message qui parle pourtant de matching, le chat node de base récupère la main avec les tools F06+F14 toujours disponibles (cf. `MODULE_TOOL_MAPPING['financing']`). Le skill est un **bonus** d'orchestration, pas un point de passage obligatoire.

---

## 5. `golden_examples` (4 conversations)

JSONB array de 4 exemples calibrés. Chaque exemple est un tableau de messages user/assistant + tool calls attendus + assertions.

### 5.1 Exemple 1 — PME informelle Togo + projet agroforesterie (US1)

```jsonc
{
  "name": "us1_pme_informelle_projet_agroforesterie",
  "context": {
    "user_role": "PME",
    "esg_assessment_finalized": false,            // Score entreprise indéterminé
    "projects_count": 0
  },
  "conversation": [
    {
      "role": "user",
      "content": "Je gère une coopérative agricole au Togo, je veux planter 200 hectares d'agroforesterie pour 850 femmes rurales. Quels fonds peuvent m'aider ?"
    },
    {
      "role": "assistant",
      "expected_tool_calls": [
        "ask_interactive_question",               // Pour collecter impact CO2 estimé
        // ... puis après collecte ...
        "create_project",
        "match_funds_for_project"
      ],
      "expected_response_contains": [
        "GCF",                                    // Green Climate Fund
        "FEM",                                    // Fonds pour l'Environnement Mondial
        "Fonds d'Adaptation"
      ],
      "expected_visualization_blocks": [
        { "block_type": "match_card_project", "count": ">= 3" }
      ]
    }
  ],
  "assertions": [
    "matches_count >= 3",
    "min(project_score for top_matches) >= 60",
    "no_match_reason is None",
    "boost_applied.rule_name == 'rouge_entreprise_vert_projet'"
  ]
}
```

### 5.2 Exemple 2 — PME bien notée + projet non vert (US3)

```jsonc
{
  "name": "us3_pme_verte_projet_non_pertinent",
  "context": {
    "user_role": "PME",
    "esg_assessment_finalized": true,
    "esg_score": 72,                              // Entreprise verte
    "projects_count": 1,
    "project_attrs": {
      "objective_env": [],
      "taxonomie_verte_uemoa_aligned": false,
      "gcf_priority_themes": [],
      "expected_impact_tco2e": null
    }
  },
  "conversation": [
    {
      "role": "user",
      "content": "Je veux savoir quels fonds verts peuvent financer mon activité de négoce."
    },
    {
      "role": "assistant",
      "expected_tool_calls": ["match_funds_for_project"],
      "expected_response_contains": [
        "Aucun fonds n'aligne",
        "thèmes",
        "taxonomie"                               // Suggère taxonomie verte UEMOA
      ]
    }
  ],
  "assertions": [
    "matches_count == 0",
    "no_match_reason is not None",
    "no_match_reason contains 'taxonomie' OR 'thèmes'"
  ]
}
```

### 5.3 Exemple 3 — Chat continu : crée projet → match → update → re-match (US2)

```jsonc
{
  "name": "us2_chat_lifecycle_complet",
  "context": {
    "user_role": "PME",
    "projects_count": 0
  },
  "conversation": [
    {
      "role": "user",
      "content": "Je veux installer 50 panneaux solaires dans mon village."
    },
    {
      "role": "assistant",
      "expected_tool_calls": ["ask_interactive_question", "create_project"]
    },
    {
      "role": "user",
      "content": "Lance le matching."
    },
    {
      "role": "assistant",
      "expected_tool_calls": ["match_funds_for_project"]
    },
    {
      "role": "user",
      "content": "Augmente mon impact CO2 à 5000 tCO2e/an."
    },
    {
      "role": "assistant",
      "expected_tool_calls": [
        "update_project",                         // Met à jour expected_impact_tco2e
        "match_funds_for_project"                 // Relance le matching automatiquement
      ]
    }
  ],
  "assertions": [
    "len(visualization_blocks) >= 2",             // 2 émissions de MatchCardBlock
    "second_match_count > first_match_count OR second_top_score > first_top_score"
  ]
}
```

### 5.4 Exemple 4 — Explication divergence projet/entreprise (US4)

```jsonc
{
  "name": "us4_divergence_explanation",
  "context": {
    "user_role": "PME",
    "esg_assessment_finalized": true,
    "esg_score": 12,                              // Entreprise rouge
    "projects_count": 1,
    "project_attrs": {
      "objective_env": ["mitigation"],
      "taxonomie_verte_uemoa_aligned": true,
      "gcf_priority_themes": ["atténuation", "REDD+"],
      "expected_impact_tco2e": 3000
    }
  },
  "conversation": [
    {
      "role": "user",
      "content": "Pourquoi mon match avec le GCF est-il à 78% alors que mon score entreprise est rouge ?"
    },
    {
      "role": "assistant",
      "expected_tool_calls": ["get_match_details"],
      "expected_response_contains": [
        "projet",
        "entreprise",
        "aligne",                                  // Le projet aligne des critères
        "renforcer"                                // L'entreprise est à renforcer
      ]
    }
  ],
  "assertions": [
    "response contains 'project_score' or 'Match projet'",
    "response contains 'company_score' or 'Match entreprise'",
    "divergence_explanation matches pattern 'projet_fort'"
  ]
}
```

---

## 6. `sources` (références F01)

JSONB array des sources F01 mobilisées par le skill (citées dans le prompt expert et les golden examples) :

```jsonc
[
  {
    "source_id": "uuid-bceao-taxonomie-verte-2024",
    "slug": "bceao-taxonomie-verte-2024",
    "name": "Taxonomie verte UEMOA — BCEAO 2024"
  },
  {
    "source_id": "uuid-gcf-strategic-plan-2024-2027",
    "slug": "gcf-strategic-plan-2024-2027",
    "name": "GCF Strategic Plan 2024-2027"
  },
  {
    "source_id": "uuid-gcf-gender-policy-2019",
    "slug": "gcf-gender-policy-2019",
    "name": "GCF Updated Gender Policy 2019"
  }
]
```

Les UUIDs réels sont résolus au seed (SELECT depuis `sources`).

---

## 7. Gating publication

Le skill est inséré en `status='draft'` par le seed. Le gating F23 (eval ≥ 90 %) est exécuté manuellement par un admin via :

```bash
# CLI
python -m app.scripts.run_skill_eval skill_match_project_funds
```

Si score moyen sur les 4 golden examples ≥ 90 %, l'endpoint `POST /api/admin/skills/{id}/publish` peut être appelé pour passer en `status='published'`. Sinon, l'admin ajuste le prompt expert et relance l'eval.

Pour le MVP, le seed peut directement insérer en `status='published'` (pattern F23 actuel pour les 3 skills MVP, cf. `seed_skills.py` commentaire « les golden_examples sont calibrés mais leur exécution réelle dépend de l'environnement LLM »). À calibrer en sprint review.

---

## 8. Conformity tests

Tests `backend/tests/conformity/test_skill_match_project_funds.py` :

1. **`test_skill_exists_in_seed`** : appel `seed_skills.seed_skills(db, admin_id)` puis SELECT → 1 ligne avec `name='skill_match_project_funds'`.
2. **`test_skill_tool_whitelist_valid`** : chaque tool dans `tool_whitelist` existe dans `tool_selector_config.ALL_TOOLS`.
3. **`test_skill_activation_rules_keywords_valid`** : tous les keywords sont en FR avec accents (regex `[a-zàâäéèêëîïôöùûüç]`).
4. **`test_skill_golden_examples_count`** : exactement 4 golden examples avec name conforme aux 4 user stories.
5. **`test_skill_sources_present_in_db`** : les 3 sources citées (bceao, gcf-strat, gcf-gender) existent en BDD `sources` avec `status='verified'`.
6. **`test_no_skill_mutation_tool`** : aucun tool dans la whitelist ne matche regex `^(create|update|delete|publish|unpublish)_skill` (conformity F23 existante).
