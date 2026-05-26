# Contract — Création de dossier : parité chat/UI, dédup, document réel (D3, D4, D5)

**Fichiers** : `backend/app/modules/applications/{schemas.py,service.py,router.py,export.py}`, `backend/app/graph/tools/application_tools.py`

## 1. Schéma `ApplicationCreate` (étendu)

```
ApplicationCreate {
  fund_id: UUID            # conservé (legacy)
  offer_id: UUID | None    # NOUVEAU — prioritaire si fourni (résout fund/intermediary)
  project_id: UUID | None  # NOUVEAU — rattachement projet
  match_id: UUID | None     # conservé
  intermediary_id: UUID|None# conservé
}
```
Validation : si `offer_id` fourni, `fund_id`/`intermediary_id` sont dérivés de l'offre.

## 2. Service `create_application(...)` (étendu + dédup)
- Accepte `offer_id`/`project_id` ; si `offer_id` → charge `Offer`, pose `fund_id`, `intermediary_id`, `offer_id`.
- **Dédup (FR-006)** : si un dossier `draft` existe pour `(user_id, project_id, offer_id)`, le **retourner** (pas de doublon). Sinon créer.
- Reste source unique appelée par le tool chat **et** l'endpoint REST (FR-016).

## 3. Endpoint REST `POST /api/applications/`
- Body `ApplicationCreate` étendu. Réponses : `201` (créé) / `200` réutilisé OU `201` idempotent documenté, `404` offre/fonds introuvable, `403` cross-account, `422` contexte invalide.
- RLS F02 + audit F03 (création dossier) conservés.

## 4. Tool chat `create_fund_application`
- Refactor pour appeler le **service partagé** (au lieu de l'assignation directe `offer_id`/`project_id` post-create). Comportement externe inchangé pour le LLM.

## 5. Tool chat `export_application` (D3 — document réel)
- Remplacer le stub `_export_application` par un appel au vrai `applications/export.py::export_application(application, format)`.
- Écrire les bytes sous `/uploads/applications/{id}.{format}` ; **enregistrer un `Document`** utilisateur (visible `/documents`).
- Retour LLM : URL réelle téléchargeable + nom de fichier. Défaut format : `docx`.

## 6. Gating ESG (D4) avant génération
- Avant production du document, vérifier la couverture des critères `is_required` du référentiel de l'offre via l'évaluation ESG-projet du `project_id`.
- Si manquants → **ne pas générer** ; retourner `{ok:false, blocked:true, missing_criteria:[...], message:"Complétez d'abord…"}`. Le LLM guide l'utilisateur (FR-003b).

## Cas de test (TDD)
| # | Niveau | Scénario | Attendu |
|---|--------|----------|---------|
| T1 | unit/service | create avec `offer_id` | fund/intermediary dérivés, offer lié |
| T2 | unit/service | 2e create même (user,project,offer) draft | même dossier retourné (dédup) |
| T3 | integration | `POST /applications` body offer_id+project_id | 201, dossier lié au projet |
| T4 | integration | offer_id inexistant | 404 |
| T5 | integration | dossier d'un autre compte | 403 |
| T6 | unit | export_application tool | fichier écrit + Document enregistré + URL réelle |
| T7 | unit | gating ESG incomplet | `blocked:true`, pas de fichier |
| T8 | unit | gating ESG complet | document généré |
| T9 | parité | tool chat vs endpoint | dossiers équivalents (mêmes champs liés) |
