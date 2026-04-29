---
story_id: M10-S1
epic: M10-EPIC-1
title: Tool descriptions beton et schemas Pydantic stricts
status: ready
priority: P1
effort: "1 j"
source_items: [10.2, 10.8.1]
created: 2026-04-29
---

# Story M10-S1 — Tool descriptions beton + schemas Pydantic stricts

## Contexte

Audit de fiabilite des 32 tools existants (spec 012). Beaucoup ont des descriptions trop courtes,
des schemas Pydantic permissifs (champs optionnels qui devraient etre requis, strings libres
qui devraient etre des enums). Premiere ligne de defense : rendre chaque tool **auto-discriminant**.

## Objectif

Reecrire les descriptions et durcir les schemas Pydantic des tools critiques pour que le LLM
choisisse le bon tool sans ambiguite, et que tout payload invalide soit rejete deterministiquement.

## Perimetre

**Tools concernes (priorite haute) :**
- Tools `ask_*` (interactive_questions, spec 018) : `ask_qcu`, `ask_qcm`, `ask_qcu_justification`,
  `ask_qcm_justification`.
- Tools de visualisation : `show_kpi_card`, `show_radar_chart`, `show_pie_chart`, `show_timeline`,
  `show_table`, `show_mermaid`, `show_gauge`.
- Tools de mutation Profil/Candidature : `update_company_profile`, `create_fund_application`,
  `batch_save_esg_criteria`.

**Hors perimetre :** tools de lecture pure (search, fetch) — traites en story 2.

## Criteres d'acceptation

- [ ] Chaque tool du perimetre a une description contenant : (a) verbe d'action sans ambiguite,
  (b) bloc « Use when », (c) bloc « Don't use when » avec renvoi vers le tool alternatif,
  (d) au moins 1 exemple positif et 1 anti-exemple.
- [ ] Chaque schema Pydantic du perimetre :
  - Champs obligatoires marques `...` (pas `Optional` quand le champ est requis metier).
  - Tous les choix fermes sont des `Enum` (pas `str`).
  - Bornes numeriques (`Field(ge=, le=)`) sur tous les nombres.
  - Regex sur strings courtes contraintes (codes, slugs).
  - `model_config = ConfigDict(extra="forbid")` sur tous les schemas (rejet de champs inconnus).
- [ ] Un test unitaire par tool valide : (a) un payload valide, (b) au moins 2 payloads invalides
  rejetes avec `ValidationError`.
- [ ] Documentation interne `backend/app/graph/tools/README.md` listant les conventions
  (nommage, structure description, structure schema).
- [ ] Mesure tokens : la longueur cumulee des descriptions de tools augmente de <+25% (acceptable
  vu le gain en precision).

## Implementation guidee

1. **Backend** : pour chaque tool dans `backend/app/graph/tools/*_tools.py`, refactorer
   `description=` et le schema `args_schema=`.
2. **Tests** : ajouter `backend/tests/graph/tools/test_<module>_tools_schemas.py` avec table-driven
   tests (cas valide + cas invalides).
3. **Lint** : ajouter une verification automatique (test meta) que chaque tool exporte
   `extra="forbid"` et a une description >= 200 caracteres.

## Definition of Done

- 32 tools (ou les 13 critiques minimum) refactores et conformes.
- Tests passent (`pytest backend/tests/graph/tools/`).
- README conventions ecrit.
- PR mergee sur `main` avec review.
