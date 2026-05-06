# F05 — RGPD : Page "Mes Données" + Consentements + Export/Suppression

**Module(s) source(s)** : Module 0.3 (Conformité Données Personnelles), Module 7.2 (Page "Mes données")
**Priorité** : P0 — bloquante pour la conformité réglementaire UEMOA / loi ivoirienne 2013-450 / RGPD
**Dépendances** : F02 (multi-tenant, account_id), F03 (audit log)
**Estimation** : 1.5 sprints

## Contexte & motivation

**Cadre légal** : RGPD européen + loi ivoirienne 2013-450 sur la protection des données + règlement UEMOA n°20/2010/CM/UEMOA.

**État actuel** :
- Aucune page "Mes données" / "Privacy" / "RGPD" dans `frontend/app/pages/`
- Aucun endpoint `GET /api/me/data/export` ou `DELETE /api/me/account`
- Aucun modèle `UserConsent` ou `ConsentLog`
- Aucune politique de confidentialité publiée (pas de `privacy.vue` ni `legal/privacy.html`)
- Aucune adresse email `privacy@`
- Module 5 spécifie 3 collectes nécessitant consentement granulaire (Mobile Money, photos exploitation, témoignages) — aucun mécanisme de consentement implémenté
- TLS 1.3 OK (`nginx/esg-mefali-vhost.conf.example:55`)
- Hébergement Europe/Afrique de l'Ouest : présomption non documentée

**Conséquences** :
- Première PME utilisatrice = violation immédiate des droits d'accès (Art. 15 RGPD), de portabilité (Art. 20), d'effacement (Art. 17)
- Absence de consentements granulaires → impossible de collecter Mobile Money (F18) légalement
- Risque réputationnel + légal majeur

## User stories

- **PME** : « En tant que PME, depuis `/mes-donnees`, je veux voir l'inventaire complet de mes données stockées (profil, projets, candidatures, scores, documents, conversations chat) et exporter le tout en JSON pour archive personnelle. »
- **PME** : « Je veux pouvoir supprimer définitivement mon compte avec un délai de grâce de 30 jours pour récupération éventuelle, après quoi tout est purgé (sauf audit log anonymisé pour conformité). »
- **PME** : « Avant que la plateforme analyse mes flux Mobile Money / photos d'exploitation / appelle des données publiques sur moi, je veux donner un consentement explicite par usage, et pouvoir le révoquer à tout moment. »
- **DPO ESG Mefali (post-MVP)** : « Je veux un dashboard des consentements actifs/révoqués, des demandes d'export en cours, des suppressions programmées. »

## Périmètre fonctionnel

### Page `/mes-donnees`

Sections :
1. **Inventaire de mes données**
   - Liste des entités stockées avec compteurs (profil entreprise : 1, projets : 3, candidatures : 5, évaluations ESG : 2, bilans carbone : 1, scores crédit : 1, documents : 12, conversations : 8, messages : 142, attestations : 1)
   - Date de dernière modification
   - Bouton "voir le détail" → page dédiée

2. **Exporter mes données**
   - Bouton "Exporter en JSON" (déclenche `GET /api/me/data/export?format=json`)
   - Fichier généré contient TOUT : profile, projects, applications, scores ESG, carbone, crédit, documents (métadonnées + URLs signées 24h pour download fichiers), conversations chat, attestations, audit log personnel, consentements
   - Format `application/json` zippé avec README.md inclus expliquant la structure
   - Délai de génération : asynchrone si > 100 MB (notification quand prêt)

