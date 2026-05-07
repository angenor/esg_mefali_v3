# Feature Flags — ESG Mefali

Liste des feature flags activables via env vars dans la plateforme.

## `USE_OFFER_VIEW` (F07)

**Description** : contrôle l'affichage de la home `/financing` côté PME.

| Valeur | Comportement |
|--------|-------------|
| `false` (default MVP F07) | Vue Cards Fonds legacy (avec modal d'intermédiaires) |
| `true` | Vue Cards Offres (couples Fonds × Intermédiaire) avec scoring décomposé |

**Env var** : `NUXT_PUBLIC_USE_OFFER_VIEW`

**Lecture** : `frontend/nuxt.config.ts` → `runtimeConfig.public.useOfferView`.

**Plan de bascule** :
- **MVP F07** : flag inactif par défaut. Les pages `/financing/offers/*` sont
  accessibles via lien direct uniquement.
- **Post-F14** (matching offre mature) : bascule vers `true` en production.
- **Post-bascule** : la vue Cards Fonds legacy est dépréciée 2 sprints puis
  retirée.

**Rollback** : pour revenir à la vue legacy en cas de problème, il suffit
de définir `NUXT_PUBLIC_USE_OFFER_VIEW=false` dans l'env de production.

## Autres flags

(Ajouter ici les flags futurs : `ENABLE_CHROME_EXT`, `ENABLE_F19_CRON_DISPATCHER`, etc.)
