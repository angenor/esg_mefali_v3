# F03 — Audit Log Append-Only

**Module(s) source(s)** : Module 0.4 (Audit Log)
**Priorité** : P0 — bloquante pour la défense réglementaire et la confiance utilisateur
**Dépendances** : F02 (account_id, role)
**Estimation** : 1.5 sprints

## Contexte & motivation

Module 0.4 du brainstorming : « Quasi-réglementaire en finance pour défense en cas de litige. »

**État actuel** :
- Aucune table `audit_log`. `grep "audit_log\|AuditLog"` → 0 résultats.
- La table `tool_call_logs` (`backend/app/models/tool_call_log.py`) trace les appels de tools LangGraph (user_id, conversation_id, node_name, tool_name, tool_args, tool_result, status, retry_count) MAIS :
  - Pas de `entity_type/entity_id/field/old_value/new_value`
  - Pas de `source_of_change` (manual / llm / import)
  - Pas de log des éditions manuelles via API REST classique
  - Pas append-only (sans contrainte INSERT-only)
- Aucune page Module 7.2 "Historique des actions" pour la PME
- Aucun export CSV/JSON

**Conséquences** :
- En cas de litige avec un fund officer ("vous avez modifié le score juste avant la soumission ?"), aucune défense possible
- En cas de bug ou de régression, impossible de reproduire l'état d'une entité à un moment T
- En cas d'incident de sécurité, aucune trace de qui a fait quoi
- Conformité auditable impossible

## User stories

- **PME** : « En tant que PME, je veux pouvoir consulter dans `/historique` toutes les actions effectuées sur mon compte (par moi, mes collaborateurs, le LLM ou les imports), avec qui, quand, quoi, ancienne et nouvelle valeur. »
- **PME** : « Je veux pouvoir exporter cet historique en CSV ou JSON pour archive ou pour partager à un auditeur. »
- **Admin** : « En tant qu'admin, je veux trace que j'ai consulté un compte PME (qui ? quand ? quel compte ?) — la consultation elle-même est auditée. »
- **Architecte** : « Je veux qu'aucune mutation métier ne puisse contourner le log : que ce soit via le LLM, via une API REST manuelle, ou via un import batch, le diff doit être tracé automatiquement. »

## Périmètre fonctionnel

### Table `audit_log` append-only