3. **Mes consentements**
   - Liste granulaire :
     - Analyse profil entreprise pour matching financements (par défaut accordé à l'inscription)
     - Analyse documents uploadés par IA pour scoring ESG (par défaut accordé)
     - Analyse flux Mobile Money pour scoring crédit (par défaut **NON** accordé — F18)
     - Analyse photos exploitation par IA pour scoring crédit (par défaut **NON** accordé — F18)
     - Analyse données publiques (réseaux sociaux, avis) (par défaut **NON** accordé — F18)
     - Génération automatique d'attestation crédit transmissible (Module 5.3 / F08, par défaut accordé)
     - Communications produit / newsletter (par défaut **NON** accordé)
   - Toggle on/off avec effet immédiat (révocation = la donnée stockée est conservée mais plus utilisée pour ce traitement, sauf demande de suppression explicite)
   - Toute action enregistrée dans `consent_logs`

4. **Supprimer mon compte**
   - Bouton "Supprimer définitivement mon compte"
   - Modal de confirmation avec :
     - Liste des conséquences ("toutes vos candidatures seront annulées", "vos attestations seront révoquées", etc.)
     - Demande de saisir le mot de passe
     - Demande de saisir "SUPPRIMER" en majuscules
   - Suppression programmée à J+30 (champ `deletion_scheduled_at` sur `accounts`)
   - Email de confirmation avec lien d'annulation
   - Endpoint `POST /api/me/account/cancel-deletion` (avant J+30)
   - À J+30, cron purge effective :
     - Tous les rows `account_id = X` supprimés en cascade (sauf `audit_log` anonymisé : remplacer `user_id` par UUID nul, conserver `account_id` → null aussi, garder timestamp + entity_type + action)
     - Fichiers uploads : suppression effective sur S3/MinIO (`/uploads/{account_id}/...`)
     - Refresh tokens révoqués
     - Email final de confirmation de suppression

### Modèle `UserConsent`

Table `consents` :
- `id: UUID PK`
- `account_id: UUID FK accounts.id NOT NULL`
- `user_id: UUID FK users.id NOT NULL` (qui a donné/révoqué)
- `consent_type: enum(...)` (liste des consentements ci-dessus)
- `granted: bool NOT NULL`
- `granted_at: datetime`
- `revoked_at: datetime | null`
- `legal_basis: enum('consent', 'contract', 'legal_obligation', 'legitimate_interest')`
- `version: str` (version du texte de consentement présenté à l'utilisateur)
- `metadata: jsonb` (ip, user-agent au moment de l'action)

Table `consent_logs` (append-only via F03) :
- Append automatique à chaque INSERT/UPDATE sur `consents`

### Garde-fou applicatif

Les services qui dépendent d'un consentement doivent **vérifier l'état actif** avant exécution :

```python
async def analyze_mobile_money(account_id, user_id, ...):
    consent = await get_active_consent(account_id, "mobile_money_analysis")
    if not consent:
        raise HTTPException(403, "Consentement Mobile Money requis pour cette analyse")
    ...
```

À appliquer pour : F18 (Mobile Money + photos IA + données publiques), F08 (génération attestation), tout futur traitement non-essentiel.

### Politique de confidentialité publiée

Page publique `/legal/privacy.vue` (no-auth, layout `public`) :
- Texte rédigé en français (et EN post-MVP) couvrant :
  - Identité du responsable de traitement (ESG Mefali)
  - Finalités et bases légales par usage
  - Catégories de données collectées
  - Durée de conservation
  - Destinataires (sous-traitants : OpenRouter, exchangerate-api, hébergeur)
  - Transferts hors UE/UEMOA (s'il y en a — minimiser)
  - Droits utilisateurs (accès, rectification, effacement, portabilité, opposition, limitation, retrait consentement)
  - Comment exercer ses droits (lien vers `/mes-donnees` + email `privacy@esg-mefali.com`)
  - Coordonnées DPO (post-MVP : DPO formalisé)
  - Date de dernière mise à jour + historique des versions

### Email de contact

- Mail générique `privacy@esg-mefali.com` dans la politique
- Footer global avec lien vers `/legal/privacy`
- À l'inscription, case à cocher obligatoire "J'ai lu et j'accepte la politique de confidentialité v1.0"

### Documentation hébergement

- Créer `docs/hosting-and-data-residency.md` :
  - Provider utilisé (OVH / Scaleway / Africa Data Centres / etc.)
  - Région (Europe / Afrique Ouest)
  - Chiffrement at-rest (AES-256 du provider)
  - Backup encrypté + rétention
  - Sous-traitants (avec DPA si applicable)

### Hébergement vérifié

- Vérifier que le déploiement actuel respecte la contrainte (Europe ou Afrique de l'Ouest, **pas USA**)
- Si pas le cas : prévoir migration

## Hors-scope (post-MVP)

- DPO formalisé avec système de tickets
- Purge granulaire fine (par champ, par catégorie de données)
- Anonymisation k-anonymity sur les données analytics
- Demandes RGPD via email parsées automatiquement
- Audit RGPD externe annuel (process)
- Cookies banner (la plateforme n'utilise pas de cookies analytics tiers — à confirmer)

## Exigences techniques

### Backend

- Migration Alembic `022_consents_and_account_deletion.py` :
  - Table `consents`
  - Ajouter `deletion_scheduled_at`, `deleted_at` sur `accounts`
- Modèle `app/models/consent.py`
- Module `app/modules/me/` (ou `privacy/`) :
  - `service.py` : `export_account_data`, `schedule_account_deletion`, `cancel_deletion`, `purge_account` (cron)
  - `router.py` :
    - `GET /api/me/data/inventory` (compteurs)
    - `GET /api/me/data/export?format=json` (export complet)
    - `GET /api/me/consents` (liste)
    - `POST /api/me/consents/{type}/grant`
    - `POST /api/me/consents/{type}/revoke`
    - `POST /api/me/account/schedule-deletion`
    - `POST /api/me/account/cancel-deletion`
- Helper `app/core/consent.py` : `require_consent(account_id, type)` à utiliser dans les services
- Job cron `scripts/purge_scheduled_deletions.py` : tourne quotidiennement, purge les comptes `deletion_scheduled_at < now() - 30 days`
- Tests :
  - Export complet : couvre toutes les tables avec `account_id`
  - Suppression programmée : ne purge pas avant 30j, purge après
  - Annulation suppression : supprimer `deletion_scheduled_at`
  - Consent gating : tenter Mobile Money sans consent → 403
  - Anonymisation audit_log : après purge, les rows audit_log existent mais avec `user_id = NULL`, `account_id = NULL`, autre champs intact

### Frontend

- Page `pages/mes-donnees/index.vue` (layout default, auth requis)
- Sous-pages :
  - `pages/mes-donnees/inventaire.vue`
  - `pages/mes-donnees/consentements.vue`
  - `pages/mes-donnees/supprimer.vue`
- Page `pages/legal/privacy.vue` (layout public, no-auth — créé par F08 ou ici)
- Composant `<ConsentToggle :type="..." :granted="..." />`
- Composant `<DeletionConfirmModal />` avec triple confirmation
- Composable `composables/useDataPrivacy.ts`
- Store `stores/consents.ts`
- Footer global avec lien `/legal/privacy`
- Modification `pages/register.vue` : checkbox obligatoire "J'accepte la politique"
- Dark mode
- Accessibilité (focus trap modal, aria-live sur status)

### Base de données

- Tables : `consents`
- Colonnes : `accounts.deletion_scheduled_at`, `accounts.deleted_at`
- Index : `consents(account_id, consent_type, revoked_at)`, `accounts(deletion_scheduled_at) WHERE deletion_scheduled_at IS NOT NULL`
- Trigger : pas de double consent actif simultané pour le même type sur un account

## Critères d'acceptation

- [ ] Page `/mes-donnees` accessible et fonctionnelle (inventaire + export + consentements + suppression)
- [ ] Endpoint `GET /api/me/data/export?format=json` génère un export complet incluant toutes les tables `account_id` + URLs signées des fichiers
- [ ] Modèle `Consent` créé avec 7 types initiaux
- [ ] Helper `require_consent` intégré dans les services dépendant (au minimum stub pour F18)
- [ ] Politique de confidentialité publiée à `/legal/privacy`, accessible sans auth
- [ ] Email `privacy@esg-mefali.com` documenté (DNS / forwarding selon infra)
- [ ] Inscription : checkbox politique obligatoire (refus = pas d'inscription)
- [ ] Suppression de compte : J+30 grâce, email confirmation, cron purge effectif
- [ ] Test E2E : créer compte → exporter → recevoir un JSON valide non vide
- [ ] Test E2E : programmer suppression → annuler → vérifier compte intact
- [ ] Test E2E : programmer suppression → simuler J+30 → vérifier purge effective + audit log anonymisé
- [ ] Test consent gating : tenter une analyse Mobile Money sans consent → 403
- [ ] Couverture tests ≥ 80 %
- [ ] Documentation `docs/rgpd-conformite.md` : checklist de conformité, process exercice droits, contacts
- [ ] Documentation `docs/hosting-and-data-residency.md` : provider, région, chiffrement, sous-traitants

## Risques & garde-fous

- **Risque** : l'export JSON contient des fichiers volumineux (documents PDF de 5 MB × 100 = 500 MB). **Garde-fou** : générer asynchrone, lien temporaire signé 7j, notification email quand prêt, taille max alertée à 1 GB.
- **Risque** : suppression de compte casse des candidatures soumises chez un intermédiaire (qui détient encore le dossier). **Garde-fou** : avant purge, marquer les candidatures `account_deleted` mais conserver le snapshot pour preuve (avec anonymisation `user_id`). Documenter dans la politique : "vos données soumises chez l'intermédiaire restent chez lui — ESG Mefali ne contrôle plus".
- **Risque** : un user qui révoque un consent post-soumission casse l'attestation déjà générée. **Garde-fou** : la révocation s'applique aux **futurs** traitements, les outputs déjà générés (PDF, dossier) restent dans leur état (sauf demande explicite via attestation revoke).
- **Risque** : un developer ajoute un nouveau traitement sans `require_consent`. **Garde-fou** : test CI qui scanne les services et vérifie que toute fonction `analyze_*`, `fetch_*_external` invoque `require_consent`.
- **Risque** : la politique de confidentialité devient obsolète si l'app évolue. **Garde-fou** : versioning de la politique avec banner "nouvelle version disponible, merci d'accepter".
- **Risque** : RGPD impose une durée de conservation max — actuellement aucune n'est définie. **Garde-fou** : documenter par catégorie (profil : tant que compte actif, audit log : 6 ans, attestations : durée de validité, conversations : 24 mois post-inactivité), implémenter post-MVP les purges automatiques.
