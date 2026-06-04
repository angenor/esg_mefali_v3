# Contrat — Sérialisation enrichie de la checklist, progression & nettoyage

Couvre la lecture (détail dossier, liste dossiers, endpoint checklist) et l'effet de bord de la suppression de document. FR-004, FR-005, FR-008, FR-014, FR-017, FR-019, SC-002, SC-004, SC-005.

---

## 1. Détail du dossier — `GET /api/applications/{application_id}`

La réponse `ApplicationResponse` voit :
- chaque élément de `checklist` enrichi en `ChecklistItemOut` (avec `document` et `status` effectif) ;
- un nouveau champ `checklist_progress`.

```json
{
  "id": "...",
  "checklist": [
    {
      "key": "company_registration", "name": "Registre de commerce (RCCM)",
      "status": "provided", "required_by": "fund_direct",
      "document_id": "5c9b...", 
      "document": { "id": "5c9b...", "original_filename": "rccm.pdf", "mime_type": "application/pdf", "status": "uploaded" }
    },
    {
      "key": "esg_report", "name": "Rapport ESG", "status": "missing",
      "required_by": "fund_direct", "document_id": null, "document": null
    }
  ],
  "checklist_progress": { "provided": 1, "total": 2 }
}
```

Règles :
- `status` est **effectif** : un item dont le `document_id` ne résout pas un document valide du compte est renvoyé `status="missing"`, `document=null` (défense en profondeur, D3).
- Chargement **groupé** des documents référencés (pas de N+1).
- `checklist` vide → `checklist_progress = { provided: 0, total: 0 }` ; l'UI affiche « Aucun document requis » (FR-017).

## 2. Liste des dossiers — `GET /api/applications/`

Chaque item de liste reçoit `checklist_progress { provided, total }` (à côté de `sections_progress` existant), pour le badge compact « M/N » de la carte de dossier (FR-008, clarification 2026-06-03).

```json
{
  "applications": [
    { "id": "...", "fund_name": "...", "sections_progress": { "generated": 2, "total": 4 },
      "checklist_progress": { "provided": 3, "total": 5 } }
  ]
}
```

## 3. Endpoint checklist — `GET /api/applications/{application_id}/checklist`

Renvoie la liste enrichie (`ChecklistItemOut[]`) + `checklist_progress`, même logique de statut effectif que (1).

## 4. Suppression de document — effet sur la checklist (FR-014)

`DELETE /api/documents/{document_id}` (endpoint existant) déclenche, en plus de la suppression du fichier et des cascades existantes, le nettoyage : tout item (de tout dossier du **même compte**) référençant ce `document_id` repasse à `document_id=null`, `status="missing"`.

Invariant post-suppression : `GET` de tout dossier concerné montre l'item « missing » (SC-005, 100 %).

## 5. Parité chatbot (FR-019) — `get_application_checklist`

Le tool LLM lit désormais la forme réelle : item « fourni » ⟺ `status == "provided"` ; libellé = `name` ; « requis » dérivé de la présence dans le catalogue (`required_by`). Plus aucune lecture de `provided`/`label`/`required` (clés inexistantes).

## Tests de contrat (à écrire AVANT — TDD)

1. Détail dossier : item « provided » expose `document` (nom de fichier) ; item « missing » expose `document=null`.
2. `checklist_progress` détail = compte exact des items effectivement « provided ».
3. Liste dossiers : chaque dossier porte `checklist_progress` correct.
4. Item avec `document_id` pointant un document supprimé → renvoyé `status="missing"`, `document=null` (statut effectif).
5. Suppression d'un document rattaché à 2 items (2 dossiers) → les 2 items repassent « missing ».
6. Checklist vide → `total=0`, pas d'erreur.
7. `get_application_checklist` (chatbot) compte « fourni » via `status=="provided"` et affiche `name` (mise à jour du mock de test vers la forme réelle).
