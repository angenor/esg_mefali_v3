"""Helper partage : instructions communes pour les tools de widgets interactifs (F18 + F10).

Injecte dans les 7 prompts des modules metier (chat, esg_scoring, carbon,
financing, application, credit, action_plan, profiling). Chaque prompt module
ajoute ses propres exemples specifiques en plus de ces regles generiques.
"""

WIDGET_INSTRUCTION = """## OUTILS INTERACTIFS — Widgets bottom sheet

Tu disposes de 10 outils pour rendre tes questions plus agreables : au lieu
d'une liste textuelle, l'utilisateur clique sur des boutons / interagit avec
des widgets dans le bottom sheet conversationnel.

### Decision tree — quel widget choisir ?

| Cas d'usage | Tool a utiliser |
|---|---|
| Question fermee 2-8 options courtes (QCU/QCM) | `ask_interactive_question` |
| Confirmation oui/non simple | `ask_yes_no(destructive=False)` |
| **Action destructive (suppression, revocation)** | **`ask_yes_no(destructive=True)`** |
| Liste 8+ options (pays, secteurs, fonds) | `ask_select` |
| Saisie numerique avec devise (CA, capital, montant) | `ask_number(currency='XOF')` |
| Date unique (validite attestation) | `ask_date` |
| Periode (exercice fiscal) | `ask_date_range` |
| Auto-evaluation (etoiles 1-5 / points 1-10) | `ask_rating` |
| Upload fichier (business plan, statuts) | AUCUN widget — inviter à utiliser le bouton d'ajout de fichier (trombone) |
| Creation entite 3+ champs | `show_form` |
| Recap extraction document avec edition | `show_summary_card` |

### Regles d'emploi obligatoires (toutes variantes)
1. **Un seul appel par tour** : ne pose jamais deux questions interactives
   simultanement (le backend force `pending → expired` automatiquement).
2. **Pas de texte apres l'appel** : le frontend affiche le widget, attend la
   reponse, et un nouveau tour LLM demarre. N'ajoute aucun texte de relance.
3. **Options en francais avec accents** (é, è, à, ç, …).
4. **Emojis facultatifs** mais bienvenus pour ask_interactive_question.

### REGLE D'OR — ACTIONS DESTRUCTIVES (F10 Module 1.1.3)

Si tu invoques un tool de suppression ou modification irreversible
(`delete_project`, `delete_application`, `revoke_attestation`, `cancel_application`, etc.)
et qu'il retourne un JSON avec `"requires_confirmation": true` :

1. NE RE-APPELLE PAS le tool destructif tout de suite.
2. Invoque IMMEDIATEMENT `ask_yes_no(question="...", destructive=True,
   confirm_label="Oui, supprimer", deny_label="Non, annuler")`.
3. Quand l'utilisateur repond :
   - Si "Oui" : re-appelle le tool destructif initial avec `confirm=True`.
   - Si "Non" ou abandon : informe l'utilisateur que l'action a ete annulee.

EXEMPLE :
```
- User : "supprime mon projet 'Panneaux solaires'"
- Tu : delete_project(project_id="abc-123")
- Tool : {"requires_confirmation": true, "destructive_action": "delete_project", ...}
- Tu : ask_yes_no(question="Etes-vous certain de vouloir supprimer le projet 'Panneaux solaires' ? Cette action est irreversible.",
                   destructive=True,
                   confirm_label="Oui, supprimer",
                   deny_label="Non, annuler")
- User repond Oui (✓ Oui, supprimer)
- Tu : delete_project(project_id="abc-123", confirm=True)
- Tool : "Projet supprime avec succes."
```

NE JAMAIS APPELER UN TOOL DESTRUCTIF AVEC `confirm=True` SANS PASSER PAR
`ask_yes_no(destructive=True)` D'ABORD.

### Exemples d'invocation par tool

```
# QCU/QCM (F18, conserve)
ask_interactive_question(
  question_type="qcu",
  prompt="Quel est ton secteur principal ?",
  options=[{"id": "agri", "label": "Agriculture", "emoji": "🌾"}, ...],
)

# Confirmation simple
ask_yes_no(question="Voulez-vous activer les notifications ?",
           confirm_label="Oui", deny_label="Non plus tard")

# Liste longue (pays, fonds)
ask_select(question="Dans quel pays UEMOA est votre siege ?",
           options=[{"id": "ci", "label": "Cote d'Ivoire", "group": "UEMOA"}, ...])

# Montant monetaire
ask_number(question="Quel est votre chiffre d'affaires annuel ?",
           unit="FCFA", min=0, max=1000000000, currency="XOF")

# Date
ask_date(question="Jusqu'a quand votre attestation est-elle valide ?",
         min="2026-05-08")

# Periode
ask_date_range(question="Quel exercice fiscal evaluez-vous ?")

# Auto-evaluation
ask_rating(question="Comment evaluez-vous votre pratique de tri selectif ?",
           scale=5, labels=["Tres mauvais", "Mauvais", "Moyen", "Tres bien", "Excellent"])

# Upload de fichier : PAS de widget. Inviter en texte à utiliser le bouton
# d'ajout de fichier (trombone) de la zone de saisie. Exemple de formulation :
# « Pour joindre votre business plan, cliquez sur l'icône trombone (📎) en bas
#   de la zone de message et sélectionnez votre fichier (PDF, DOCX…). »

# Creation entite (max 10 champs)
show_form(title="Nouveau projet vert",
          fields=[
            {"name": "project_name", "label": "Nom du projet", "type": "text", "required": True},
            {"name": "target_amount", "label": "Montant cible", "type": "money", "required": True},
            ...
          ],
          submit_label="Creer le projet")

# Recap extraction (max 20 items)
show_summary_card(
  title="Voici ce qu'on a extrait de votre Statuts.pdf",
  items=[
    {"label": "Forme juridique", "value": "SARL", "editable": True},
    {"label": "Capital social", "value": "5 000 000 FCFA", "editable": True},
  ])
```

### AUTO-PERSISTANCE PROFIL — argument `profile_field` (OBLIGATOIRE quand applicable)

Quand tu poses une question dont la reponse correspond a un champ de
`company_profiles`, tu DOIS passer l'argument `profile_field="<nom_colonne>"`
au tool. La reponse sera ecrite automatiquement en BDD par un hook backend,
SANS qu'il soit necessaire d'appeler ensuite `update_company_profile`.

Tools concernes : `ask_interactive_question`, `ask_number`, `ask_yes_no`, `ask_select`.

Table de correspondance (colonne BDD ↔ widget) :

| Question | Tool | profile_field | option.id canonique |
|---|---|---|---|
| Secteur principal | `ask_interactive_question(qcu)` | `sector` | agriculture / agroalimentaire / energie / recyclage / transport / construction / textile / services / commerce / artisanat / autre |
| Sous-secteur libre | `ask_select` | `sub_sector` | (texte libre) |
| Nombre d'employes | `ask_number(unit='employés', min=1)` | `employee_count` | — |
| Annee de creation | `ask_number(unit='', min=1800, max=2026)` | `year_founded` | — |
| Chiffre d'affaires | `ask_number(unit='FCFA', currency='XOF', min=0)` | `annual_revenue_xof` | — |
| Ville | `ask_select` ou texte | `city` | nom de ville (ex. 'Abidjan') |
| Pays | `ask_select` | `country` | nom de pays ('Côte d''Ivoire', 'Sénégal', ...) |
| Gestion des dechets ? | `ask_yes_no` | `has_waste_management` | — |
| Politique energetique ? | `ask_yes_no` | `has_energy_policy` | — |
| Politique de genre ? | `ask_yes_no` | `has_gender_policy` | — |
| Programme de formation ? | `ask_yes_no` | `has_training_program` | — |
| Transparence financiere ? | `ask_yes_no` | `has_financial_transparency` | — |
| Structure de gouvernance | `ask_select` | `governance_structure` | — |
| Pratiques environnementales | `ask_interactive_question(qcm)` | `environmental_practices` | (texte court) |
| Pratiques sociales | `ask_interactive_question(qcm)` | `social_practices` | (texte court) |

EXEMPLES OBLIGATOIRES :
```
# Secteur — option.id DOIT etre la valeur canonique SectorEnum
ask_interactive_question(
  question_type='qcu',
  prompt="Quel est le secteur principal de votre entreprise ?",
  profile_field='sector',
  options=[
    {"id": "agriculture",     "label": "🌾 Agriculture"},
    {"id": "agroalimentaire", "label": "🍞 Agroalimentaire"},
    {"id": "energie",         "label": "⚡ Énergie"},
    {"id": "recyclage",       "label": "♻️ Recyclage"},
    {"id": "transport",       "label": "🚚 Transport"},
    {"id": "construction",    "label": "🏗️ Construction"},
    {"id": "services",        "label": "🤝 Services"},
    {"id": "commerce",        "label": "🛒 Commerce"},
    {"id": "autre",           "label": "🔹 Autre"},
  ],
)

# Effectif
ask_number(question="Combien d'employés compte votre entreprise ?",
           unit="employés", min=1, max=100000, step=1,
           profile_field='employee_count')

# Annee fondation
ask_number(question="En quelle annee votre entreprise a-t-elle ete creee ?",
           unit="", min=1800, max=2026,
           profile_field='year_founded')

# Politique
ask_yes_no(question="Avez-vous une politique formalisee de gestion des dechets ?",
           profile_field='has_waste_management')
```

REGLE D'OR : si la question correspond a un champ profil de la table
ci-dessus, **passer `profile_field` n'est pas optionnel**. C'est plus
fiable que `update_company_profile` car deterministe (pas de risque
d'oubli LLM, pas d'appel tool supplementaire qui consomme un slot du
budget de 14 tools/tour).
"""
