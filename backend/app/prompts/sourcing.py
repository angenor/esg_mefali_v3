"""Instruction partagee pour les modules producteurs de chiffres (F01).

A injecter dans les prompts des noeuds esg_scoring, carbon, financing,
application, credit, action_plan et chat global (post-onboarding).
"""

SOURCING_INSTRUCTION = """
SOURCAGE OBLIGATOIRE (regle stricte F01) :
- Pour CHAQUE chiffre, score, pourcentage, montant, facteur d'emission, seuil
  ou taux que tu mentionnes, tu DOIS invoquer le tool `cite_source(source_id)`
  avec l'identifiant d'une source verifiee du catalogue dans le meme tour.
- Si tu ne connais pas l'UUID, utilise d'abord `search_source(query, publisher)`
  pour trouver une source pertinente parmi les sources verifiees.
- Si aucune source verifiee ne couvre ton affirmation, invoque
  `flag_unsourced(claim, reason)` avec un motif explicite plutot que d'inventer.
- Le backend rejettera toute reponse contenant un chiffre sans citation
  associee. Tu disposes d'UNE SEULE tentative de correction.
- Sont exemptes : normes ISO (ISO 14001, ISO 26000...), articles
  reglementaires (article 4.2), identifiants techniques (802.1Q,
  PCI-DSS 4.0), references internes (AR6, ODD 13, COP28).
"""
