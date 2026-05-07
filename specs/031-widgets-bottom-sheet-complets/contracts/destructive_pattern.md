# Contract — Pattern Destructif (Module 1.1.3)

**Date** : 2026-05-07
**Phase** : 1

## Principe

Aucun tool de mutation destructif (`delete_*`, `revoke_*`, `cancel_*`) ne DOIT pouvoir s'exécuter sans une étape de confirmation utilisateur explicite via `ask_yes_no(destructive=True)`. Le pattern repose sur une signature commune `confirm: bool = False` et un retour conditionnel.

## Signature uniforme

Tous les tools destructifs DOIVENT accepter un paramètre `confirm: bool = False` :

```python
class DeleteProjectArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    confirm: bool = False

@tool(args_schema=DeleteProjectArgs)
async def delete_project(
    project_id: UUID,
    confirm: bool = False,
    config: RunnableConfig = None,
) -> str:
    """Supprime un projet (action destructive irréversible).

    PATTERN OBLIGATOIRE :
    - Premier appel sans confirmation : confirm=False, retourne requires_confirmation.
    - Seul le tool ask_yes_no(destructive=True) doit être invoqué entre les deux.
    - Second appel avec confirmation : confirm=True, exécute la suppression.
    """
    if not confirm:
        return requires_destructive_confirmation("delete_project")

    # Sinon : suppression effective
    db, user_id = get_db_and_user(config)
    project = await db.get(Project, project_id)
    if not project:
        return "Erreur : projet introuvable."

    # Vérifier les permissions multi-tenant (F02)
    if project.account_id != _account_id_from_config(config):
        return "Erreur : accès refusé."

    # Audit log F03 (avant suppression pour capter les valeurs)
    await audit_log_service.log(
        action="delete_project",
        actor_user_id=user_id,
        target_type="project",
        target_id=project_id,
        before=project.to_dict(),
        after=None,
        metadata={"confirm": True, "required_confirmation": True},
    )

    await db.delete(project)
    await db.commit()
    return f"Projet '{project.name}' supprimé avec succès."
```

## Helper `requires_destructive_confirmation`

Localisation : `backend/app/graph/tools/common.py`.

```python
import json

DESTRUCTIVE_ACTIONS = {
    "delete_project",
    "delete_application",
    "delete_assessment",
    "delete_carbon_assessment",
    "revoke_attestation",
    "cancel_application",
    # à compléter au fur et à mesure
}


def requires_destructive_confirmation(action_name: str) -> str:
    """Retourne le marker JSON destiné au LLM pour déclencher ask_yes_no.

    Le LLM, en voyant ce retour, doit invoquer immédiatement
    ask_yes_no(destructive=True) pour solliciter une confirmation
    utilisateur explicite.
    """
    if action_name not in DESTRUCTIVE_ACTIONS:
        # Garde-fou : ne marque comme destructif que les actions enregistrées
        raise ValueError(
            f"'{action_name}' n'est pas dans la liste des actions destructives. "
            f"Ajoutez-la à DESTRUCTIVE_ACTIONS si elle l'est réellement."
        )

    return json.dumps({
        "requires_confirmation": True,
        "message": (
            f"Action destructive '{action_name}' nécessite une confirmation utilisateur. "
            "Invoque immédiatement ask_yes_no(destructive=True, question='...') "
            "puis re-appelle ce tool avec confirm=True si l'utilisateur confirme."
        ),
        "destructive_action": action_name,
    })
```

## Instruction LLM (WIDGET_INSTRUCTION étendue)

Section ajoutée à `backend/app/prompts/_widget_instruction.py` :

