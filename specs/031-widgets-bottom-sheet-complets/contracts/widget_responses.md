# Contract — `response_payload jsonb` BDD par variante

**Date** : 2026-05-07
**Phase** : 1

Forme exacte du `response_payload` jsonb stocké dans `interactive_questions.response_payload` pour chaque variante. Validé via les schémas Pydantic `*Response` discriminés (cf. `data-model.md`).

## yes_no

```json
{
  "question_type": "yes_no",
  "value": true,
  "label": "Oui, supprimer"
}
```

## select

```json
{
  "question_type": "select",
  "selected": [
    {"id": "ci", "label": "Côte d'Ivoire", "group": "UEMOA"}
  ],
  "other_value": null
}
```

Multi-sélection :
```json
{
  "question_type": "select",
  "selected": [
    {"id": "ci", "label": "Côte d'Ivoire"},
    {"id": "sn", "label": "Sénégal"},
    {"id": "ml", "label": "Mali"}
  ],
  "other_value": null
}
```

Avec "Autre" :
```json
{
  "question_type": "select",
  "selected": [{"id": "other", "label": "Autre"}],
  "other_value": "Tchad"
}
```

## number

```json
{
  "question_type": "number",
  "value": 1200000.0,
  "currency": "XOF",
  "formatted": "1 200 000 FCFA"
}
```

## date

```json
{
  "question_type": "date",
  "value": "2026-03-15",
  "label": "15 mars 2026"
}
```

## date_range

```json
{
  "question_type": "date_range",
  "from": "2026-01-01",
  "to": "2026-12-31",
  "label": "Du 1 janvier au 31 décembre 2026"
}
```

(Note : sérialisation utilise les alias `from`/`to` au lieu de `from_date`/`to_date` Python.)

## rating

```json
{
  "question_type": "rating",
  "value": 4,
  "scale": 5,
  "label": "Très bien"
}
```

## file_upload

```json
{
  "question_type": "file_upload",
  "documents": [
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "statuts.pdf",
      "size": 524288,
      "mime_type": "application/pdf"
    }
  ]
}
```

## form

```json
{
  "question_type": "form",
  "values": {
    "project_name": "Panneaux solaires PME",
    "description": "Installation de 50 panneaux photovoltaïques sur le toit de l'usine.",
    "target_amount": 5000000.0,
    "sector": "energy",
    "duration_months": 24,
    "start_date": "2026-09-01"
  },
  "summary_label": "Projet créé : Panneaux solaires PME, 5 000 000 FCFA, énergie"
}
```

## summary_card

Validation sans modifications :
```json
{
  "question_type": "summary_card",
  "validated": true,
  "modifications": []
}
```

Validation avec corrections :
```json
{
  "question_type": "summary_card",
  "validated": true,
  "modifications": [
    {
      "field": "Capital social",
      "before": "5 000 000 FCFA",
      "after": "6 000 000 FCFA"
    }
  ]
}
```

## Message texte affiché dans le fil (canonique)

| Variante | Format texte |
|---|---|
| yes_no (true) | `✓ Oui` ou `✓ <confirm_label>` (ex : `✓ Oui, supprimer`) |
| yes_no (false) | `✗ Non` ou `✗ <deny_label>` |
| select mono | `✓ Côte d'Ivoire` |
| select multi | `✓ Côte d'Ivoire, Sénégal, Mali` |
| select other | `✓ Autre : Tchad` |
| number | `✓ 1 200 000 FCFA` |
| date | `✓ 15 mars 2026` |
| date_range | `✓ Du 1 janvier au 31 décembre 2026` |
| rating | `✓ 4/5 (Très bien)` |
| file_upload (1) | `✓ statuts.pdf (uploaded)` |
| file_upload (multi) | `✓ statuts.pdf, business_plan.pdf (2 fichiers uploaded)` |
| form | `✓ Projet créé : Panneaux solaires PME, 5 000 000 FCFA, énergie` |
| summary_card validé | `✓ Validé` |
| summary_card corrigé | `✓ Corrigé : Capital social 6 000 000 FCFA (au lieu de 5 000 000 FCFA)` |

Le payload structuré (response_payload) est conservé en métadonnée du message côté `messages` (champ `interactive_question_response_payload` à raccrocher en Phase B sur le schéma `Message` existant).
