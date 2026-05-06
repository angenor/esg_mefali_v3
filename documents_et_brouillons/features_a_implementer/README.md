# Features à implémenter — Plans SpecKit

Ces fichiers sont des **prompts de feature description** au format SpecKit (`/speckit.specify`). Chaque fichier décrit une feature en langage naturel — il sera converti en `spec.md`, `plan.md`, `tasks.md` par le workflow SpecKit.

## Méthode de travail

Pour chaque feature à implémenter :

```bash
# 1. Lire le fichier prompt et l'utiliser comme description
cat documents_et_brouillons/features_a_implementer/F01-fondations-sourcage-catalogue.md

# 2. Lancer SpecKit avec ce prompt comme entrée
# Dans Claude Code : /speckit.specify [coller le contenu du fichier]

# 3. Continuer le workflow SpecKit
/speckit.clarify     # poser les questions ambiguës
/speckit.plan        # générer plan technique
/speckit.tasks       # générer la liste de tâches
/speckit.implement   # exécuter
```

## Ordre de traitement recommandé

Les plans sont numérotés par **priorité décroissante**. Les fondations (P0) doivent être implémentées avant les features qui en dépendent (P1, P2). Les dépendances explicites sont indiquées en tête de chaque fichier.

### Phase 0 — Fondations transversales (P0 — bloquantes)

Ces 5 features doivent être implémentées AVANT toute autre car elles introduisent des entités/contraintes qui infusent toute l'application (sourçage, multi-tenant, audit, versioning, devises) :

1. **F01** — Sourçage et catalogue Source (Module 0.1) — différenciateur n°1 de la plateforme
2. **F02** — Multi-tenant + rôle Admin + Row-Level Security (Module 0.2)
3. **F03** — Audit log append-only (Module 0.4)
4. **F04** — Versioning référentiels + Money type + multi-devises (Module 0.5 + 0.6)
5. **F05** — RGPD : page "Mes données" + consentements + export/suppression (Module 0.3 + 7.2)

### Phase 1 — Entités conceptuelles manquantes (P0 — bloquantes)

Le modèle conceptuel "Entreprise 1—N Projets 1—N Candidatures vers Offres = (Fonds × Intermédiaire)" exige 2 entités absentes :

6. **F06** — Entité Projet vert (Module 1.3) — pivot des candidatures
7. **F07** — Entité Offre = couple Fonds × Intermédiaire (Module 3.1.3) — unité commercialement accessible

### Phase 2 — Différenciateurs produit (P0 — bloquants pour la promesse)

8. **F08** — Attestation vérifiable Ed25519 + QR + page publique `/verify/{id}` + révocation (Module 5.3)
9. **F09** — Back-Office Admin complet (Module 9) — sans lui, pas de catalogue

### Phase 3 — Couche conversationnelle complète (P1)

10. **F10** — 8 widgets bottom sheet manquants (Module 1.1.1)
11. **F11** — Tools de visualisation typés : KPICard, MatchCard, Map (Leaflet), ComparisonTable (Module 1.1.2)
12. **F12** — Mémoire contextuelle conforme : 15 messages bruts + pgvector messages + recall_history (Module 1.4)

### Phase 4 — Cœur métier multi-référentiels (P1)

13. **F13** — Scoring ESG multi-référentiels GCF/IFC/BOAD/SUNREF (Module 2.3)
14. **F14** — Matching Projet ↔ Offre avec score décomposé fonds + intermédiaire + comparateur multi-intermédiaires (Module 3.2)
15. **F15** — Génération de dossiers par Offre (FR/EN, union docs fonds+interm) + correctifs bugs (Module 3.3)
16. **F16** — Simulateur sourcé : coût total réel, ROI vert sourcé, comparateur multi-offres (Module 3.4)

### Phase 5 — Carbone et crédit complets (P1)

17. **F17** — Mix UEMOA 8 pays + facteurs ADEME/IPCC sourcés + catégorie Achats (Module 4)
18. **F18** — Mobile Money + photos IA + données publiques + consentements granulaires (Module 5.1)

### Phase 6 — Plan d'action et écosystème (P1)

19. **F19** — Cron dispatcher rappels + auto-création alertes deadline et silence-radio (Module 6.2)
20. **F20** — Bibliothèque ressources + fiches par intermédiaire (Module 6.3)
21. **F21** — Dashboard avec granularité par Offre + carte intermédiaires + rapport carbone PDF (Module 7.1 + 7.2)

### Phase 7 — Tool-use et Skills (P1)

22. **F22** — Decision tree dans system prompt + with_retry effectif + golden set 50 cas (Module 10.3, 10.5, 10.6)
23. **F23** — Skills (playbooks métier) : modèle BDD + loader + 3 skills critiques (Module 11)

### Phase 8 — Extension Chrome (P2)

24. **F24** — Extension Chrome MV3 complète (Module 8) — 7 sous-modules

## Index des dépendances inter-features

```
F01 (Source) ───┬──► F07 (Offre, requiert Source)
                ├──► F08 (Attestation, requiert Source pour référentiels)
                ├──► F13 (Multi-référentiels, requiert Indicator + Référentiel sourcés)
                ├──► F16 (Simulateur, requiert Source pour facteurs)
                ├──► F17 (Carbone, requiert Source pour ADEME/IPCC)
                └──► F23 (Skills, requiert Source pour références)

F02 (Multi-tenant) ──► F09 (Admin, requiert rôle Admin)

F03 (Audit log) ──► F05 (RGPD, audit log visible PME)

F06 (Projet) ───┬──► F14 (Matching Projet↔Offre)
                ├──► F15 (Génération dossier référence Project)
                └──► F19 (Rappels par projet)

F07 (Offre) ────┬──► F14 (Matching)
                ├──► F15 (Templates par Offre)
                ├──► F16 (Simulateur multi-offres)
                ├──► F19 (Deadlines par Offre)
                └──► F24 (Extension détecte par Offre)

F09 (Admin) ────────► toutes les features qui nécessitent un peuplement catalogue
```

## Conventions des fichiers prompts

Chaque fichier suit la structure :

```markdown
# Fxx — Titre court

**Module(s) source(s)** : x.y du fonctionnalites_brainstorming.md
**Priorité** : P0/P1/P2
**Dépendances** : Fxx, Fyy
**Estimation** : N sprints

## Contexte & motivation
[pourquoi ce changement, état actuel + ce qui manque]

## User stories
[en tant que ... je veux ... afin de ...]

## Périmètre fonctionnel
[ce qui est dans le scope]

## Hors-scope
[ce qui n'est pas dans le scope, post-MVP]

## Exigences techniques
### Backend
### Frontend
### Base de données

## Critères d'acceptation
[liste de checks vérifiables]

## Risques & garde-fous
[ce qui peut mal tourner, comment l'éviter]
```
