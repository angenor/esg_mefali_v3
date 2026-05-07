# Contract — Tools LangChain Projects (F06)

**Module** : `backend/app/graph/tools/project_tools.py`
**Pattern** : 7 tools async décorés `@tool` avec `args_schema` Pydantic v2
**Source of change** : `'llm'` (via `source_of_change_scope` F03)
**Audit log F03** : automatique via mixin `Auditable` sur `Project`

## Convention commune

Tous les tools :
1. Importent `from langchain_core.tools import tool`
2. Lisent `account_id` et `user_id` depuis le `RunnableConfig` (`config["configurable"]`)
3. Appellent le service `app.modules.projects.service` (pas de SQL direct)
4. Retournent un JSON string (`json.dumps(payload, ensure_ascii=False)`)
5. Erreurs encapsulées dans `{"ok": false, "error": "..."}`

## 1. `list_projects`

**Description LangChain** : « Liste tous les projets verts de l'entreprise. Retourne nom, statut, maturité, objectifs environnementaux, montant cible, impact carbone attendu et nombre de candidatures actives. À utiliser pour montrer un récapitulatif ou pour identifier le projet concerné par une candidature. »

**Args schema** :
```python
class ListProjectsArgs(BaseModel):
    status: Annotated[str | None, Field(
        default=None,
        description="Filtrer par statut (draft/seeking_funding/funded/in_execution/closed/cancelled)"
    )] = None
    maturity: Annotated[str | None, Field(
        default=None,
        description="Filtrer par maturité (ideation/pre_feasibility/pilot/scale/replication)"
    )] = None
```

**Return** : `list[ProjectSummary]` (sérialisé JSON)

**Exemple invocation LLM** :
```json
{
  "tool": "list_projects",
  "args": {"status": "seeking_funding"}
}
```

**Exemple retour** :
```json
[
  {
    "id": "00000000-0000-0000-0000-000000000001",
    "name": "Panneaux solaires usine principale",
    "status": "seeking_funding",
    "maturity": "pilot",
    "objective_env": ["renewable_energy", "mitigation"],
    "target_amount": {"amount": "50000000", "currency": "XOF"},
    "expected_impact_tco2e": "120.0000",
    "auto_generated": false,
    "applications_count": 2,
    "created_at": "2026-05-07T10:30:00Z"
  }
]
```

## 2. `get_project`

**Description** : « Récupère le détail complet d'un projet par son ID, y compris la liste des documents associés et le compteur de candidatures actives. »

**Args schema** :
```python
class GetProjectArgs(BaseModel):
    project_id: Annotated[uuid.UUID, Field(description="UUID du projet à récupérer")]
```

**Return** : `ProjectDetail` (JSON)

**Erreurs** :
- `{"ok": false, "error": "Project not found"}` si l'ID n'existe pas (ou est masqué par RLS).

## 3. `create_project`

**Description** : « Crée un nouveau projet vert pour l'entreprise. Utilisé quand l'utilisateur décrit une initiative qu'il souhaite financer. AVANT d'appeler ce tool avec un montant cible (target_amount) ou un impact carbone attendu (expected_impact_tco2e), tu DOIS appeler `cite_source(source_id)` pour citer la référence du chiffre, OU appeler `flag_unsourced(reason)` si tu cites un chiffre fourni par l'utilisateur sans source externe (reason='user_input'). Le projet est créé avec source_of_change='llm' dans l'audit log. »

