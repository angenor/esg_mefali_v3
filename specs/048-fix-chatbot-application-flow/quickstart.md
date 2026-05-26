# Quickstart — Validation manuelle (048-fix-chatbot-application-flow)

**Pré-requis** :
```bash
# Backend (venv actif)
source backend/venv/bin/activate
uvicorn app.main:app --reload
# Frontend
cd frontend && npm run dev
```
Compte PME authentifié avec ≥ 1 projet actif (ex. « Solarisation Boulangerie Dakar ») et une offre publiée (ex. « GCF via BOAD »).

## Scénario 1 — Créer un dossier via le chatbot depuis n'importe quelle page (US1)
1. Ouvrir le chat **depuis `/documents`** (slug `documents`).
2. Demander : « génère-moi un dossier de candidature pour GCF via BOAD ».
3. **Attendu** :
   - Le chatbot confirme le projet et l'offre (lève l'ambiguïté de nom si besoin).
   - **Aucun** message « outil indisponible ».
   - Si critères ESG requis complets : dossier `draft` créé + document généré téléchargeable, indiqué comme consultable dans `/documents`.
   - Si critères requis manquants (US2/D4) : pas de document, guidage vers les critères à compléter.

## Scénario 2 — Mémoire ESG entre sessions (US2)
1. Session A (chat) : démarrer/poursuivre l'évaluation ESG d'un projet pour BOAD ESS, renseigner ≥ 2 critères (dont ESS 1, ESS 2).
2. Fermer la conversation, **ouvrir une nouvelle conversation** (session B).
3. Demander : « où en est mon évaluation ESG du projet Solarisation Boulangerie Dakar ? ».
4. **Attendu** : le chatbot reconnaît l'évaluation, présente ESS 1/ESS 2 comme **couverts**, reflète le score/couverture réels. Aucun critère déjà rempli n'est annoncé « manquant » (SC-002).

## Scénario 3 — Bouton « Candidater » (US3)
1. Aller sur `/financing/offers/{offer_id}?project_id={project_id}`.
2. Cliquer **« Candidater »**.
3. **Attendu** : un dossier `draft` est créé (rattaché projet + offre) et l'on est conduit vers le dossier (ou `/documents`). Aucune page 404, aucun clic sans effet. Un second clic ne crée pas de doublon (SC-006).
4. Variante sans `project_id` : message de guidage clair (FR-015).

## Vérifications transverses
- Le dossier créé via chat et via bouton sont **équivalents** (mêmes `offer_id`/`project_id`, statut `draft`) — FR-016.
- Le document généré apparaît bien dans `/documents`.
- Les chiffres affichés restent sourcés (F01) ; le cloisonnement multi-tenant (F02) et l'audit (F03) sont respectés.

## Tests automatisés (rappel TDD — écrits AVANT l'implémentation)
```bash
# Backend
pytest backend/tests -k "tool_selector or context_esg or application_create or export or gating" --cov=app --cov-report=term-missing
# Frontend
cd frontend && npx vitest run && npx playwright test
```
Cible couverture : ≥ 80 % sur les modules touchés.
