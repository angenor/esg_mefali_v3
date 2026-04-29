---
story_id: M10-S5
epic: M10-EPIC-1
title: Backlog post-MVP — Post-processeur UX, eval etendu, multi-modele, cache, apprentissage
status: backlog
priority: post-MVP
effort: "non chiffre"
source_items: [10.7, 10.8.5, 10.9]
created: 2026-04-29
depends_on: [M10-S1, M10-S2, M10-S3, M10-S4]
---

# Story M10-S5 — Backlog post-MVP

## Contexte

Apres validation MVP (S1-S4), plusieurs ameliorations restent souhaitables mais n'apportent pas
de valeur demonstrable au hackathon. Cette story regroupe le backlog hors-scope MVP pour ne pas
le perdre.

## Items

### 1. Post-processeur UX (item 10.7)

**Probleme** : le LLM peut, malgre tout, repondre en texte libre a une question fermee qui aurait
gagne a invoquer `ask_qcu`. Ou produire un chiffre sans tool sourcé.

**Solution** :
- Detection par pattern sur la reponse texte : « preferez-vous A, B ou C ? », enumerations
  avec puces, « oui ou non ? ».
- Sur detection -> proposer des chips de suggestion cote frontend OU forcer une reformulation
  cote backend (1 retry).
- Si le LLM produit un chiffre sans tool sourcé (regex sur output) -> bandeau d'avertissement
  « non source » + log.

**Effort estime** : 1-1.5 j.

### 2. Eval set etendu a 100+ cas

**Probleme** : 30 cas (M10-S3) couvrent les tools critiques mais pas les cas edge ni tous les
modules.

**Solution** :
- Etendre a 100-150 cas avec couverture multi-modules (carbone, financement, action plan).
- Ajouter cas multi-tour (continuation, changement de module).
- Integrer le runner dans un job CI nightly avec alertes Slack si regression > seuil.

**Effort estime** : 2 j.

### 3. Routage multi-modele (item 10.9)

**Probleme** : un seul modele puissant (couteux) traite tous les tours. Un modele leger suffit
pour le classifier d'intention et le selecteur.

**Solution** :
- Haiku 4.5 pour classifier d'intention.
- MiniMax / Sonnet pour reponse principale.
- Sonnet 4.6 pour analyse complexe (rapport ESG, recommandations financement).

**Effort estime** : 2-3 j (incluant tuning prompts par modele).

### 4. Cache semantique des reponses tools

**Probleme** : certains tools (recherche fonds, lecture profil) sont appeles repetitivement avec
des arguments quasi-identiques.

**Solution** :
- Cache Redis avec cle = `(tool_name, hash(args_normalized))`, TTL configurable par tool.
- Invalidation explicite sur mutation associee.

**Effort estime** : 1-2 j.

### 5. Apprentissage en ligne sur corrections utilisateurs

**Probleme** : quand l'utilisateur corrige une reponse du LLM (ex : « non, je voulais dire SAS,
pas SARL »), cette correction n'est pas exploitee.

**Solution** :
- Capturer les corrections explicites (pattern detection).
- Les stocker dans un dataset `user_corrections.jsonl`.
- Periodiquement, ajouter des cas issus de ce dataset au golden set ou a un fine-tuning.

**Effort estime** : 3-5 j (incluant pipeline de capture + revue humaine avant integration).

## Priorisation post-MVP suggeree

1. **Eval set etendu** (2 j) — fondation pour evaluer toute autre amelioration.
2. **Post-processeur UX** (1-1.5 j) — gain perceptif eleve.
3. **Routage multi-modele** (2-3 j) — gain de cout, ROI clair.
4. **Cache semantique** (1-2 j) — gain de latence.
5. **Apprentissage en ligne** (3-5 j) — long terme, ROI incertain sans volume utilisateur.

## Criteres d'acceptation

Cette story est un backlog : aucun critere d'acceptation. Chaque item ci-dessus deviendra une
story dediee quand il sera priorise.

## Note

Cette story doit etre **scindee en 5 stories independantes** lors de la planification post-MVP.
Elle existe ici uniquement pour tracer l'intention et eviter de perdre les items 10.7 et 10.9
de la spec Module 10.
