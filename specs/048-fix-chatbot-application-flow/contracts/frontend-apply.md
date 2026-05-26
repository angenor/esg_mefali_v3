# Contract — Bouton « Candidater » fonctionnel (D5)

**Fichiers** : `frontend/app/pages/financing/offers/[offer_id].vue`, `frontend/app/composables/useApplications.ts` (ajout/maj), `frontend/app/components/financing/OfferDetail.vue` (vérif émission `@apply`)

## `handleApply(offerId)` (réécrit)

Comportement attendu :

```
async handleApply(offerId):
  try:
    app = await useApplications().createApplication({
      offerId,
      projectId: activeProjectId.value   // depuis route.query.project_id
    })
    router.push(`/applications/${app.id}`)   // ou /documents
  catch (e):
    error.value = message clair FR (FR-015)
```

- Plus de `router.push('/financing/offers/${id}/apply')` (route inexistante supprimée).
- État de chargement pendant l'appel (désactiver le bouton, éviter double-clic → FR-006).

## Composable `useApplications().createApplication`
- `POST /api/applications/` avec `{ offer_id, project_id }`.
- Retourne le dossier créé (id, status). Gère erreurs réseau/HTTP → throw message FR.

## Comportement contexte incomplet (FR-015)
- Si pas de `project_id` actif : selon politique projet, soit créer sans projet (si autorisé), soit afficher un message invitant à sélectionner un projet — **jamais** de clic sans effet.

## Cas de test
| # | Niveau | Scénario | Attendu |
|---|--------|----------|---------|
| T1 | Vitest | clic avec offer+project | appelle createApplication, navigue vers le dossier |
| T2 | Vitest | API en erreur | `error` affichée, pas de navigation |
| T3 | Vitest | double clic rapide | une seule création (bouton désactivé) |
| T4 | E2E Playwright | parcours offre → Candidater | dossier créé visible (/applications ou /documents), 0 page 404 |
| T5 | E2E | sans project_id | message guidage explicite, pas de clic mort |

## SC liés
- SC-004 : 100 % des clics → dossier OU message explicite (0 clic sans effet).
