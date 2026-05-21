"""Helper partage : instructions pour le tool trigger_guided_tour.

Injecte dans les 6 prompts systeme des modules eligibles au guidage visuel
(chat post-onboarding, esg_scoring, carbon, financing, credit, action_plan).
Les modules application, document, profiling et router ne recoivent PAS
ce prompt — le guidage ne concerne pas les phases de saisie ou d'extraction.

Voir story 6.2 : le tool `trigger_guided_tour` existe deja (story 6.1),
cette instruction active sa capacite d'appel par le LLM.
"""

GUIDED_TOUR_INSTRUCTION = """## OUTIL GUIDAGE VISUEL — trigger_guided_tour

Tu disposes d'un outil `trigger_guided_tour` qui lance un parcours interactif
sur l'interface (flechage, popovers, navigation inter-pages). L'utilisateur
voit alors ses resultats expliques pas a pas sur les ecrans dedies.

### Parcours disponibles
- `show_esg_results` — Resultats de l'evaluation ESG (/esg/results)
- `show_carbon_results` — Bilan carbone et plan de reduction (/carbon/results)
- `show_financing_catalog` — Catalogue de fonds verts et matchs (/financing)
- `show_credit_score` — Score credit vert alternatif (/credit-score)
- `show_action_plan` — Feuille de route 6-12-24 mois (/action-plan)
- `show_dashboard_overview` — Vue d'ensemble du tableau de bord (/dashboard)
- `show_reports_carbon` — Bibliotheque des rapports Word, onglet Carbone (/reports?tab=carbon)
- `show_reports_esg` — Bibliotheque des rapports Word, onglet ESG (/reports?tab=esg)

### Quand proposer un guidage
1. **Apres completion d'un module** : evaluation ESG terminee, bilan carbone
   finalise, plan d'action genere, dossier financement soumis, score de credit
   calcule. C'est le moment ideal pour montrer les resultats visuellement.
2. **Sur demande explicite de l'utilisateur** : il dit « montre-moi »,
   « guide-moi vers », « où sont mes resultats », « visualise-moi »,
   « fais-moi visiter », ou toute formulation indiquant clairement qu'il
   veut etre accompagne vers un ecran. Le verbe `voir` seul (« je veux voir »,
   « j'aimerais voir ») NE suffit PAS — il faut un verbe imperatif d'action
   visuel direct (`montre`, `guide`, `visualise`, `fais-moi visiter`, `où sont`).

### Mapping canonique module termine → tour_id

Quand un module vient d'etre cloture, le `tour_id` a proposer est fixe :

| Module termine / demande utilisateur | tour_id a utiliser |
|---|---|
| Evaluation ESG close (30 criteres notes) | `show_esg_results` |
| Bilan carbone finalise (plan de reduction genere) | `show_carbon_results` |
| Recherche de fonds / demande catalogue financement | `show_financing_catalog` |
| Score credit vert calcule | `show_credit_score` |
| Plan d'action / feuille de route 6-12-24 mois genere | `show_action_plan` |
| Vue d'ensemble tableau de bord (post-onboarding, chat) | `show_dashboard_overview` |
| Rapport carbone Word genere (`generate_carbon_report` OK) | `show_reports_carbon` |
| Rapport ESG Word genere (`generate_esg_report` OK) | `show_reports_esg` |

N'invente jamais un autre `tour_id`. Ces 8 identifiants sont la source unique
de verite — toute autre valeur est rejetee cote serveur.

**Distinction importante** : apres FINALISATION d'un bilan ou d'une evaluation
(score calcule, plan de reduction genere), utilise `show_*_results` pour montrer
les graphiques et resultats metier. Apres GENERATION D'UN RAPPORT TELECHARGEABLE
(`generate_*_report` retourne `ok:true`), utilise `show_reports_*` pour amener
l'utilisateur vers la bibliotheque /reports ou il pourra telecharger le .docx.
Ce sont deux moments distincts du parcours, ne les confonds pas.

### Cles `context` par tour_id (OBLIGATOIRE — remplis toujours)

Sans ces cles, les placeholders `{{...}}` s'affichent bruts dans le popover
au lieu des vraies valeurs. Les valeurs proviennent du contexte de la page
courante deja injecte dans ton prompt (profil entreprise, dernier bilan,
dernier score, etc.) — ne les invente pas, extrais-les.

| tour_id | Cles requises |
|---|---|
| `show_carbon_results` | `total_tco2`, `top_category`, `top_category_pct`, `sector` |
| `show_esg_results` | `esg_score` |
| `show_credit_score` | `credit_score` |
| `show_financing_catalog` | `matched_count` |
| `show_action_plan` | `active_actions` |
| `show_dashboard_overview` | `esg_score`, `total_tco2`, `credit_score`, `matched_count` |
| `show_reports_carbon` | `report_filename` (nom .docx renvoye par generate_carbon_report) |
| `show_reports_esg` | `report_filename` (nom .docx renvoye par generate_esg_report) |

Exemple concret (user : « Montre-moi mon bilan carbone ») :
```
trigger_guided_tour(
  tour_id="show_carbon_results",
  context={"total_tco2": 12.4, "top_category": "Transport",
           "top_category_pct": 38, "sector": "Agro-alimentaire"},
)
```

### Intent ambigu — privilegie le consentement

Si l'utilisateur exprime un interet **vague** ou **ambigu** pour ses donnees
— par exemple « j'aimerais voir mes chiffres », « dis-m'en plus »,
« c'est quoi la suite ? » — le declenchement direct n'est PAS autorise.
Dans le doute, privilegie `ask_interactive_question` pour obtenir un
consentement clair (prudence > initiative). Un intent est **explicite**
uniquement s'il contient un verbe d'action visuel clair :
`montre`, `guide`, `visualise`, `fais-moi visiter`, `où sont`.
Sans ce signal, reste prudent et propose via le widget.

### Regles de declenchement obligatoires

1. **Proposition de guidage (post-module OU en cours d'echange)** : appelle
   `ask_interactive_question` pour demander le consentement de l'utilisateur.
   - `question_type="qcu"`
   - **EXACTEMENT 2 options, PAS PLUS** :
     `{"id":"yes","label":"Oui, montre-moi","emoji":"👀"}` et
     `{"id":"no","label":"Non merci","emoji":"🙏"}`.
   - Les `id` « yes » et « no » sont OBLIGATOIRES (contrat UI, ne jamais renommer).
   - INTERDIT : proposer 3 options ou plus pour un consentement de guidage.
   - INTERDIT : remplacer « yes »/« no » par des choix metier (ex : « carbone »,
     « boad ») — ces segmentations metier sont une question differente, pas un
     consentement de guidage.
   Si l'utilisateur choisit `yes` au tour suivant, appelle alors
   `trigger_guided_tour(tour_id)`.

2. **Sur demande explicite (declenchement direct)** : appelle
   `trigger_guided_tour(tour_id)` IMMEDIATEMENT, SANS passer par
   `ask_interactive_question`. L'intent est deja clair, pas besoin
   de consentement supplementaire.

3. **Un seul guidage par tour** : ne declenche jamais plusieurs parcours
   dans la meme reponse. Attends le retour de l'utilisateur avant de
   proposer un autre parcours.

4. **Pas de texte apres l'appel** : une fois `trigger_guided_tour` appele,
   le frontend prend la main, le widget de chat se retracte automatiquement
   et le parcours demarre. N'ajoute aucun texte apres le tool call.

5. **Separation guidage vs segmentation metier** : si tu veux affiner la
   recherche de l'utilisateur (ex : « quel type de fonds t'interesse ? »),
   utilise `ask_interactive_question` avec des options metier — mais NE PROPOSE
   PAS de guidage dans le meme tour. Le consentement de guidage est une
   question distincte, posee dans un tour separe apres la segmentation.

5. **Securite du champ `context`** (NFR10 — rappel) :
   - `context` peut porter un prenom ou des chiffres non sensibles pour
     personnaliser le texte du popover (ex : `{"user_first_name": "Fatou"}`,
     `{"pillar_top": "Social"}`, `{"score": 72}`).
   - JAMAIS d'IDs techniques (`user_id`, `conversation_id`), de tokens,
     d'emails, de mots de passe, ni de donnees PII ou financieres sensibles.

### Exemple 1 — Proposition post-module (evaluation ESG terminee)

Apres avoir cloture une evaluation ESG complete (30 criteres notes,
visuels radar+gauge+table affiches), propose le guidage :
```
ask_interactive_question(
  question_type="qcu",
  prompt="Evaluation terminee ! Veux-tu que je te montre tes resultats en detail sur l'ecran ?",
  options=[
    {"id":"yes","label":"Oui, montre-moi","emoji":"👀"},
    {"id":"no","label":"Non merci","emoji":"🙏"},
  ],
)
```
Si l'utilisateur choisit `yes` au tour suivant :
```
trigger_guided_tour(
  tour_id="show_esg_results",
  context={"pillar_top":"Social"},
)
```

### Exemple 2 — Declenchement direct (demande explicite)

Utilisateur : « Montre-moi mes resultats carbone »
```
trigger_guided_tour(
  tour_id="show_carbon_results",
)
```
Pas de `ask_interactive_question` : l'utilisateur a deja demande
explicitement, toute question de consentement serait redondante.

### Exemple 3 — Declenchement direct avec contexte

Utilisateur : « Guide-moi vers le catalogue des fonds verts, je cherche pour
mon projet solaire »
```
trigger_guided_tour(
  tour_id="show_financing_catalog",
  context={"project_hint":"solaire"},
)
```
"""


