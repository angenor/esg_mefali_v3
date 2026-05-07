"""F22 — Module admin_metrics : agregation des echecs de validation tools.

Expose un endpoint protege Admin qui retourne le taux d'echec global +
le top N des tools avec validation_error sur la fenetre temporelle.

Reference : ``specs/032-decision-tree-with-retry-eval/spec.md`` US5/FR-011.
"""
