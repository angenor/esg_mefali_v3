# Runbook Back-Office Admin (F09)

> **Public** : Administrateurs ESG Mefali (rôle `ADMIN`).
> **Pré-requis** : compte Admin créé via `python -m app.scripts.seed_admin`,
> accès à `/admin/*` après authentification.

Ce runbook décrit les procédures opérationnelles courantes du back-office.
Toute action métier (création, mise à jour, publication, révocation) est
journalisée dans `audit_log` (F03) avec `source_of_change=admin` et
`actor_metadata.admin_action=<type>`.

---

## 1. Ajouter une nouvelle source officielle (workflow 4-yeux)

**Contexte.** Toute valeur catalogue (facteur d'émission, indicateur, critère,
fonds) doit pointer vers une `Source` ayant `verification_status='verified'`.
Le workflow 4-yeux impose que l'admin qui valide soit différent de celui qui a
saisi (CHECK constraint + trigger PostgreSQL).

### Étapes

1. **Saisie** (Admin A) — `/admin/sources/new` :
   - Renseigner l'URL canonique du document officiel (PDF, page web).
   - Titre, éditeur (publisher), version, date de publication, page,
     section.
   - Sauvegarder → la source est créée en `verification_status='pending'`,
     `captured_by=A`.
2. **Vérification croisée** (Admin B ≠ A) — `/admin/sources/{id}` :
   - Ouvrir l'URL pour vérifier accessibilité et conformité.
   - Cliquer **« Marquer vérifiée »** (le bouton n'est pas affiché pour
     l'admin A — règle 4-yeux côté UI).
   - La source passe en `verified`, `verified_by=B`, `verified_at=now()`.
3. Si l'URL est cassée ou périmée, marquer **« Obsolète »** (champ raison
   obligatoire). Les entités catalogue qui pointent vers la source restent
   intactes mais doivent être migrées (cf. § 5).

> ⚠ **Erreur 4-yeux** : si l'admin A tente PATCH avec
> `verification_status=verified`, le trigger PostgreSQL renvoie 400 + message
> structuré.

---

## 2. Publier un fonds, intermédiaire ou offre

**Contexte.** Une entité catalogue passe `draft → published` uniquement si
**toutes les sources liées sont `verified`** (publish gating, trigger BDD).

### Étapes

1. Créer ou éditer le fonds via `/admin/funds/{id}`.
2. Lier au moins une source `verified` (champ `source_id`).
3. Cliquer **« Publier »** : la requête `POST /admin/funds/{id}/publish`
   tente l'UPDATE.
4. Si le gating bloque (sources `pending`/`outdated`), un toast affiche les
   UUIDs bloquants.
   - Action : retourner sur les sources concernées et déclencher § 1.

> 💡 **Astuce** : `simulation_factors` et `funds` partagent le même workflow,
> mais les `simulation_factors` peuvent rester `status='pending'` sans
> source pour les valeurs en attente de validation éditoriale.

---

## 3. Gérer un incident PME (consultation + reset password + révocation)

### 3.1 Consulter le compte

1. `/admin/companies` — chercher par nom ou statut.
2. Cliquer sur la ligne → `/admin/companies/{account_id}` charge l'overview
   (profil, projets F06, candidatures, scores, attestations).
3. **L'appel déclenche un audit log `view_admin`** visible côté PME via
   `/historique` (dédup quotidienne — un seul log par admin/par compte/par
   jour).

### 3.2 Réinitialiser le mot de passe

1. Sur `/admin/companies/{account_id}` → onglet « Utilisateurs ».
2. Bouton **« Reset password »** sur l'utilisateur ciblé.
3. Confirmer → token créé en BDD (TTL 1h, hash sha256), email envoyé via
   `EmailService` (backend `console` en dev, SMTP en staging/prod).
4. L'utilisateur reçoit un lien `/auth/reset?token=<plain>` et complète
   son nouveau mot de passe (≥ 8 caractères).
5. Audit log : `reset_password_initiated` côté admin,
   `reset_password_completed` côté user.

### 3.3 Désactiver un compte

`/admin/users/{id}/toggle-active` avec champ `reason` (≥ 10 caractères).
La PME ne peut plus se connecter. Audit log `user_deactivated`.

### 3.4 Révoquer une attestation

1. `/admin/attestations` — filtrer par tenant ou statut.
2. Cliquer **« Révoquer »** → modal demande la raison (≥ 10 caractères).
3. POST `/admin/attestations/{id}/revoke` met à jour `revoked_at`,
   `revoked_reason`, `revoked_by_user_id`.
4. La page publique `/verify/{display_id}` affiche désormais
   `{ valid: false, revoked: true, reason: "..." }`.

---

## 4. Interpréter le dashboard métriques

`/admin/metrics` agrège :

