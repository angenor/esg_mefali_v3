# Quickstart — Validation manuelle de `/admin/catalog`

**Feature**: 044-admin-catalog-financing
**Audience**: Développeurs et QA après implémentation

## Pré-requis

```bash
# Backend (venv activé)
source backend/venv/bin/activate
uvicorn app.main:app --reload

# Frontend (autre terminal)
cd frontend && npm run dev
```

Compte ADMIN disponible (créé via `python -m app.scripts.seed_admin` si nécessaire).

## Parcours US1 — Vue unifiée (P1)

1. Se connecter à l'app avec le compte ADMIN.
2. Naviguer vers `/admin/catalog`.
3. **Vérifier** : la page affiche 4 onglets (Fonds, Intermédiaires, Offres, Liaisons fonds × intermédiaires), chacun avec un compteur.
4. **Vérifier** : la somme des éléments « publié » par onglet correspond à ce qui est visible dans `/financing` (index + onglets sous-jacents) — ouvrir `/financing` dans un autre onglet pour comparer.
5. Cliquer successivement sur les 4 onglets : chaque liste se charge en < 2 s.
6. Saisir un terme connu (ex : « GCF » dans Fonds) dans la barre de recherche. **Vérifier** : la liste filtre en < 500 ms et le compteur « filtré / total » se met à jour.
7. Cliquer sur un élément. **Vérifier** : la fiche détaillée s'ouvre avec toutes les caractéristiques métier, version, statut, et sources F01 (composant `SourceLink`).
8. Se déconnecter, se reconnecter avec un compte PME, tenter d'ouvrir `/admin/catalog`. **Vérifier** : accès refusé et redirection hors espace admin.

## Parcours US2 — Filtres statut/version (P2)

1. ADMIN sur `/admin/catalog`, onglet Fonds.
2. Activer le filtre « Statut = brouillon ».
3. **Vérifier** : seuls les fonds non publiés s'affichent ; aucun d'eux n'est listé côté `/financing` public.
4. Activer le filtre « Statut = déprécié ». Ouvrir une fiche déprécié.
5. **Vérifier** : un lien « Version successeur » est présent et fonctionne (navigation vers la fiche remplaçante).

## Parcours US3 — Liaison fonds × intermédiaire (clarifié)

1. Onglet « Liaisons fonds × intermédiaires ».
2. Cliquer sur une ligne.
3. **Vérifier** : la fiche dédiée affiche la paire, `accredited_from`, `accredited_to`, `max_amount_per_fund_money`, source d'accréditation (avec `SourceLink`), liens « Voir le fonds » et « Voir l'intermédiaire ».
4. Cliquer sur « Voir le fonds » → navigation vers la fiche détail correspondante.

## Parcours Export (P3)

1. Appliquer un filtre sur un onglet (ex : Intermédiaires statut publié).
2. Cliquer sur « Exporter ».
3. **Vérifier** : un fichier `catalog-intermediaries-YYYYMMDD.csv` se télécharge, contient uniquement les lignes correspondant au filtre, et s'ouvre sans erreur d'encodage dans Excel FR (BOM UTF-8).

## Edge cases à valider

- **Liste vide** : forcer un filtre incohérent (ex : `q=zzzzzzz`) → message « Aucun résultat » + bouton « Réinitialiser les filtres ».
- **Onglet vide** : si la base ne contient aucun élément dans un onglet, message « Aucun élément enregistré dans cette catégorie ».
- **Incohérence détectée** : forcer en BDD un fond `published` avec `source_id NULL` → badge « Incohérence détectée » présent sur la ligne et la fiche.
- **Dark mode** : basculer le toggle thème → tous les fonds, textes, bordures et états hover sont en parité claire/sombre (aucune zone blanche persistante).
- **Liaison expirée** : créer une liaison `accredited_to < today` → s'affiche en onglet « Liaisons » avec badge « Expirée » quand filtre = expired.

## Tests automatisés à exécuter avant merge

```bash
# Backend
cd backend && pytest tests/modules/admin/test_catalog_*.py -v

# Frontend unitaires
cd frontend && npm run test -- admin/catalog

# E2E
cd frontend && npx playwright test admin-catalog
```

## Critères de succès (SC-001..SC-005)

| Critère | Méthode de mesure |
|---|---|
| SC-001 — élément retrouvé < 5 s | Chronométrer le parcours « ouvrir → saisir → cliquer » |
| SC-002 — parité `/financing` ↔ `/admin/catalog` publiés | Compter manuellement ou via script de vérification |
| SC-003 — repérage brouillons/dépréciés < 30 s | Chronométrer l'application du filtre statut |
| SC-004 — chargement et filtrage < 2 s pour 1 000 éléments | DevTools Network panel |
| SC-005 — zéro accès non autorisé | Test E2E Playwright avec compte PME |
