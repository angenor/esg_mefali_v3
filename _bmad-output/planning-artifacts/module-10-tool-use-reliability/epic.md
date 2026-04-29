---
epic_id: M10-EPIC-1
title: Refonte fiabilite tool-use LLM
status: draft
priority: P0 (MVP hackathon)
owner: Angenor
created: 2026-04-29
source_spec: Module 10 — Strategie de Fiabilite du Tool-Use LLM
stories:
  - story-1-tool-descriptions-pydantic-strict.md
  - story-2-tool-filtering-by-page-context.md
  - story-3-eval-set-30-cas.md
  - story-4-pydantic-retry-loop.md
  - story-5-post-mvp-backlog.md
---

# Epic M10 — Refonte fiabilite tool-use LLM

## Probleme

Avec un catalogue de 30+ tools (reponse, visualisation, mutation, lecture/calcul/recherche),
un LLM laisse seul degrade rapidement : mauvais tool selectionne, payload invalide, hallucination
de schema. Sans garde-fous, le taux d'echec sur les questions fermees, mutations metier et
visualisations contextuelles devient inacceptable pour un MVP demonstrable.

## Objectif

Garantir que **le bon tool est invoque avec le bon payload, a chaque tour de conversation**, en
combinant :

1. Schemas et descriptions de tools robustes (auto-discriminants).
2. Filtrage contextuel des tools par page courante (ne jamais exposer >10 tools au LLM).
3. Validation Pydantic systematique avec boucle de correction bornee.
4. Eval-driven development sur un golden set versionne.

## Valeur metier

- **Demonstration MVP fiable** : zero hallucination sur les tools critiques (`ask_qcu`,
  `show_kpi_card`, mutations Profil/Candidature) lors du parcours hackathon.
- **Cout LLM maitrise** : moins de retries, moins de tokens consommes par tour.
- **Evolutivite** : chaque ajout de tool ou changement de modele est non-regressif grace a l'eval set.

## Scope MVP (5 stories)

| # | Story | Priorite | Effort | Item Module 10 |
|---|-------|----------|--------|----------------|
| 1 | Tool descriptions beton + schemas Pydantic stricts | P1 | 1 j | 10.2, 10.8.1 |
| 2 | Filtrage des tools par contexte de page (LangGraph selecteur) | P2 | 1-2 j | 10.1, 10.4, 10.8.2 |
| 3 | Mini eval set de 30 cas sur tools critiques | P3 | 0.5 j | 10.6, 10.8.3 |
| 4 | Boucle de correction Pydantic (1 retry) | P4 | 0.5 j | 10.5, 10.8.4 |
| 5 | Backlog post-MVP (post-processeur UX, eval etendu, multi-modele, cache, apprentissage) | post-MVP | n/a | 10.7, 10.8.5, 10.9 |

**Effort total MVP : 3 a 4 jours.**

## Hors scope (story 5 — backlog post-MVP)

- Post-processeur UX (chips de suggestion sur reponses texte libre a question fermee, bandeau
  "non source" sur chiffres sans tool).
- Eval set etendu (>50 cas, couverture multi-modules).
- Routage multi-modele (Haiku classifier, MiniMax reponse, Sonnet analyse complexe).
- Cache semantique des reponses tools.
- Apprentissage en ligne sur corrections utilisateurs.

## Architecture cible (apres epic)

```
[User message + page_context]
        |
        v
[Classifier d'intention LangGraph]   (LLM leger ou regles)
        |
        v
[Selecteur de tools]   --> charge 5-10 tools max selon (intention, page, entites actives)
        |
        v
[LLM avec tools filtres + system prompt avec decision tree]
        |
        v
[Validateur Pydantic]  --> si invalide : retry 1x avec erreur structuree
        |                  --> si echec apres retry : fallback texte + log incident
        v
[Reponse / mutation / visualisation]
        |
        v
[Trace tool_call_logs : entree, sortie, duree, validation_status]
```

## Criteres de succes de l'epic

- [ ] Les 4 stories MVP (1 a 4) sont implementees et mergees.
- [ ] Eval set de 30 cas passe a >=90% (bon tool + payload valide).
- [ ] Aucun tour de conversation n'expose plus de 10 tools au LLM.
- [ ] Toute reponse tool invalide est retracee dans `tool_call_logs` avec `validation_status`.
- [ ] La boucle de correction Pydantic est bornee a 1 retry, fallback texte garanti au-dela.
- [ ] Demo hackathon : le parcours golden (Profil -> ESG -> Carbone -> Financement -> Candidature)
  ne produit aucune hallucination de tool sur 3 executions consecutives.

## Dependances

- LangGraph deja en place (specs 012, 013, 015, 018).
- 32 tools LangChain existants (spec 012) : refactoring de leurs descriptions et schemas, pas
  de creation massive de nouveaux tools.
- `tool_call_logs` table existante (spec 012) : extension avec `validation_status` et
  `retry_count`.
- Module 1.1 (page courante connue par le LLM) : prerequis pour story 2.

## Risques

| Risque | Probabilite | Impact | Mitigation |
|--------|-------------|--------|------------|
| Eval set incomplet -> regressions invisibles | Moyenne | Eleve | Iteration : +10 cas a chaque incident |
| Filtrage trop agressif -> tool legitime indisponible | Moyenne | Moyen | Whitelist transverse + fallback "tools globaux" |
| Retry boucle infinie sur erreur recurrente | Faible | Eleve | Max 1 retry hard-code + circuit breaker |
| Descriptions tool trop longues -> cout tokens | Moyenne | Moyen | Mesure tokens/tour avant/apres, objectif <+15% |

## Metriques de suivi (post-deploiement)

- Taux de bon tool (golden set) : objectif >=90%.
- Taux de payload Pydantic valide au 1er essai : objectif >=85%.
- Taux de fallback texte : objectif <5%.
- Tokens moyens par tour : surveillance, objectif +15% max vs baseline.
