# Contract — `payload jsonb` BDD par variante

**Date** : 2026-05-07
**Phase** : 1

Forme exacte du `payload` jsonb stocké dans `interactive_questions.payload` pour chaque variante. Le contenu est validé via les schémas Pydantic discriminés (cf. `data-model.md`).

## yes_no

```json
{
  "question_type": "yes_no",
  "confirm_label": "Oui, supprimer",
  "deny_label": "Non, annuler",
  "destructive": true
}
```

## select

```json
{
  "question_type": "select",
  "options": [
    {"id": "ci", "label": "Côte d'Ivoire", "sublabel": "République de Côte d'Ivoire", "group": "UEMOA"},
    {"id": "sn", "label": "Sénégal", "group": "UEMOA"},
    {"id": "ml", "label": "Mali", "group": "UEMOA"},
    {"id": "ng", "label": "Nigeria", "group": "CEDEAO non-UEMOA"}
  ],
  "min_selections": 1,
  "max_selections": 1,
  "allow_other": false
}
```

## number

```json
{
  "question_type": "number",
  "unit": "FCFA",
  "min": 0,
  "max": 1000000000000,
  "step": 1000,
  "currency": "XOF",
  "default": null
}
```

## date

```json
{
  "question_type": "date",
  "min": "2026-05-07",
  "max": "2027-12-31",
  "default": null
}
```

## date_range

```json
{
  "question_type": "date_range",
  "min": "2026-01-01",
  "max": "2026-12-31"
}
```

## rating

```json
{
  "question_type": "rating",
  "scale": 5,
  "labels": ["Très mauvais", "Mauvais", "Moyen", "Très bien", "Excellent"]
}
```

## file_upload

```json
{
  "question_type": "file_upload",
  "accept": [".pdf", ".docx", ".xlsx"],
  "max_size_mb": 10,
  "multi": false,
  "doc_type_hint": "business_plan"
}
```

## form

```json
{
  "question_type": "form",
  "title": "Création de projet vert",
  "fields": [
    {
      "name": "project_name",
      "label": "Nom du projet",
      "type": "text",
      "required": true,
      "placeholder": "Ex : Panneaux solaires PME",
      "validation": {"min_length": 5, "max_length": 200}
    },
    {
      "name": "description",
      "label": "Description",
      "type": "textarea",
      "required": true,
      "validation": {"max_length": 2000}
    },
    {
      "name": "target_amount",
      "label": "Montant cible",
      "type": "money",
      "required": true,
      "validation": {"min": 1000000, "max": 1000000000}
    },
    {
      "name": "sector",
      "label": "Secteur",
      "type": "select",
      "required": true,
      "validation": {
        "options": [
          {"id": "energy", "label": "Énergie"},
          {"id": "agri", "label": "Agriculture"}
        ]
      }
    },
    {
      "name": "duration_months",
      "label": "Durée (mois)",
      "type": "number",
      "required": true,
      "validation": {"min": 6, "max": 60}
    },
    {
      "name": "start_date",
      "label": "Date de démarrage",
      "type": "date",
      "required": false,
      "default": null
    }
  ],
  "submit_label": "Créer le projet"
}
```

## summary_card

```json
{
  "question_type": "summary_card",
  "title": "Voici ce qu'on a extrait de votre Statuts.pdf",
  "items": [
    {"label": "Forme juridique", "value": "SARL", "editable": true},
    {"label": "Capital social", "value": "5 000 000 FCFA", "editable": true},
    {"label": "Effectif", "value": 12, "editable": true},
    {"label": "Date de création", "value": "2018-03-15", "editable": false}
  ],
  "confirm_label": "Valider",
  "correct_label": "Corriger"
}
```

## Validation côté serveur (Pydantic union discriminée)

```python
def validate_payload(question_type: str, payload: dict) -> InteractiveQuestionPayload:
    """Valide le payload selon le type. Lève ValidationError si non conforme."""
    payload_with_type = {**payload, "question_type": question_type}
    return InteractiveQuestionPayloadAdapter.validate_python(payload_with_type)
```

## Hard limits (rappel)

- `select.options` : ≤ 200
- `form.fields` : ≤ 10
- `file_upload.max_size_mb` : ≤ 10
- `summary_card.items` : ≤ 20
- `rating.scale` : ∈ [2, 10]
- `rating.labels` : len = scale si fourni
- `prompt` (texte de la question) : ≤ 500 caractères (hérité F18)