**Args schema** :
```python
class ProjectCreateArgs(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200, description="Nom du projet")]
    description: Annotated[str | None, Field(default=None, description="Description détaillée")]
    objective_env: Annotated[list[str], Field(
        default_factory=list,
        description="Objectifs environnementaux : mitigation/adaptation/biodiversity/circular_economy/water/renewable_energy/sustainable_agriculture/mixed"
    )]
    maturity: Annotated[str | None, Field(
        default=None,
        description="ideation/pre_feasibility/pilot/scale/replication"
    )]
    status: Annotated[str, Field(
        default="draft",
        description="draft/seeking_funding/funded/in_execution/closed/cancelled"
    )]
    target_amount_amount: Annotated[Decimal | None, Field(default=None, ge=0)] = None
    target_amount_currency: Annotated[str | None, Field(
        default=None,
        description="Devise XOF/EUR/USD/GBP/JPY"
    )] = None
    duration_months: Annotated[int | None, Field(default=None, gt=0)] = None
    financing_structure: Annotated[str | None, Field(
        default=None,
        description="subvention/pret_concessionnel/equity/blending/mixte"
    )] = None
    expected_impact_tco2e: Annotated[Decimal | None, Field(default=None, ge=0)] = None
    expected_jobs_created: Annotated[int | None, Field(default=None, ge=0)] = None
    expected_beneficiaries: Annotated[int | None, Field(default=None, ge=0)] = None
    expected_hectares_restored: Annotated[Decimal | None, Field(default=None, ge=0)] = None
    location_country: Annotated[str | None, Field(default=None, min_length=2, max_length=2)] = None
    location_region: Annotated[str | None, Field(default=None, max_length=100)] = None

    @model_validator(mode='after')
    def validate_target_amount_pair(self):
        amt = self.target_amount_amount
        cur = self.target_amount_currency
        if (amt is None) != (cur is None):
            raise ValueError(
                "target_amount_amount et target_amount_currency doivent "
                "être tous deux fournis OU tous deux absents"
            )
        return self
```

**Return** : `ProjectDetail` (JSON)

**Audit log** : `action='create' source_of_change='llm' actor_metadata={'tool_name': 'create_project', 'conversation_id': '...'}`.

**Validator F01** : si `target_amount_amount` ou `expected_impact_tco2e` non null sans `cite_source`/`flag_unsourced` invoqué dans le tour, `source_required.py` déclenche un retry max 1 puis fallback texte.

## 4. `update_project`

**Description** : « Met à jour les champs d'un projet existant. Tu peux modifier n'importe quel champ sauf id, account_id, auto_generated, created_at. Pour ajouter ou retirer des objectifs environnementaux, fournis le tableau `objective_env` complet. »

**Args schema** :
```python
class UpdateProjectArgs(BaseModel):
    project_id: Annotated[uuid.UUID, Field(description="UUID du projet à mettre à jour")]
    fields: Annotated[dict[str, Any], Field(
        description="Dictionnaire {champ: nouvelle_valeur}. Les champs non fournis ne sont pas modifiés."
    )]
```

**Return** : `ProjectDetail` (JSON)

**Validation** : le service convertit `fields` en `ProjectUpdate` Pydantic ; les champs inconnus sont rejetés.

## 5. `delete_project`

**Description** : « Supprime (soft-delete : statut passe à 'cancelled') un projet. Si le projet a des candidatures actives (status NOT IN rejected/accepted/cancelled), le tool refuse par défaut et retourne la liste des candidatures bloquantes. Tu peux alors appeler `ask_interactive_question` pour demander confirmation à l'utilisateur, puis re-appeler `delete_project(project_id, force=true)` si l'utilisateur confirme. »

**Args schema** :
```python
class DeleteProjectArgs(BaseModel):
    project_id: Annotated[uuid.UUID, Field(description="UUID du projet à supprimer")]
    force: Annotated[bool, Field(
        default=False,
        description="True pour confirmer malgré les candidatures actives"
    )] = False
```

**Return** : `DeleteResult` (JSON)

**Cas blocage** :
```json
{
  "ok": false,
  "blocked_by": [
    {
      "application_id": "00000000-0000-0000-0000-0000000000cc",
      "fund_name": "Green Climate Fund",
      "status": "submitted_to_fund"
    }
  ],
  "hint": "force=true pour confirmer la suppression (les applications resteront liées)"
}
```

**Cas succès** :
```json
{
  "ok": true,
  "blocked_by": [],
  "hint": null
}
```

**Log structuré** (FR-036) : `INFO project_force_deleted {project_id, account_id, blocked_by_count, user_id}` quand `force=true`.

## 6. `duplicate_project`

**Description** : « Duplique un projet existant. Le nouveau projet hérite de tous les champs métier sauf id, created_at, updated_at, auto_generated et project_documents. Le statut est forcé à 'draft'. Si new_name est absent, le nom source reçoit le suffixe ' (copie)'. »

**Args schema** :
```python
class DuplicateProjectArgs(BaseModel):
    project_id: Annotated[uuid.UUID, Field(description="UUID du projet source à dupliquer")]
    new_name: Annotated[str | None, Field(
        default=None, min_length=1, max_length=200,
        description="Nouveau nom (optionnel)"
    )] = None
```

