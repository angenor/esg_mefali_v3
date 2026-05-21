# Phase 0 — Research & Décisions Techniques

**Feature**: 044-admin-catalog-financing
**Date**: 2026-05-21

Aucun marqueur `NEEDS CLARIFICATION` ne subsiste dans le Technical Context. Les trois zones ambiguës initialement détectées ont déjà été résolues par `/speckit.clarify` (cf. spec §Clarifications). Les décisions ci-dessous consolident les choix structurants restants.

---

## D1 — Stratégie de pagination conditionnelle

**Decision**: Pagination serveur déclenchée automatiquement quand `total_count` dépasse 2 000 pour l'onglet courant ; en deçà, l'API renvoie la liste intégrale en une seule requête. La taille de page par défaut est 50 (sélecteur 25/50/100) ; les filtres et le tri sont conservés à travers les pages.

**Rationale**:
- Aligné sur la clarification utilisateur (FR-013a).
- Les volumes actuels (<100 par catégorie) garantissent qu'on reste en mode « liste complète » pendant les premières années, ce qui simplifie la recherche client-side et l'export.
- Le seuil 2 000 est suffisamment haut pour ne pas dégrader l'UX (toutes les listes admin existantes — `/admin/funds`, `/admin/sources` — fonctionnent déjà sans pagination visible) et suffisamment bas pour éviter d'envoyer >500 KB JSON.

**Alternatives rejetées**:
- Pagination systématique (Option A initiale) : friction inutile pour les volumes actuels.
- Défilement virtualisé (Option B) : complexité front (intersection observer, hauteur dynamique), incompatible avec l'export ligne-par-ligne et la sélection multiple future.

---

## D2 — Endpoint pour les liaisons `fund_intermediaries`

**Decision**: Nouveau router `app/modules/admin/fund_intermediaries_router.py` monté sous `/api/admin/catalog/fund-intermediaries` exposant `GET /` (liste paginée + filtres) et `GET /{id}` (détail). Le modèle `FundIntermediary` existe déjà (table `fund_intermediaries` F07) ; la PK composite `(fund_id, intermediary_id)` est exposée sous forme d'un identifiant synthétique `{fund_id}:{intermediary_id}` URL-safe pour les routes détail.

**Rationale**:
- Aucun router admin n'expose actuellement la table `fund_intermediaries` ; seules les routes publiques `compute_effective_offer` la consomment indirectement.
- Réutilise les helpers existants (`get_current_admin`, RLS admin policy, `func.lower` pour recherche).
- Format d'ID `:` séparateur évite l'introduction d'une colonne UUID PK supplémentaire sans migration.

**Alternatives rejetées**:
- Ajouter une colonne `id UUID PK` à `fund_intermediaries` : nécessiterait une migration et casserait la clé composite existante référencée par F07.
- Exposer les liaisons sous chaque fiche fond/intermédiaire seulement : ne couvre pas l'onglet dédié demandé.

---

## D3 — Format et endpoint d'export CSV

**Decision**: Endpoint unique `GET /api/admin/catalog/export?tab={funds|intermediaries|offers|fund_intermediaries}&...filtres` qui répond avec `Content-Type: text/csv; charset=utf-8` et `Content-Disposition: attachment; filename="catalog-{tab}-{YYYYMMDD}.csv"`. Streaming via `StreamingResponse` ligne-par-ligne (idem export audit F03). Séparateur `,`, encodage UTF-8 avec BOM pour compatibilité Excel FR.

**Rationale**:
- Réutilise le pattern d'export streaming déjà éprouvé sur `/api/audit/me/export`.
- Un seul endpoint paramétrable plutôt que 4 endpoints distincts → moins de code, moins de tests.
- CSV est le format standard demandé par la spec (Assumptions) et compatible avec les outils des auditeurs.

**Alternatives rejetées**:
- Export Excel (.xlsx via openpyxl) : ajoute une dépendance, alourdit la mémoire en streaming.
- Export côté frontend (génération JS) : ne respecterait pas les filtres serveur sur gros volumes et duplique la logique de sérialisation.

---

## D4 — Compteurs par onglet

**Decision**: Endpoint `GET /api/admin/catalog/summary` retournant un objet `{funds: {total, by_status}, intermediaries: {total, by_status}, offers: {total, by_status}, fund_intermediaries: {total, active, expired}}` calculé via 4 `SELECT COUNT(*)` SQL avec `GROUP BY publication_status`. Appel unique au chargement de la page.

**Rationale**:
- Évite 4 appels HTTP parallèles (chacun avec un `total_count`) pour peupler les compteurs des onglets.
- Permet d'afficher la répartition publié/brouillon/déprécié sans charger les listes.
- Simple à mettre en cache côté navigateur (ETag) pour de futures optimisations.

**Alternatives rejetées**:
- Calculer les compteurs côté frontend après chargement de chaque onglet : impose de visiter chaque onglet pour voir les totaux.
- Inclure les compteurs dans la réponse `list` de chaque onglet : oblige à appeler 4 endpoints au chargement initial.

---

## D5 — Détection d'incohérence (Edge Case « badge »)

**Decision**: Une incohérence est définie comme : (a) un fond ou intermédiaire en statut `published` mais dont la `source_id` est NULL, ou (b) une liaison `fund_intermediaries` dont `accredited_to` est dépassée mais qui n'a pas été marquée comme expirée. La détection est calculée en SQL au moment du fetch via un champ booléen `has_incoherence` ajouté à chaque ligne de liste, et le détail explicite la cause.

**Rationale**:
- Reste léger (deux conditions SQL simples), pas de job de détection asynchrone.
- Couvre les cas réels rencontrés en production (cf. F01 sourçage obligatoire et cron `check_expired_accreditations.py`).

**Alternatives rejetées**:
- Service de détection nightly stocké en BDD : sur-ingénierie pour un volume <2 000 lignes.
- Pas de badge (suppression de l'edge case) : perte de valeur opérationnelle pour l'admin.

---

## D6 — Réutilisation des fiches détail existantes

**Decision**: Les fiches détail fonds, intermédiaires, offres sous `/admin/catalog/{entity}/[id]` réutilisent les composants/pages existantes via wrapping minimal (import direct du composant détail si extractible, sinon `<NuxtLink>` redirigeant vers la page existante avec un bouton « Retour au catalogue »). Seule la fiche **liaison** est nouvelle (US3 clarifié).

**Rationale**:
- Évite de dupliquer ~600 lignes de template/style de `admin/funds/[id].vue`.
- Centralise la maintenance des fiches détail au même endroit.

**Alternatives rejetées**:
- Recréer des fiches détail dédiées sous `/admin/catalog/*` : duplication coûteuse et risque de divergence.

---

## D7 — Authentification & RLS

**Decision**: Réutilisation stricte de `Depends(get_current_admin)` (déjà en place sur tous les routers admin). RLS policy `admin_full_access` couvre les 14 tables F02 ; les tables `fund_intermediaries`, `funds`, `intermediaries`, `offers` ne sont pas multi-tenant (référentiel global) donc pas de filtrage `account_id`.

**Rationale**: Pas de surface de sécurité nouvelle, héritage complet des fondations F02.

**Alternatives rejetées**: aucune justifiée (changer le mécanisme d'auth admin sort du périmètre).

---

## Synthèse

Toutes les zones grises sont résolues, aucune dépendance externe nouvelle, aucune migration BDD. Le coût d'implémentation est concentré côté frontend (page + 6 composants + store/composable + types) ; le backend ajoute environ 200 lignes de Python (1 router + 1 service export + schemas).