Schéma :
- `id: UUID` (PK)
- `user_id: UUID FK users.id` (qui a fait l'action — toujours nécessaire)
- `account_id: UUID FK accounts.id` (qui possède la donnée — pour RLS visibilité PME)
- `timestamp: timestamptz NOT NULL DEFAULT now()`
- `entity_type: str NOT NULL` (ex : "company_profile", "fund_application", "esg_assessment", "credit_score", "candidature_status")
- `entity_id: UUID NOT NULL` (l'objet muté)
- `action: enum('create', 'update', 'delete', 'view_admin')` (le verbe)
- `field: str | null` (le champ muté pour `update` ; null pour `create`/`delete`)
- `old_value: jsonb | null` (valeur avant)
- `new_value: jsonb | null` (valeur après)
- `source_of_change: enum('manual', 'llm', 'import', 'admin') NOT NULL`
- `actor_metadata: jsonb | null` (contexte additionnel : tool_name, conversation_id, request_id, ip_address, user_agent)

Contraintes append-only :
- Trigger PostgreSQL `BEFORE UPDATE ON audit_log` qui lève une exception
- Trigger PostgreSQL `BEFORE DELETE ON audit_log` qui lève une exception (sauf si admin spécial avec rôle `dpo`, post-MVP)
- Permission DB : le user applicatif a `INSERT, SELECT` mais pas `UPDATE, DELETE`

Index :
- `(account_id, timestamp DESC)` pour scrolling chronologique
- `(account_id, entity_type, entity_id)` pour reconstituer l'historique d'une entité
- `(user_id, timestamp DESC)` pour audit par acteur
- `(source_of_change, timestamp DESC)` pour métriques admin

### Mixin `Auditable` SQLAlchemy

Créer `backend/app/core/auditable.py` :
- Mixin qui hooke `event.listens_for(Session, 'before_flush')` ou les events `before_insert/before_update/before_delete`
- Pour chaque mutation, capture :
  - L'entité, l'id
  - Le diff field-by-field (old → new)
  - Le user courant (depuis context var)
  - Le `source_of_change` (depuis context var positionné par le middleware)
- Insère un row dans `audit_log` AVANT le commit principal (même transaction)

Modèles à rendre `Auditable` :
- `CompanyProfile`
- `FundApplication`
- `ESGAssessment`, `ESGCriterionScore`
- `CarbonAssessment`, `CarbonEmissionEntry`
- `CreditScore`
- `ActionPlan`, `ActionItem`
- (à étendre par les futures entités F06 `Project`, F07 `Offer`)

### Context variables `source_of_change`

Dans `backend/app/core/audit_context.py` :
- ContextVar `current_source_of_change: str` (défaut "manual")
- Les nœuds LangGraph SET `current_source_of_change.set("llm")` avant d'appeler les services
- Les imports batch SET "import"
- Les actions admin SET "admin" via le middleware admin

### Tools LLM tracés

Les tools de mutation LangChain (via F01 `cite_source` + tools existants `update_company_profile`, etc.) doivent invoquer les services métier qui passent par `Auditable` → l'audit log capture automatiquement avec `source_of_change = "llm"`.

Vérifier que **tous** les tools de mutation actuellement codés en bypass des services (avec `db.commit()` direct dans le tool) sont migrés pour passer par les services.

### Cas spécial : `view_admin` action

Quand un admin consulte un compte PME via le back-office :
- Insertion `audit_log(action='view_admin', source_of_change='admin', entity_type='account', entity_id=<account_id>, user_id=<admin_id>, account_id=<pme_account_id>)`
- Visible côté PME (pour transparence)

### API et UI

Endpoints :
- `GET /api/audit/me` (PME : son propre audit log)
  - Query params : `entity_type`, `entity_id`, `since` (date), `until`, `source_of_change`, `page`, `limit`
- `GET /api/audit/me/export` (export CSV ou JSON, header `Accept`)
- `GET /api/admin/audit/{account_id}` (admin only, audit log d'un compte spécifique)
- `GET /api/admin/audit` (admin only, audit log global)

Frontend :
- `pages/historique.vue` (Module 7.2) : timeline filtrable, recherche full-text, export
- Composant `<AuditLogEntry :event="..." />` qui rend une ligne lisible :
  - "📝 LLM a modifié votre profil entreprise (sector: agriculture → energie) — il y a 2 minutes"
  - "🗑️ Vous avez supprimé la candidature #42 (GCF via BOAD) — hier à 16:32"
  - "👁️ Un admin Mefali a consulté votre compte — il y a 3 jours"
- Composant `<AuditExportButton />` (CSV / JSON)

Page admin :
- `pages/admin/audit/index.vue` : audit log global filtrable
- Filtre par account, par user, par entity_type, par period

## Hors-scope (post-MVP)

- DPO formalisé avec rôle dédié et permission de purge GDPR (avec marquage cryptographique du gap)
- Hachage chaîné (Merkle tree) pour preuve d'intégrité forte
- Export PDF signé numériquement (Ed25519 cf. F08)
- Diff visuel side-by-side dans l'UI (juste valeurs textuelles MVP)
- Webhooks "change events" pour intégrations tierces

## Exigences techniques

### Backend

- Migration Alembic `020_create_audit_log.py` :
  - Table `audit_log` avec tous les champs
  - Triggers PostgreSQL BEFORE UPDATE/DELETE qui RAISE EXCEPTION
  - Permissions : `application_user` a `INSERT, SELECT` only
  - Indexes spécifiés
- Modèle `app/models/audit_log.py`
- Mixin `app/core/auditable.py` (event listeners SQLAlchemy)
- Context vars `app/core/audit_context.py`
- Module `app/modules/audit/` :
  - `service.py` : query helpers, format pour rendu
  - `router.py` : endpoints PME + admin
  - `schemas.py` : `AuditEvent`, `AuditEventList`, `AuditExportFormat`
- Modifications aux services existants :
  - `app/modules/company/service.py` : utiliser le mixin
  - `app/modules/applications/service.py` : utiliser le mixin
  - `app/modules/esg/service.py` : utiliser le mixin
  - `app/modules/carbon/service.py` : utiliser le mixin
  - `app/modules/credit/service.py` : utiliser le mixin
  - `app/modules/action_plan/service.py` : utiliser le mixin
- Modifications aux nœuds LangGraph : SET `current_source_of_change = "llm"` avant invocation des services
- Tests :
  - Test isolation RLS : audit_log d'un account A invisible depuis user account B (avec/sans RLS — F02)
  - Test append-only : `UPDATE audit_log SET ...` doit lever une exception
  - Test source_of_change : muter via API REST = "manual", muter via tool LangChain = "llm"
  - Test admin view : appel admin sur compte PME crée bien un audit_log "view_admin"

### Frontend

- Page `pages/historique.vue` avec layout default
- Composant `components/audit/AuditLogEntry.vue`
- Composant `components/audit/AuditExportButton.vue`
- Composant `components/audit/AuditFilters.vue`
- Composable `composables/useAuditLog.ts`
- Store Pinia `stores/audit.ts`
- Page admin `pages/admin/audit/index.vue` (avec layout admin de F02)
- Dark mode complet
- Pagination infinie ou par pages (50 par page)

### Base de données

- Table `audit_log`
- Triggers PostgreSQL append-only
- Indexes spécifiés
- Permission `application_user` : `INSERT, SELECT` only
- Granularité du diff JSON : ne pas stocker des objets gigantesques (limiter old_value/new_value à 10 KB chacun, tronquer si nécessaire avec marqueur `_truncated: true`)

## Critères d'acceptation

- [ ] Table `audit_log` créée avec tous les champs et contraintes
- [ ] Triggers append-only fonctionnels (UPDATE/DELETE → exception)
- [ ] Mixin `Auditable` instrumente les 6+ entités principales
- [ ] Toute mutation passe par les services (plus de `db.commit()` direct dans les tools LangChain)
- [ ] `source_of_change` correctement positionné selon contexte (manual / llm / import / admin)
- [ ] Endpoint `GET /api/audit/me` retourne le log filtrable du PME courant
- [ ] Endpoint `GET /api/audit/me/export` génère CSV ou JSON
- [ ] Endpoint admin `GET /api/admin/audit/{account_id}` accessible uniquement aux Admin (test 403 pour PME)
- [ ] Page `/historique` fonctionnelle, dark mode OK, filtre + pagination + export
- [ ] Page admin `/admin/audit` fonctionnelle
- [ ] Quand un admin consulte un compte PME, un audit_log `view_admin` est créé et visible côté PME
- [ ] Test E2E : créer une candidature via LLM → vérifier audit_log entry avec source_of_change=llm + diff complet
- [ ] Test E2E : éditer profil via /profile → vérifier audit_log entry avec source_of_change=manual
- [ ] Couverture tests ≥ 85 %
- [ ] Documentation `docs/audit-log.md` : modèle de menaces, schéma, requêtes communes, format export

## Risques & garde-fous

- **Risque** : volume d'audit_log explose (1 row par mutation × 1000 PME × 100 mutations/jour = 100k rows/jour). **Garde-fou** : pagination obligatoire, partitionnement PostgreSQL par mois (post-MVP), archivage à froid après 12 mois.
- **Risque** : performance des INSERT audit_log dégrade les services métier. **Garde-fou** : insertion dans la même transaction (ACID) ; benchmark : overhead acceptable < 5 ms par mutation.
- **Risque** : taille des `old_value/new_value` JSON pour de gros objets (ex : `assessment_data` JSON de 100 KB). **Garde-fou** : tronquer à 10 KB avec marqueur `_truncated`, stocker seulement les **champs modifiés** (diff field-level), pas l'objet entier.
- **Risque** : un dev oublie d'appliquer `Auditable` sur une nouvelle entité. **Garde-fou** : test CI qui vérifie que les modèles dans une whitelist (`AUDITABLE_MODELS`) appliquent bien le mixin.
- **Risque** : un attaquant qui obtient l'accès DB peut tenter `DELETE FROM audit_log`. **Garde-fou** : permission DB stricte (application_user n'a pas `DELETE`), backup quotidien hors-site, post-MVP : hachage chaîné Merkle.
- **Risque** : RGPD vs append-only. Le droit à l'oubli (GDPR Art. 17) impose la suppression. **Garde-fou** : post-MVP, prévoir un mécanisme DPO de "tombstone" qui anonymise les valeurs personnelles tout en gardant l'événement et le hash. Pour MVP, documenter la limite.
