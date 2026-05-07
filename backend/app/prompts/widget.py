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
| Upload fichier (business plan, statuts) | `ask_file_upload` |
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

# Upload contextualise
ask_file_upload(question="Pouvez-vous m'envoyer votre business plan ?",
                accept=[".pdf", ".docx"], max_size_mb=10)

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
"""