_ADAPTIVE_FREQUENCY_HINT = """## Modulation de frequence (adaptation comportementale)

L'utilisateur a refuse plusieurs fois consecutives tes propositions de guidage.
- Ne propose PLUS spontanement de guidage via `ask_interactive_question` avec les options « Oui, montre-moi » / « Non merci ».
- Ne declenche un guidage via `trigger_guided_tour` QUE sur demande explicite de l'utilisateur (verbes d'action visuels : `montre`, `guide`, `visualise`, `fais-moi visiter`, `où sont`).
- Ne relance pas et ne suggere pas en boucle — respecte son choix et ne plus proposer tant que l'intent reste implicite.
- Cette restriction se leve automatiquement quand l'utilisateur acceptera a nouveau un guidage (compteur reinitialise cote client).
"""


def build_adaptive_frequency_hint(guidance_stats: dict | None) -> str:
    """Construire un bloc d'instruction adaptative selon les stats client (FR17).

    Quand l'utilisateur a refuse >= 3 fois consecutives, retourne un bloc
    normatif demandant au LLM de ne plus proposer de guidage spontanement.
    Sinon, retourne une chaine vide (appendix conditionnel pur).

    Args:
        guidance_stats: dict {refusal_count:int, acceptance_count:int} ou None.

    Returns:
        Bloc texte FR si seuil atteint, chaine vide sinon. Pure, deterministe,
        sans PII (NFR10 : aucune valeur numerique exposee dans la chaine).
    """
    if guidance_stats is None:
        return ""
    refusal_count = guidance_stats.get("refusal_count")
    if not isinstance(refusal_count, int) or isinstance(refusal_count, bool):
        return ""
    if refusal_count < 3:
        return ""
    return _ADAPTIVE_FREQUENCY_HINT
