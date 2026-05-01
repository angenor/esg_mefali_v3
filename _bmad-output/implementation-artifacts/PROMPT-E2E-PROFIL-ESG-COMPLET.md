# Prompt BMAD Quick Dev — E2E `agent-browser --headed` : création profil entreprise + génération score ESG complet

---

## CONTEXTE

- **Repo** : `/Users/mac/Documents/projets/2025/esg_mefali_v3`
- **Branche actuelle** : `fix/esg-scoring-node-routing` (PR #4 ouverte) — re-tester après merge sur `main` ou directement sur cette branche
- **Stack** : Nuxt 4 (frontend port 3000) + FastAPI (backend port 8000) + PostgreSQL (`esg_mefali_v3`)
- **Outil** : `agent-browser --headed` v0.8.5 (mode visible obligatoire pour observer animations widgets, dark mode, transitions)

## PRÉ-REQUIS À VÉRIFIER AVANT DÉMARRAGE

```bash
# 1. Frontend up
curl -s -o /dev/null -w "frontend: %{http_code}\n" http://localhost:3000/

# 2. Backend up AVEC --reload (sinon les fixes ne sont pas chargés !)
ps aux | grep -E "uvicorn.*app.main" | grep -v grep
# DOIT contenir "--reload --port 8000". Sinon : kill puis
# cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000

# 3. DB accessible
PGPASSWORD=postgres psql -h localhost -U postgres -d esg_mefali_v3 -c "SELECT count(*) FROM esg_assessments;"

# 4. Compte test disponible
PGPASSWORD=postgres psql -h localhost -U postgres -d esg_mefali_v3 -c "SELECT id, email FROM users WHERE email='moussa1@gmail.com';"
```

## OBJECTIF

Reproduire le **parcours utilisateur complet** d'un nouvel inscrit jusqu'à un score ESG terminé :

1. **Création de profil entreprise** complet (secteur, taille, localisation, ancienneté, ODD prioritaires) via le chat conversationnel **OU** via la page `/profile` (tester les deux chemins).
2. **Lancement et finalisation d'une évaluation ESG** avec scoring sur les 30 critères (E1-E10, S1-S10, G1-G10).
3. **Vérification visuelle et BDD** : 4 scores non-null + radar chart affiché + recommandations générées.

## COMPTE TEST

- Email : `moussa1@gmail.com`
- Mot de passe : `Moussa2026!`
- État de profil attendu en début de test : **incomplet** (~6%, secteur manquant — voir captures `ac5-replay/02-esg-page.png`)

> **Note importante** : si le compte a déjà un assessment `in_progress` (cas après les replays précédents), le LLM proposera de le reprendre. Soit reprendre, soit nettoyer la DB en début de test (cf. section Cleanup).

## SÉQUENCE E2E (à exécuter avec `agent-browser --session profil-esg-complet --headed`)

### Phase 1 — Login

```bash
agent-browser --session profil-esg-complet --headed open http://localhost:3000/login
agent-browser --session profil-esg-complet snapshot -i
# Identifier @e1 (email), @e2 (password), @e3 (Se connecter)
agent-browser --session profil-esg-complet fill @e1 "moussa1@gmail.com"
agent-browser --session profil-esg-complet fill @e2 "Moussa2026!"
agent-browser --session profil-esg-complet click @e3
agent-browser --session profil-esg-complet wait --url "**/dashboard"
agent-browser --session profil-esg-complet screenshot _bmad-output/implementation-artifacts/widget-esg-fix-evidence-v3/profil-esg-complet/01-login.png
```

### Phase 2 — Profilage via chat (parcours conversationnel)

**Chemin A — chat profilage guidé** :

```bash
agent-browser --session profil-esg-complet open http://localhost:3000/dashboard
agent-browser --session profil-esg-complet snapshot -i
# Trouver bouton "Ouvrir l'assistant IA" (ref variable selon DOM)
agent-browser --session profil-esg-complet click <ref>
# Trouver bouton "Historique des conversations" puis "+ Nouvelle conversation"
agent-browser --session profil-esg-complet click <historique-ref>
agent-browser --session profil-esg-complet click <nouvelle-conv-ref>
```

Envoyer **un seul message dense** qui couvre tous les champs IDENTITY_FIELDS :

```
Bonjour, je suis Moussa, fondateur de Moussa SARL. C'est une PME agroalimentaire
basee a Dakar (Senegal), creee en 2020. On emploie 18 personnes (12 femmes, 6 hommes)
et notre chiffre d'affaires annuel est de 85 millions FCFA. Nos priorites ESG sont
ODD 8 (travail decent), ODD 12 (production responsable) et ODD 13 (climat).
```

```bash
agent-browser --session profil-esg-complet fill <textbox-ref> "<message ci-dessus>"
agent-browser --session profil-esg-complet press Enter
# Attendre extraction profilage : 15-25s (extract_profile_from_message + update_company_profile)
sleep 25
agent-browser --session profil-esg-complet screenshot _bmad-output/.../profil-esg-complet/02-profilage-chat.png
```

**Vérifications après profilage** :

```bash
# Le profil doit etre passe a >= 70% (seuil pour quitter le mode profilage prioritaire)
PGPASSWORD=postgres psql -h localhost -U postgres -d esg_mefali_v3 -t -c "
  SELECT name, sector, size_employees, country, city, founded_year, revenue_xof
  FROM company_profiles
  WHERE user_id = (SELECT id FROM users WHERE email='moussa1@gmail.com');
"
# DOIT retourner : Moussa SARL, agroalimentaire, 18, Senegal, Dakar, 2020, 85000000
```

**Chemin B — page `/profile` (alternatif, à tester si chemin A ne complete pas)** :

```bash
agent-browser --session profil-esg-complet open http://localhost:3000/profile
agent-browser --session profil-esg-complet snapshot -i
# Remplir manuellement les champs manquants (sector dropdown, taille, etc.)
# Capturer 03-profilage-page.png
```

### Phase 3 — Lancement évaluation ESG

```bash
# Re-ouvrir le chat sur une nouvelle conversation pour eviter l'effet "reprise d'assessment in_progress"
agent-browser --session profil-esg-complet open http://localhost:3000/dashboard
# Cliquer "Ouvrir l'assistant IA" → "Historique" → "+ Nouvelle conversation"
agent-browser --session profil-esg-complet fill <textbox> "lance mon évaluation ESG"
agent-browser --session profil-esg-complet press Enter
sleep 15
agent-browser --session profil-esg-complet screenshot _bmad-output/.../profil-esg-complet/04-esg-routed.png
```

**Vérifier que `_route_esg=True` a fonctionné** :

```bash
# tool_call_logs doit montrer create_esg_assessment success dans les 2 dernieres minutes
PGPASSWORD=postgres psql -h localhost -U postgres -d esg_mefali_v3 -t -c "
  SELECT created_at, node_name, tool_name, status
  FROM tool_call_logs
  WHERE created_at > NOW() - INTERVAL '2 minutes'
  ORDER BY created_at DESC LIMIT 5;
"
# Resultat attendu : esg_scoring | create_esg_assessment | success
```

### Phase 4 — Réponse aux 30 critères (parcours nominal)

L'assistant pose des questions par groupe (2-3 questions par pilier). Pour chaque question :

- Soit répondre **librement** (texte ouvert) — le LLM extraira un score 0-10
- Soit cliquer sur un widget interactif (radio/checkbox)
- Soit, **pour aller vite et tester `batch_save_esg_criteria`**, taper :

```
applique des hypothèses prudentes (score 4/10 par défaut) pour TOUS les critères
restants ET appelle batch_save_esg_criteria pour TOUS les 30 critères en une
seule fois, puis finalise immédiatement l'évaluation avec finalize_esg_assessment.
```

> Capture screenshot après chaque pilier complété : `05-pillar-E.png`, `06-pillar-S.png`, `07-pillar-G.png`.

### Phase 5 — Finalisation et vérification scores

```bash
sleep 60  # finalize_esg_assessment + benchmark sectoriel + radar = 30-90s
agent-browser --session profil-esg-complet screenshot _bmad-output/.../profil-esg-complet/08-final-result.png

# DB final state
PGPASSWORD=postgres psql -h localhost -U postgres -d esg_mefali_v3 -c "
  SELECT id, status, overall_score, environment_score, social_score, governance_score,
         jsonb_array_length(evaluated_criteria) AS nb_criteres,
         created_at, updated_at
  FROM esg_assessments
  WHERE user_id = (SELECT id FROM users WHERE email='moussa1@gmail.com')
  ORDER BY created_at DESC LIMIT 1;
"
# CRITERES PASS :
# - status = 'completed'
# - overall_score, environment_score, social_score, governance_score : tous non-null, dans [0, 100]
# - nb_criteres = 30
```

### Phase 6 — Vérification UI page `/esg`

```bash
agent-browser --session profil-esg-complet open http://localhost:3000/esg
sleep 3
agent-browser --session profil-esg-complet screenshot _bmad-output/.../profil-esg-complet/09-esg-page-with-result.png
agent-browser --session profil-esg-complet snapshot -i
```

**Éléments à valider visuellement** :
- [ ] Carte « Évaluation ESG » affiche les 4 scores
- [ ] Radar chart visible (Chart.js)
- [ ] Liste des 30 critères avec scores individuels
- [ ] Bouton « Voir le rapport PDF » présent (sans le générer ici)
- [ ] Dark mode toggle fonctionnel sans régression visuelle (capture `10-dark-mode.png`)

## CRITÈRES D'ACCEPTATION

| AC | Description | Verdict attendu |
|----|-------------|-----------------|
| AC1 | Profil entreprise passe à ≥ 70% completion après le message dense | PASS |
| AC2 | `_detect_esg_request("lance mon évaluation ESG")` route vers `esg_scoring_node` | PASS |
| AC3 | Row `esg_assessments` créée en `status='draft'` puis `'in_progress'` | PASS |
| AC4 | `batch_save_esg_criteria` invoqué sans `TypeError: '_CriterionItem'` (post-fix bug `[M]`) | PASS |
| AC5 | `finalize_esg_assessment` produit 4 scores non-null + 30 critères | PASS |
| AC6 | Page `/esg` affiche radar chart + scores après refresh | PASS |
| AC7 | Aucune erreur console JS, aucun stack trace dans `/tmp/uvicorn-*.log` | PASS |
| AC8 | Dark mode toggle ne casse pas l'affichage des scores | PASS |

## CLEANUP (entre 2 runs si nécessaire)

```bash
# ATTENTION : destructif. Ne supprime QUE les données du compte de test.
PGPASSWORD=postgres psql -h localhost -U postgres -d esg_mefali_v3 -c "
DO \$\$
DECLARE u_id uuid;
BEGIN
  SELECT id INTO u_id FROM users WHERE email='moussa1@gmail.com';
  DELETE FROM tool_call_logs WHERE user_id = u_id;
  DELETE FROM interactive_questions WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id = u_id);
  DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id = u_id);
  DELETE FROM esg_assessments WHERE user_id = u_id;
  DELETE FROM conversations WHERE user_id = u_id;
  -- Reset profile to incomplete state (sans supprimer le user lui-meme)
  UPDATE company_profiles SET sector=NULL, size_employees=NULL, country=NULL, city=NULL, founded_year=NULL, revenue_xof=NULL WHERE user_id = u_id;
END \$\$;
"
```

## RÈGLES DE RÉALISATION

- **Mode `--headed` OBLIGATOIRE** : observer visuellement les transitions widgets, dark mode, animations.
- **Session isolée** : `--session profil-esg-complet` pour ne pas polluer `ac5-replay`.
- **Captures dans** `_bmad-output/implementation-artifacts/widget-esg-fix-evidence-v3/profil-esg-complet/` (créer le dossier au début).
- **Backend doit être en `--reload`** sinon les fixes du PR #4 (regex `_detect_esg_request`, anti-boucle, coercion Pydantic) ne sont pas chargés.
- **Surveiller `tail -f /tmp/uvicorn-*.log`** dans une autre fenêtre pour détecter `TypeError`, `Traceback`, `KeyError`.
- **Timeout total** : 10 min max. Si scoring bloque > 90s sur une étape, capturer l'état + le state DB et reporter.

## LIVRABLES ATTENDUS

1. Dossier `profil-esg-complet/` avec ≥ 10 captures (login → profilage → routing → piliers → finalisation → vérification UI).
2. Fichier `REPORT.md` synthétisant les 8 AC avec verdict PASS/FAIL/PARTIAL et timestamps.
3. Snapshot DB final (`SELECT * FROM esg_assessments WHERE user_id = ...`) en `db-final-state.txt`.
4. Si une régression est trouvée : prompt BMAD de fix dédié dans le même dossier.

## RÉFÉRENCES

- Spec du fix routage : `_bmad-output/implementation-artifacts/spec-fix-esg-scoring-node-routing.md`
- Bug original : `widget-esg-fix-evidence-v3/REPORT.md`
- Replay AC5 antérieur : `widget-esg-fix-evidence-v3/ac5-replay/`
- Helper agent-browser : `~/.claude/skills/agent-browser/SKILL.md`
- CLAUDE.md du projet : `/Users/mac/Documents/projets/2025/esg_mefali_v3/CLAUDE.md`