| Section | Contenu | Lecture |
|---------|---------|---------|
| **Sources** | Total + breakdown par `verification_status` | `pending` élevé = backlog 4-yeux à résorber. |
| **Comptes PME** | Total / actifs / inactifs / nouveaux 30j / suppression programmée | Trend nouveaux 30j stagne ⇒ attention canal d'acquisition. |
| **Candidatures** | `by_status` + `submission_rate` | Taux soumission < 30 % ⇒ analyser blocages F08/F09. |
| **Attestations** | actives / révoquées / expirées | `revoked` élevé ⇒ enquête anti-fraude. |
| **Coûts LLM** | Placeholder MVP | Activé post-MVP via `tool_call_logs.cost_usd`. |

> **Performance** : l'endpoint `GET /admin/metrics/overview` exécute ~5
> requêtes COUNT/GROUP BY. Cache 5 min envisagé en post-MVP (cf. spec
> Phase 7).

---

## 5. Suppression destructive (analyse d'impact)

**Contexte.** Les sources et entités catalogue ont des dépendances en
cascade. La suppression sans `force=true` est refusée si des dépendances
existent.

### Étapes

1. Sur la fiche source `/admin/sources/{id}`, le panneau « Entités dépendantes »
   liste les indicateurs/critères/fonds qui pointent vers la source.
2. Cliquer **« Supprimer »** → modal `<ImpactAnalysisModal>` affiche
   la liste groupée par type avec compteurs.
3. Si dépendants > 0 : bouton **« Forcer la suppression »** appelle
   DELETE avec `?force=true` → cascade `valid_to=today()` sur les dépendants.
4. Audit log `<entity>_deleted` + `<entity>_force_cascaded` pour chaque
   dépendant impacté.

> ⚠ **Préférer le marquage `outdated`** quand c'est possible : il préserve
> la traçabilité historique sans casser les liens BDD.

---

## 6. Migrer une BDD existante (script seed_publish_existing_catalog.py)

**Contexte.** La migration Alembic 035 ajoute `publication_status='draft'`
par défaut. Les fonds/intermédiaires/etc. déjà en BDD restent donc en
`draft` même s'ils sont effectivement utilisés en prod. Le script
`seed_publish_existing_catalog.py` les passe en `published` si toutes
leurs sources liées sont `verified`.

```bash
cd backend
source venv/bin/activate
python -m app.scripts.seed_publish_existing_catalog --dry-run   # preview
python -m app.scripts.seed_publish_existing_catalog              # apply
```

Le script est **idempotent** (skip si déjà `published`) et journalise dans
`audit_log` avec `source_of_change=script`,
`admin_action=batch_publish_existing`.

---

## 7. Dépannage

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| Publish 400 « blocking_sources » | Source `pending` ou `outdated` | Lancer § 1 sur les UUIDs listés. |
| 4-eyes 400 | Admin tente verify sa propre saisie | Demander à un autre admin de valider. |
| `view_admin` doublon J | Bug dédup | Vérifier `actor_metadata.dedup_strategy='daily'` ; sinon ouvrir un ticket. |
| `Event loop is closed` en tests | Bug pytest pré-existant (non-F09) | Skip les tests admin_metrics dans la suite combinée ou utiliser `--forked`. |

---

## Annexe — Endpoints REST exposés

```
GET    /api/admin/sources          (list filtré)
POST   /api/admin/sources          (create draft)
PATCH  /api/admin/sources/{id}     (update / verify / outdate)
DELETE /api/admin/sources/{id}     (impact analysis + force)

GET    /api/admin/funds | /intermediaries | /offers
POST   /api/admin/{type}/{id}/publish

GET    /api/admin/referentials | /indicators | /criteria
POST   /api/admin/{type}                       (create draft)
PATCH  /api/admin/{type}/{id}                  (update)
POST   /api/admin/{type}/{id}/publish
DELETE /api/admin/{type}/{id}                  (drafts uniquement)

GET    /api/admin/emission-factors | /simulation-factors
POST/PATCH/DELETE                               (idem)

GET    /api/admin/companies                    (list paginée)
GET    /api/admin/companies/{account_id}       (overview + view_admin dedup)

GET    /api/admin/attestations                 (cross-tenant)
POST   /api/admin/attestations/{id}/revoke     (raison ≥ 10 chars)

GET    /api/admin/metrics/overview             (sources/comptes/applications/attestations)
GET    /api/admin/metrics/validation-failures  (F22 — tools failures)

POST   /api/admin/users/{id}/reset-password    (token + email)
POST   /api/admin/users/{id}/toggle-active     (raison obligatoire)
GET    /api/admin/health                       (200 si admin)
```

---

**Maintenu par** : équipe ESG Mefali. Toute évolution doit mettre à jour ce
runbook + `specs/035-f09-back-office-admin/spec.md`.
