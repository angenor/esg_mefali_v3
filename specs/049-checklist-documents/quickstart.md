# Quickstart — Validation manuelle de bout en bout

Feature : **049-checklist-documents** | Date : 2026-06-03

Scénario de recette couvrant les 5 user stories. À exécuter après implémentation (en complément des tests automatisés).

## Pré-requis

```bash
# Backend (venv actif)
source backend/venv/bin/activate
uvicorn app.main:app --reload
# Frontend
cd frontend && npm run dev
```

- Un compte PME avec au moins un **dossier de candidature** existant (sinon en créer un depuis le parcours financement).
- Connexion en tant que PME propriétaire du dossier. Tester aussi bien en **mode clair qu'en dark mode** (toggle UI).

## Parcours

### US1 — Téléverser un fichier sur un item manquant (P1)
1. Ouvrir `/applications/{id}` → onglet **Checklist**.
2. Repérer un item « Manquant ». Cliquer **Téléverser** et choisir un PDF valide (< 10 MB).
3. ✅ L'item passe à « Fourni », affiche le **nom du fichier** ; la progression (M/N) s'incrémente dans l'onglet et sur la carte du dossier (revenir sur `/applications`).
4. Tenter un fichier non supporté (ex. `.txt`) ou > 10 MB → ✅ message d'erreur français clair, item reste « Manquant ».

### US2 — Rattacher un document existant (P2)
1. Sur un item « Manquant », cliquer **Choisir un existant**.
2. ✅ Une modale liste les documents du compte (ceux de /documents et du chatbot). Sélectionner un document.
3. ✅ L'item passe à « Fourni » et pointe vers ce document.
4. Cas compte vide : si aucun document → ✅ la modale l'indique et propose de téléverser.

### US3 — Prévisualiser (P3)
1. Sur un item « Fourni », cliquer **Aperçu**.
2. ✅ Le document s'affiche (PDF en iframe / image), sans quitter la page du dossier.

### US4 — Détacher / Remplacer (P3)
1. Sur un item « Fourni », cliquer **Détacher** → ✅ l'item repasse « Manquant », progression décrémentée ; le document reste visible sur `/documents`.
2. Sur un item « Fourni », cliquer **Remplacer** et fournir un autre document → ✅ l'item reste « Fourni » avec le nouveau nom de fichier.

### US5 — Progression (P4)
1. Onglet Checklist : ✅ indicateur « M / N documents fournis » exact.
2. Page `/applications` : ✅ badge compact « M/N » sur la carte du dossier, cohérent.

## Cas limites
- **Document supprimé** : rattacher un document à un item, aller sur `/documents`, supprimer ce document, revenir au dossier → ✅ l'item est repassé « Manquant » (pas d'erreur, pas de fichier fantôme).
- **Réutilisation** : rattacher le **même** document à deux items différents (ou deux dossiers) → ✅ accepté.
- **Dossier sans documents requis** : ✅ l'onglet affiche « Aucun document requis ».
- **Multi-tenant** (test API/dev) : tenter de rattacher via API un `document_id` d'un autre compte → ✅ `403`, aucun changement.

## Parité & audit
- **Chatbot** : demander au chat « où en est ma checklist ? » → ✅ les items fournis remontent correctement (nom + statut), cohérent avec l'UI (FR-019).
- **Fiche de préparation** (dossier via intermédiaire) : ✅ les documents fournis apparaissent comme disponibles.
- **Audit** : page `/historique` (ou `/admin/audit`) → ✅ les rattachements/détachements figurent dans le journal.

## Vérification couverture
```bash
# Backend
cd backend && pytest tests/test_applications/test_checklist_documents.py tests/test_documents/test_delete_cleanup.py tests/test_tools/test_application_tools.py --cov=app/modules/applications --cov=app/modules/documents
# Frontend
cd frontend && npm run test
```
Objectif : ≥ 80 % sur le code ajouté (Constitution IV).
