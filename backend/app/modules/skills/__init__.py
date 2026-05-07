"""Module métier F23 — Skills (Playbooks Métier).

Composants :

- ``schemas`` : Pydantic v2 (SkillCreate, SkillUpdate, SkillRead, GoldenExample,
  ActivationRules, SkillEvalReport, FailedCase).
- ``validator`` : valide un payload SkillCreate/SkillUpdate (anti-injection,
  tokens cap, sources verified, tool names connus).
- ``service`` : CRUD + query_skills_matching + publish_skill + versioning.
- ``eval_runner`` : exécute les golden_examples avec gating (seuil 90 %).
- ``seed`` : 3 skills MVP critiques (idempotent).
- ``exceptions`` : erreurs métier (EvalGatingFailedError, etc.).
"""
