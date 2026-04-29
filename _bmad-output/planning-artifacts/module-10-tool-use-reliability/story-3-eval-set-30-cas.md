---
story_id: M10-S3
epic: M10-EPIC-1
title: Mini eval set de 30 cas sur tools critiques
status: ready
priority: P3
effort: "0.5 j"
source_items: [10.6, 10.8.3]
created: 2026-04-29
depends_on: [M10-S1]
---

# Story M10-S3 — Mini eval set de 30 cas sur tools critiques

## Contexte

Sans eval automatise, chaque changement de prompt, de modele ou de tool est un saut dans le vide.
Un mini eval set versionne en git permet de detecter les regressions et de comparer objectivement
les variantes (modeles, prompts, descriptions de tools).

## Objectif

Constituer un golden set de **30 cas** au format `(message_utilisateur, page_context) -> (tool_attendu, payload_attendu)`
et un runner CLI/pytest qui execute le set et produit des metriques.

## Repartition des 30 cas

| Module | Tool cible | Nombre de cas |
|--------|-----------|---------------|
| `ask_qcu` | question fermee 2-7 options exclusives | 5 |
| `ask_qcm` | question fermee multi-choix | 3 |
| `show_kpi_card` | chiffre cle a afficher | 4 |
| `show_radar_chart` / `show_pie_chart` | visualisation typee | 4 |
| `update_company_profile` | mutation profil | 5 |
| `create_fund_application` | mutation candidature | 3 |
| `batch_save_esg_criteria` | mutation ESG | 3 |
| Cas piege (texte libre attendu, pas de tool) | — | 3 |

## Criteres d'acceptation

- [ ] Fichier `backend/tests/llm_eval/golden_set_v1.yaml` versionne, 30 entrees au format :
  ```yaml
  - id: case_001
    message: "Mon entreprise est une SARL avec 12 salaries dans l'agroalimentaire."
    page_context: "profile"
    expected_tool: "update_company_profile"
    expected_payload_partial:
      legal_form: "SARL"
      employee_count: 12
      sector: "agroalimentaire"
    notes: "Mutation profil avec 3 champs canoniques"
  ```
- [ ] Runner `backend/tests/llm_eval/run_eval.py` execute le set et imprime un rapport :
  - taux de bon tool (%),
  - taux de payload valide (Pydantic) (%),
  - taux de match `expected_payload_partial` (subset match) (%),
  - taux de fallback texte (%).
- [ ] Le runner peut etre lance via `pytest backend/tests/llm_eval/ -m eval`.
- [ ] Marker pytest `eval` configure dans `pyproject.toml` (skippe par defaut, lance manuellement).
- [ ] Baseline initiale enregistree (snapshot du run avec le modele courant) dans
  `backend/tests/llm_eval/baselines/2026-04-29_<modele>.json`.
- [ ] README `backend/tests/llm_eval/README.md` documente comment ajouter un cas et lancer le set.

## Implementation guidee

1. **Format YAML** : choisir YAML pour lisibilite humaine (les cas seront ajoutes a la main).
2. **Subset match** : un payload est valide si tous les champs `expected_payload_partial` sont
   presents avec la bonne valeur (le LLM peut ajouter des champs additionnels valides).
3. **Determinisme** : `temperature=0` pour le runner, seed fixe si possible.

## Definition of Done

- 30 cas ecrits et revus.
- Runner fonctionne et produit un rapport lisible.
- Baseline du jour enregistree.
- Documentation ecrite.
