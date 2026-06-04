# Contrat API — Rattacher / Remplacer le document d'un item de checklist

**Endpoint** : `PUT /api/applications/{application_id}/checklist/{item_key}/document`
**Auth** : requise (Bearer JWT). Rôle PME propriétaire du dossier.
**Couvre** : US1 (après upload), US2 (document existant), US4 (remplacement). FR-001..FR-004, FR-007, FR-009..FR-011, FR-019.

## Requête

Path :
- `application_id` : UUID du dossier.
- `item_key` : `key` de l'item de checklist (ex. `company_registration`).

Body (JSON) :

```json
{ "document_id": "5c9b1e2a-..." }
```

| Champ | Type | Requis | Règle |
|-------|------|--------|-------|
| `document_id` | UUID | oui | Document existant, appartenant au **même compte** que le dossier. |

## Réponse 200 OK

```json
{
  "success": true,
  "data": {
    "item": {
      "key": "company_registration",
      "name": "Registre de commerce (RCCM)",
      "status": "provided",
      "required_by": "fund_direct",
      "document_id": "5c9b1e2a-...",
      "document": {
        "id": "5c9b1e2a-...",
        "original_filename": "rccm_2026.pdf",
        "mime_type": "application/pdf",
        "status": "uploaded"
      }
    },
    "checklist_progress": { "provided": 3, "total": 5 }
  }
}
```

Comportement : idempotent. Si l'item était déjà « provided », le `document_id` est remplacé (FR-007). Mutation atomique du seul item ciblé.

## Réponses d'erreur

| Code | Cas | Corps (`detail`) |
|------|-----|------------------|
| 400 | `document_id` absent / format invalide | « Identifiant de document invalide. » |
| 401 | Non authentifié | (standard) |
| 403 | Document d'un **autre compte** que le dossier (FR-010, SC-003) | « Ce document n'appartient pas à votre organisation. » |
| 404 | Dossier inexistant / non possédé (FR-018) | « Dossier introuvable. » |
| 404 | `item_key` inexistant dans la checklist (FR-016) | « Élément de checklist introuvable. » |
| 404 | `document_id` inexistant | « Document introuvable. » |

Aucune modification d'état en cas d'erreur (transaction).

## Effets de bord

- Item : `document_id = <body>`, `status = "provided"`.
- Audit : 1 ligne `audit_log` (entity `fund_applications`, field `checklist`, `source_of_change="manual"`).

## Tests de contrat (à écrire AVANT — TDD)

1. Rattachement nominal sur item « missing » → 200, item « provided », `document` peuplé, progression incrémentée.
2. Rattachement sur item déjà « provided » avec un autre document → 200, `document_id` remplacé, progression inchangée.
3. Document d'un autre compte → 403, état inchangé.
4. `item_key` inconnu → 404.
5. `application_id` inconnu / autre utilisateur → 404.
6. `document_id` inconnu → 404.
7. Body sans `document_id` → 400/422.
8. Une ligne d'audit est créée après rattachement.
