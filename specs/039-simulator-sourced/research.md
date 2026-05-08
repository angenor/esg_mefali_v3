# Phase 0 — Research : F16 Simulateur Financement Sourcé

**Date** : 2026-05-08
**Statut** : Complet — toutes les NEEDS CLARIFICATION résolues.

## R1 — Mécanique de chargement des facteurs de simulation

**Decision** : un unique SELECT par appel sur `simulation_factors` (filtre statut `verified` ∪ `pending` mais pas `outdated` bloquant), joint à `sources` via `source_id`. Le résultat est matérialisé dans une `FactorSnapshot` immuable (frozen dataclass) qui sert toutes les offres comparées dans un même appel multi-simulate.

**Rationale** :
- Cohérence FR-017 : un même snapshot pour toutes les offres comparées.
- Performance SC-005 (< 5 s pour 5 offres) : l'aller-retour BDD coûte ~quelques ms ; un SELECT global est moins cher que 5×N lookups par-facteur.
- Simplicité MVP : pas de cache distribué Redis, pas d'invalidation complexe ; le snapshot vit le temps de la requête.

**Alternatives considérées** :
- Cache TTL en mémoire process : rejeté (incohérence possible avec mutations admin F09 pendant le TTL ; complexité non justifiée).
- Lazy lookup par-facteur dans chaque `compute_*` : rejeté (rompt FR-017, surcoût latence négligeable mais cohérence non garantie si admin publie un nouveau facteur en cours d'appel).

## R2 — Mapping instrument financier → formule ROI

**Decision** : table de dispatch `dict[InstrumentLiteral, RoiCalculator]` où `InstrumentLiteral = Literal['subvention','pret_concessionnel','equity','blending']` (aligné sur `funds.instruments` JSONB de F07). Chaque calculateur est une fonction pure typée Pydantic v2 prenant `(project, offer, factor_snapshot)` et retournant `RoiBreakdown`. Les paramètres numériques (par exemple ratio de gain énergétique par défaut, durée d'amortissement par défaut) viennent **exclusivement** du `FactorSnapshot` (jamais de constantes inline).

**Rationale** :
- Différenciation FR-005 : subvention → ROI = "pas de remboursement" ; prêt concessionnel → ratio gains / coût total ; equity → dilution + IRR projeté ; blending → combinaison pondérée.
- Testabilité : chaque calculateur est isolé, pure, sans I/O — tests unitaires triviaux.
- Évolutivité : ajouter un instrument = ajouter une entrée au dict + une fonction.

**Alternatives considérées** :
- Polymorphisme via classes héritées `BaseRoiStrategy` : rejeté (overengineering pour 4 cas, dataclass + dict suffisent).
- Calcul unifié paramétré : rejeté (les formules sont structurellement différentes, surtout subvention vs prêt).

## R3 — Source des ratios sectoriels carbone (CarbonImpact)

**Decision** : lecture sur `emission_factors` (table créée par F01, peuplée par F17) avec clé `(category='sector_carbon_intensity', country=projet.country, year=année courante)`. Fallback ascendant : (a) pays exact + année exacte, (b) pays exact + année antérieure récente (diff ≤ 3, marqué `is_approximate=False` si diff ≤ 3, sinon True), (c) global + année exacte, (d) global + année antérieure. Si aucun match, `CarbonImpact.degraded_reason = "aucun_facteur_sectoriel_disponible"` et la valeur reste `None` (pas d'invention, FR-006).

L'impact final est calculé comme : `tco2e_per_year = project.expected_impact_tco2e * sector_factor` où `sector_factor` est un coefficient d'ajustement contextuel (1.0 par défaut quand `verified`, 0.8 si secteur informel notable, etc., paramétré par F17). Ne JAMAIS utiliser `target_amount * constant`.

**Rationale** :
- FR-006 explicite : pas de multiplicateur linéaire au montant.
- Réutilise le pattern F17 (lookup factor + fallback + flag `is_approximate`) pour cohérence.
- Mode dégradé clair : si rien à dire, on dit "non estimé" plutôt qu'inventer.

**Alternatives considérées** :
- Calcul via `target_amount × ratio_kgCO2e_par_FCFA` : rejeté (c'est précisément l'antipattern actuel à supprimer).
- Demande au LLM de générer une estimation : rejeté (non sourçable, viole FR-002).

## R4 — Transport SSE du tool `compare_simulations`

**Decision** : réutilise le marker SSE F11 existant `<!--SSE:{"__sse_visualization_block__":true,"block_type":"comparison_table","payload":{...}}-->` détecté par `stream_graph_events` et converti en événement typé `visualization_block`. Aucune extension du protocole SSE requise.

Le `payload` adopte le schéma `ComparisonTableArgs` de F11 (subjects = liste d'offres, rows = lignes Coût total / Timeline / Taux succès / Score F14, values avec `source_id` cliquable côté frontend, `winner_index` calculé serveur-side pour highlight).

**Rationale** :
- Réutilisation directe du composant `ComparisonTableBlock.vue` (F11) — pas de nouveau composant à écrire pour le canal chat.
- Pattern éprouvé sur F11 (testé, en production sur le projet).
- Conserve la séparation entre `tool result` (résumé court pour le LLM) et `visualization payload` (rendu UI).

**Alternatives considérées** :
- Nouveau type d'événement SSE dédié `simulation_block` : rejeté (duplique F11 sans gain).
- Rendu inline Markdown table dans le message LLM : rejeté (perd les sources cliquables et le highlight winner).

## R5 — Garde-fou anti-constantes magiques (test AST)

**Decision** : test pytest `tests/unit/test_no_magic_constants_in_simulation.py` qui parse `backend/app/modules/applications/simulation.py` via `ast.parse`, visite tous les `ast.Constant` de type numérique et échoue si la valeur est ailleurs que dans une whitelist explicite. Whitelist proposée :

- `0`, `1` (neutres mathématiques, indices, valeurs de retour pas-applicable)
- `12` (nombre de mois dans une année — utilisé pour conversion durée_mois → durée_années dans formules ROI)
- Constantes définies dans des `Decimal("...")` lus depuis le snapshot factors sont **autorisées** (le passage à `Decimal` est validé séparément).

Le test inspecte chaque numérique trouvé : si valeur ∉ whitelist → fail avec localisation `(filename, line_no, col_offset, value)`.

Implémentation : `class MagicConstantVisitor(ast.NodeVisitor)` + `_assert_no_magic(file_path, whitelist)`. Le test tourne sur CI à chaque commit.

**Rationale** :
- Garantit SC-002 de manière mécanique (revue manuelle non scalable).
- Détection précoce d'une régression où un développeur réintroduirait `_DEFAULT_FEE_RATE = 0.03`.
- Indépendant du choix d'IDE / lint config.

**Alternatives considérées** :
- Linter ruff custom rule : rejeté (ruff ne supporte pas trivialement de plugins custom Python ; pytest est plus simple et déjà standard projet).
- Inspection manuelle par revue de code : rejeté (non scalable, oubli humain probable au fil des features).

## R6 — Score de compatibilité dans le comparateur (lien F14)

**Decision** : F16 lit le score de compatibilité depuis le service F14 `matching_service.compute_score(project, offer)` quand F14 est mergé ; sinon la colonne « Score compatibilité » est masquée dans le tableau comparatif (et non remplie par une valeur factice). C'est cohérent avec l'Assumption "score consommé depuis F14 lorsqu'il est disponible".

**Rationale** :
- Découplage F14 ↔ F16 : F16 ne dépend pas du merge de F14 pour livrer.
- Évite tout chiffre fabriqué (cohérent avec l'invariant F01).

**Alternatives considérées** :
- Implémenter un score local F16 : rejeté (duplication de logique F14, dette technique immédiate).
- Bloquer F16 sur F14 : rejeté (couplage temporel inutile).

## Synthèse — aucune NEEDS CLARIFICATION résiduelle

Toutes les décisions techniques sont prises. Phase 1 peut démarrer immédiatement.