```
RÈGLE D'OR : ACTIONS DESTRUCTIVES

Si tu invoques un tool de suppression ou modification irréversible (delete_project,
delete_application, revoke_attestation, cancel_application, etc.) et qu'il retourne
un JSON avec "requires_confirmation": true :

1. NE RE-APPELLE PAS le tool destructif tout de suite.
2. Invoque IMMÉDIATEMENT ask_yes_no(question="<question naturelle>", destructive=True).
3. Quand l'utilisateur répond :
   - Si "Oui" : re-appelle le tool destructif initial avec confirm=True.
   - Si "Non" ou abandon : informe l'utilisateur que l'action a été annulée.

EXEMPLE :
- User : "supprime mon projet 'Panneaux solaires'"
- Tu : delete_project(project_id="abc-123")
- Tool : {"requires_confirmation": true, "destructive_action": "delete_project", ...}
- Tu : ask_yes_no(question="Êtes-vous certain de vouloir supprimer définitivement le projet 'Panneaux solaires' ?", destructive=True, confirm_label="Oui, supprimer", deny_label="Non, annuler")
- User : "✓ Oui, supprimer"
- Tu : delete_project(project_id="abc-123", confirm=True)
- Tool : "Projet 'Panneaux solaires' supprimé avec succès."

NE JAMAIS APPELER UN TOOL DESTRUCTIF AVEC confirm=True SANS PASSER PAR ask_yes_no D'ABORD.
```

## Audit log F03

Chaque mutation destructive DOIT créer une entrée dans `audit_log` :

| Colonne | Valeur |
|---|---|
| account_id | account_id de la conversation |
| actor_user_id | user_id du caller |
| action | nom du tool (ex : `delete_project`) |
| target_type | type de l'entité (ex : `project`) |
| target_id | id de l'entité |
| before | snapshot JSON avant suppression (jsonb) |
| after | NULL (suppression) |
| metadata | `{"confirm": True, "required_confirmation": True}` (jsonb) |
| created_at | now() |

L'audit_log permet de tracer post-mortem que l'utilisateur a bien confirmé.

## Tests obligatoires

`backend/tests/unit/graph/tools/test_destructive_pattern.py` :

1. **test_delete_project_without_confirm_returns_requires_confirmation** : appel `delete_project(project_id, confirm=False)` retourne le JSON marker, aucune mutation BDD.
2. **test_delete_project_with_confirm_executes** : appel `delete_project(project_id, confirm=True)` exécute la suppression effective + crée audit_log.
3. **test_helper_rejects_unregistered_action** : `requires_destructive_confirmation("not_a_destructive_action")` lève `ValueError`.
4. **test_marker_format** : le JSON retourné contient `requires_confirmation`, `message`, `destructive_action`.

`backend/tests/integration/test_widget_e2e_yes_no_destructive.py` :

5. **test_full_flow_delete_with_confirmation** :
   - Insert un projet
   - Appel `delete_project(confirm=False)` → retourne marker
   - Appel `ask_yes_no(destructive=True)` → crée question pending
   - Simule réponse user true → state=answered
   - Re-appel `delete_project(confirm=True)` → projet supprimé
   - Vérifie audit_log : 1 entrée avec `metadata.confirm=True`.

## Tools destructifs initiaux (Phase B)

Si certains tools n'existent pas encore (modules pas livrés), F10 crée des stubs :

| Tool | Module cible | Stub ou existant ? |
|---|---|---|
| `delete_project` | F25 (projet vert) | Stub à créer dans F10 (raccrocher en F25) |
| `delete_application` | F09 (fund_applications) | Existant, à étendre avec `confirm` |
| `delete_carbon_assessment` | F07 (carbon) | Existant, à étendre avec `confirm` |
| `delete_esg_assessment` | F05 (esg_scoring) | Existant, à étendre avec `confirm` |
| `revoke_attestation` | F26 (attestation) | Stub à créer dans F10 (raccrocher en F26) |
| `cancel_application` | F09 | Existant, à étendre avec `confirm` |

Pour les stubs : retournent `requires_destructive_confirmation(...)` si confirm=False, sinon retournent `"Stub : action 'xxx' non implémentée, raccrochez à F25/F26."` — utile pour valider le pattern et les tests E2E avant la livraison du module concret.