**Return** : `ProjectDetail` (le nouveau projet, JSON)

**Audit log** : `actor_metadata={'tool_name': 'duplicate_project', 'duplicated_from': '<source_id>'}`.

## 7. `link_document_to_project`

**Description** : « Associe un document existant (déjà uploadé via le module documents) à un projet, en spécifiant le type. Échoue si l'association existe déjà (UNIQUE constraint). »

**Args schema** :
```python
class LinkDocumentArgs(BaseModel):
    project_id: Annotated[uuid.UUID, Field(description="UUID du projet")]
    document_id: Annotated[uuid.UUID, Field(description="UUID du document existant")]
    doc_type: Annotated[str, Field(
        description="feasibility_study/business_plan/impact_assessment/support_letter/other"
    )]
```

**Return** : `ProjectDocumentRead` (JSON)

**Erreurs** :
- `{"ok": false, "error": "Project not found"}` (RLS ou ID invalide)
- `{"ok": false, "error": "Document not found"}`
- `{"ok": false, "error": "Association already exists"}` (UNIQUE constraint)

## Injection dans le tool selector

### `tool_selector_config.py` modifications

```python
# Ajout dans MODULE_TOOL_MAPPING
"chat": frozenset({
    # ... tools existants ...
    "list_projects",  # le LLM peut interroger les projets depuis le chat
}),

# Nouvelles entrées dans PAGE_TOOL_MAPPING
"profile": frozenset({
    "update_company_profile",
    "get_company_profile",
    "get_company_profile_chat",
    # F06 — accès lecture aux projets depuis /profile
    "list_projects",
    "get_project",
}),
"profile_projects": frozenset({
    "list_projects",
    "get_project",
    "create_project",
    "update_project",
    "delete_project",
    "duplicate_project",
    "link_document_to_project",
}),

# Mapping path Nuxt
(re.compile(r"^/profile/projects(?:/|$)"), "profile_projects"),
```

### Borne `MAX_TOOLS_PER_TURN`

Inchangée à `14`. Les 7 tools projet ne sont jamais tous exposés simultanément :
- Sur `chat_global` / nœud `chat` : seul `list_projects` est ajouté (10 tools métier max + 4 globaux F01/F12).
- Sur `/profile/projects` : 7 tools projet exclusifs (pas d'autre tool métier exposé sur cette page).

## Conformité invariants F01/F02/F03/F04

| Invariant | Conformité |
|-----------|------------|
| F01 sourçage | `create_project`/`update_project` vérifient via `source_required.py` si target_amount/expected_impact_tco2e cités. |
| F02 multi-tenant | `account_id` lu depuis `config["configurable"]["account_id"]` ; transmis au service ; RLS PG filtre. |
| F03 audit log | `Project` hérite `Auditable` ; mutation `before_flush` capture automatiquement. |
| F04 Money typed | `target_amount_amount` + `target_amount_currency` validés par `model_validator` Pydantic ; service appelle `Money.from_columns(amt, cur)` pour matérialiser. |

## Tests unitaires & intégration

| Test | Type | Description |
|------|------|------|
| `test_create_project_tool_basic.py` | unit | Mock service, vérifie sérialisation JSON. |
| `test_create_project_with_source.py` | integration | Tool + cite_source = OK, projet créé avec montants. |
| `test_create_project_without_source.py` | integration | Tool sans cite_source ⇒ retry 1x ⇒ fallback ; montants NULL. |
| `test_delete_project_blocked_by_applications.py` | integration | App active ⇒ `ok:false, blocked_by:[...]`. |
| `test_delete_project_force.py` | integration | `force=true` ⇒ status='cancelled' + log INFO. |
| `test_duplicate_project_fields.py` | integration | Duplique ; vérifie copie complète sauf id/status/auto_generated/documents. |
| `test_link_document_unique.py` | integration | Échec UNIQUE sur 2e association. |
| `test_project_tools_audit_log.py` | integration | Tool ⇒ audit_log avec source_of_change='llm', tool_name dans actor_metadata. |
| `test_project_tools_rls.py` | integration | PME-A appelle get_project sur projet PME-B ⇒ 404. |
