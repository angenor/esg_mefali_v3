# Bug 06 — Le FAB « Ouvrir l'assistant IA » est absent sur certaines pages (ex: `/profile/projects`)

## Symptôme

Le bouton flottant (FAB) *« Ouvrir l'assistant IA »* / *« Fermer l'assistant IA »* en bas à droite est **absent de plusieurs pages secondaires**, alors qu'il est présent sur `/dashboard`, `/` et d'autres pages principales.

Reproduction (session du 2026-05-08) :

| Page | FAB visible ? |
|---|---|
| `/dashboard` (Tableau de bord) | ✅ oui |
| `/profile/projects` (Mes Projets) | ❌ non |

À vérifier sur l'ensemble des pages métier listées dans `_PATH_TO_SLUG_PATTERNS` (cf. `backend/app/graph/tool_selector_config.py:330-350`) :
- `/profile`, `/profile/projects`
- `/esg`, `/esg/results`
- `/carbon`, `/carbon/results`
- `/financing`, `/financing/simulator`
- `/applications`, `/credit-score`
- `/action-plan`, `/documents`, `/reports`

Conséquence : l'utilisateur ne peut pas invoquer l'assistant IA depuis ces pages — il doit revenir au dashboard puis revenir manuellement, perdant le contexte de page (`current_page`) qui sert à filtrer les tools (cf. F11 / scope `profile_projects` qui contient `create_project`). C'est doublement pénalisant : UX dégradée + tool routing privé du contexte page.

## Cause racine (à investiguer)

Le FAB est probablement injecté par un layout Nuxt (ex: `frontend/app/layouts/default.vue`) ou un composant racine (`app.vue`). Les pages qui n'utilisent pas ce layout (ex: layout `profile.vue` dédié pour `/profile/*`) n'héritent pas du FAB.

Hypothèses :

1. **Layout différent sur `/profile/*`** : si `frontend/app/pages/profile.vue` ou `frontend/app/layouts/profile.vue` ne contient pas le composant `<ChatAssistantHost />` (ou nom équivalent), le FAB n'apparaît pas.
2. **Condition de visibilité côté composant** : le composant FAB peut avoir une condition `v-if` qui exclut certaines routes.
3. **Z-index ou overflow CSS** : moins probable mais possible — le FAB est rendu mais masqué visuellement par un container qui clippe.

## Fichiers concernés

À **explorer** :

- `frontend/app/app.vue` — racine de l'application Nuxt
- `frontend/app/layouts/*.vue` — tous les layouts (default, profile, admin, ...)
- `frontend/app/components/` — chercher `ChatHost`, `ChatLauncher`, `AssistantFab`, ou similaire
- `frontend/app/pages/profile/projects.vue` (ou `index.vue` selon la structure F06) — vérifier le `definePageMeta({ layout: '...' })`
- `frontend/app/composables/useChat.ts` — voir si la fonction `openAssistant()` est bien exposée globalement

## Tâche

1. **Localiser le composant FAB** :
   - `grep -rn "Ouvrir l.assistant\|Fermer l.assistant\|chat-fab\|ChatHost\|AssistantFab" frontend/app/`
   - Identifier où il est monté dans la hiérarchie (app.vue ? default.vue ? composable global ?).

2. **Auditer les layouts** :
   - Pour chaque layout sous `frontend/app/layouts/`, vérifier la présence du composant FAB.
   - Tableau récapitulatif : layout | FAB présent | pages utilisant ce layout.

3. **Choisir l'option de fix** :

   ### Option A — Monter le FAB dans `app.vue` (racine globale)
   - Une seule occurrence, présent partout par défaut.
   - **Pour** : zéro duplication, garantit la cohérence sur toutes les pages présentes ET futures.
   - **Contre** : le composant doit gérer correctement les pages où il ne doit PAS apparaître (ex: `/login`, `/register`) via une condition `v-if` sur la route.

   ### Option B — Ajouter le FAB dans chaque layout qui le manque
   - Plus simple à isoler par layout (admin peut avoir un FAB différent par exemple).
   - **Contre** : duplication, risque de régression à chaque nouveau layout.

   → **Recommandé : Option A**, avec une whitelist explicite de routes où le FAB doit être masqué (route `/login`, `/register`, et éventuellement les pages d'erreur `/error/*`).

4. **Vérifier le contexte `current_page`** :
   - Lorsque l'utilisateur ouvre le chat depuis `/profile/projects`, le `current_page` envoyé au backend doit bien être `/profile/projects` (pas `/dashboard`).
   - Inspecter `frontend/app/composables/useChat.ts` ou équivalent : il doit lire `useRoute().path` au moment de l'envoi, pas une variable figée.

5. **Tests E2E** :
   - Ajouter un test Playwright : pour chaque page principale (`/dashboard`, `/profile/projects`, `/esg`, `/carbon`, `/financing`, `/action-plan`), vérifier que le bouton `[aria-label="Ouvrir l'assistant IA"]` est visible.
   - Cas négatif : sur `/login`, vérifier qu'il **n'est pas** visible.

## Critères d'acceptation

- [ ] Le FAB est visible sur **toutes les pages métier authentifiées** : `/dashboard`, `/profile`, `/profile/projects`, `/esg/*`, `/carbon/*`, `/financing/*`, `/applications/*`, `/credit-score`, `/action-plan`, `/documents`, `/reports`.
- [ ] Le FAB est **absent** des pages publiques : `/login`, `/register`, `/forgot-password`.
- [ ] L'envoi d'un message depuis `/profile/projects` transmet `current_page=/profile/projects` au backend (vérifier via DevTools Network ou logs).
- [ ] Tests Playwright `frontend/e2e/chat-fab-visibility.spec.ts` passent.
- [ ] Aucune régression visuelle (z-index, layout) sur les pages où le FAB était déjà visible.
- [ ] Dark mode toujours respecté (cf. CLAUDE.md — le FAB doit avoir ses classes `dark:*`).

## Notes

- Bug **bloquant pour l'UX** : sans FAB sur `/profile/projects`, l'utilisateur ne peut PAS demander à l'assistant de créer un projet via chat — il est forcé d'utiliser le bouton manuel `+ Créer un projet`. Cela contredit la promesse "agent conversationnel" du module 1 de la plateforme.
- Lié au bug 05 : sans FAB sur la page projets, on ne peut pas tester le flow de création conversationnelle dans son contexte natural.
- Vérifier en passant si d'autres widgets globaux ont le même problème (ex: notifications, toasts).
- Si Option A est choisie, profiter pour centraliser aussi la logique d'historique de conversations et la gestion du dark mode du FAB.
