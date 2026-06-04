# Contrat API — Détacher le document d'un item de checklist

**Endpoint** : `DELETE /api/applications/{application_id}/checklist/{item_key}/document`
**Auth** : requise (Bearer JWT). Rôle PME propriétaire du dossier.
**Couvre** : US4 (détachement). FR-006, FR-009, FR-013.

## Requête

Path :
- `application_id` : UUID du dossier.
- `item_key` : `key` de l'item de checklist.

Pas de body.

## Réponse 200 OK

```json
{
  "success": true,
  "data": {
    "item": {
      "key": "company_registration",
      "name": "Registre de commerce (RCCM)",
      "status": "missing",
      "required_by": "fund_direct",
      "document_id": null,
      "document": null
    },
    "checklist_progress": { "provided": 2, "total": 5 }
  }
}
```

Comportement : ramène l'item à « missing ». **Ne supprime pas** le document (il reste disponible sur /documents et rattachable ailleurs — FR-011). Mutation atomique du seul item ciblé.

Idempotence : détacher un item déjà « missing » renvoie 200 avec l'item inchangé (`status="missing"`, `document=null`).

## Réponses d'erreur

| Code | Cas | Corps (`detail`) |
|------|-----|------------------|
| 401 | Non authentifié | (standard) |
| 404 | Dossier inexistant / non possédé | « Dossier introuvable. » |
| 404 | `item_key` inexistant | « Élément de checklist introuvable. » |

## Effets de bord

- Item : `document_id = null`, `status = "missing"`.
- Audit : 1 ligne `audit_log` (field `checklist`).

## Tests de contrat (à écrire AVANT — TDD)

1. Détachement nominal d'un item « provided » → 200, item « missing », `document=null`, progression décrémentée.
2. Détachement d'un item déjà « missing » → 200 idempotent.
3. Le document détaché **existe toujours** (non supprimé) et reste rattachable à un autre item.
4. `item_key` inconnu → 404.
5. `application_id` inconnu / autre utilisateur → 404.
6. Une ligne d'audit est créée après détachement.
