# Quickstart — F10 Widgets Interactifs Bottom Sheet Complets

**Date** : 2026-05-07
**Phase** : 1

Guide pas-à-pas pour mettre en place et tester localement la feature F10.

## Prérequis

- Branche `feat/F10-widgets-bottom-sheet-complets` checkout depuis `main` à jour
- Python 3.12 installé
- Node.js 20+ installé
- PostgreSQL 16 + pgvector (Docker ou local)
- libmagic installé (macOS : `brew install libmagic`, Linux : `apt install libmagic1`)

## Étape 1 — Backend setup

```bash
cd /Users/mac/Documents/projets/2025/esg_mefali_v3/backend

# Activer le venv (toujours)
source venv/bin/activate

# Installer les nouvelles dépendances
pip install -r requirements.txt   # python-magic ajouté en Phase B

# Vérifier la disponibilité de libmagic (Python)
python -c "import magic; print(magic.from_buffer(b'%PDF-1.4', mime=True))"
# Attendu : application/pdf
```

## Étape 2 — Migration BDD

```bash
# Démarrer postgres (Docker)
docker compose up postgres -d

# Appliquer la migration 031
cd backend && source venv/bin/activate
alembic upgrade head

# Vérifier l'extension de l'enum
psql -h localhost -U postgres -d esg_mefali -c "
  SELECT enumlabel FROM pg_enum
  WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname='interactivequestiontype')
  ORDER BY enumsortorder;
"
# Attendu : 13 valeurs (4 F18 + 9 F10)

# Vérifier les colonnes ajoutées
psql -h localhost -U postgres -d esg_mefali -c "\d interactive_questions" | grep -E "payload|response_payload"
# Attendu : 2 colonnes jsonb
```

## Étape 3 — Frontend setup

```bash
cd /Users/mac/Documents/projets/2025/esg_mefali_v3/frontend

# Installer les nouvelles dépendances
npm install   # vue-virtual-scroller, zod ajoutés en Phase B

# Lancer le dev server
npm run dev
```

## Étape 4 — Démos manuelles

### Démo 1 : `ask_yes_no` destructif

1. Ouvrir une conversation et avoir au moins un projet existant.
2. Demander : « Supprime mon projet "Panneaux solaires" ».
3. Le LLM doit appeler `delete_project(confirm=False)` qui retourne `{requires_confirmation: True}`.
4. Le LLM doit ensuite appeler `ask_yes_no(destructive=True, question='Êtes-vous certain de vouloir supprimer définitivement le projet "Panneaux solaires" ?')`.
5. Un widget rouge avec deux boutons « Oui, supprimer » (rouge) / « Non, annuler » (gris) doit apparaître en bottom sheet.
6. Click-and-hold 2 s sur « Oui, supprimer » → animation d'anneau de progression → action exécutée.
7. Vérifier en BDD : projet supprimé + audit_log entry avec `metadata.confirm=true`.

### Démo 2 : `ask_select` UEMOA

1. Demander : « Dans quel pays UEMOA est votre siège ? ».
2. Le LLM doit appeler `ask_select(...)` avec 8 pays UEMOA groupés.
3. Le widget doit afficher un champ de recherche en haut + 8 options avec en-tête « UEMOA ».
4. Taper « Cote » → seul « Côte d'Ivoire » reste affiché.
5. Cliquer → message « ✓ Côte d'Ivoire » dans le fil.

### Démo 3 : `ask_number` CA en XOF

1. Demander : « Quel est votre chiffre d'affaires annuel ? ».
2. Le LLM doit appeler `ask_number(currency='XOF', min=0, max=1_000_000_000_000, step=100_000)`.
3. Saisir « 1000000 » → affichage « 1 000 000 » + équivalent EUR « ≈ 1 524 € » sous l'input.
4. Cliquer Valider → message « ✓ 1 200 000 FCFA » dans le fil.

### Démo 4 : `show_form` création projet

1. Préparer une conversation où le LLM a accumulé plusieurs informations sur un projet (nom, secteur, montant).
2. Demander : « Crée le projet ».
3. Le LLM doit appeler `show_form(...)` avec 8 champs préremplis.
4. Vérifier la validation : laisser un champ requis vide → bouton désactivé + message d'erreur.
5. Remplir tous les champs valides → cliquer Créer → projet en BDD + message « ✓ Projet créé : ... ».

### Démo 5 : `show_summary_card` extraction

1. Uploader un fichier `Statuts.pdf`.
2. Le LLM extrait des informations et appelle `show_summary_card(...)`.
3. Cliquer « Corriger » sur l'item « Capital social » → input inline.
4. Modifier la valeur → cliquer « Valider mes corrections ».
5. Vérifier le message : « ✓ Corrigé : Capital social 6 000 000 FCFA (au lieu de 5 000 000 FCFA) ».

## Étape 5 — Tests

```bash
# Backend tests unitaires + intégration
cd backend && source venv/bin/activate
pytest tests/unit/graph/tools/test_interactive_tools_*.py -v --cov=app.graph.tools.interactive_tools
pytest tests/integration/test_widget_e2e_*.py -v
pytest tests/integration/test_alembic_031_up_down_up.py -v

# Frontend tests unitaires
cd frontend
npm run test -- components/chat/widgets

# Frontend E2E Playwright
npx playwright test tests/e2e/F10-widgets-bottom-sheet-complets.spec.ts --reporter=html
# Ouvrir le rapport : open playwright-report/index.html
```

## Étape 6 — Test de migration up/down/up

```bash
cd backend && source venv/bin/activate

# 1. Up
alembic upgrade head

# 2. Down (ne fonctionne que si aucune ligne n'utilise les nouvelles valeurs d'enum)
# Pour tester en dev : tronquer la table d'abord
psql -c "DELETE FROM interactive_questions WHERE question_type IN ('yes_no','select','number','date','date_range','rating','file_upload','form','summary_card');"
alembic downgrade -1

# 3. Up à nouveau
alembic upgrade head
```

## Troubleshooting

### libmagic introuvable

```
ImportError: failed to find libmagic. Check your installation
```

Solution :
- macOS : `brew install libmagic`
- Linux : `apt install libmagic1`
- Vérifier `/usr/local/lib/libmagic*` existe.

### Migration 031 échoue : `ALTER TYPE ... ADD VALUE` non autocommit

PostgreSQL exige que `ALTER TYPE ADD VALUE` soit dans une transaction autocommit. Le bloc `with op.get_context().autocommit_block():` est obligatoire.

### Frontend : type d'enum inconnu

Si un payload SSE arrive avec un `question_type` inconnu (ex : déploiement progressif), le composant `UnsupportedWidget.vue` doit s'afficher avec un message clair. Vérifier `console.warn` côté frontend.

### Test E2E destructif : timing du hold

Playwright doit utiliser `await page.locator('[data-testid="confirm-destructive"]').dispatchEvent('mousedown')` puis `await page.waitForTimeout(2100)` avant `mouseup` pour valider le hold.

## Références

- Spec : `specs/031-widgets-bottom-sheet-complets/spec.md`
- Plan : `specs/031-widgets-bottom-sheet-complets/plan.md`
- Data model : `specs/031-widgets-bottom-sheet-complets/data-model.md`
- Contracts : `specs/031-widgets-bottom-sheet-complets/contracts/`
- Research : `specs/031-widgets-bottom-sheet-complets/research.md`
- Fiche source : `documents_et_brouillons/features_a_implementer/F10-widgets-bottom-sheet-complets.md`
