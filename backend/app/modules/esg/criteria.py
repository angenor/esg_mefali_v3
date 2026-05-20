"""Définition des 30 critères ESG contextualisés pour les PME africaines.

Grille de 30 critères (10 par pilier E-S-G), chacun noté de 0 à 10.
Adaptés au contexte UEMOA/CEDEAO et au secteur informel.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ESGCriterion:
    """Définition d'un critère ESG."""

    code: str
    pillar: str
    label: str
    description: str
    question: str


# --- Pilier Environnement (E1-E10) ---

ENVIRONMENT_CRITERIA: tuple[ESGCriterion, ...] = (
    ESGCriterion(
        code="E1",
        pillar="environment",
        label="Gestion des déchets",
        description="Pratiques de tri, recyclage et élimination des déchets.",
        question="Comment votre entreprise gère-t-elle ses déchets ? Avez-vous un système de tri ou de recyclage ?",
    ),
    ESGCriterion(
        code="E2",
        pillar="environment",
        label="Consommation d'énergie",
        description="Niveau de consommation énergétique et efforts de réduction.",
        question="Quelle est votre consommation énergétique principale ? Avez-vous des initiatives pour la réduire ?",
    ),
    ESGCriterion(
        code="E3",
        pillar="environment",
        label="Émissions carbone",
        description="Émissions de gaz à effet de serre directes et indirectes.",
        question="Avez-vous une idée de vos émissions de CO2 ? Utilisez-vous des véhicules ou machines polluants ?",
    ),
    ESGCriterion(
        code="E4",
        pillar="environment",
        label="Ressources naturelles",
        description="Utilisation responsable des matières premières et ressources.",
        question="Comment gérez-vous vos matières premières ? Avez-vous des pratiques pour limiter le gaspillage ?",
    ),
    ESGCriterion(
        code="E5",
        pillar="environment",
        label="Biodiversité",
        description="Impact sur la faune, la flore et les écosystèmes locaux.",
        question="Votre activité a-t-elle un impact sur l'environnement naturel local (forêts, cours d'eau, faune) ?",
    ),
    ESGCriterion(
        code="E6",
        pillar="environment",
        label="Gestion de l'eau",
        description="Consommation, traitement et protection des ressources en eau.",
        question="Comment gérez-vous votre consommation d'eau ? Traitez-vous vos eaux usées ?",
    ),
    ESGCriterion(
        code="E7",
        pillar="environment",
        label="Politique environnementale",
        description="Existence d'une politique ou charte environnementale formelle.",
        question="Avez-vous une politique environnementale écrite ou des engagements formels en matière d'environnement ?",
    ),
    ESGCriterion(
        code="E8",
        pillar="environment",
        label="Énergies renouvelables",
        description="Utilisation de sources d'énergie renouvelables (solaire, éolien, biomasse).",
        question="Utilisez-vous des énergies renouvelables (panneaux solaires, biomasse) ? Envisagez-vous d'en adopter ?",
    ),
    ESGCriterion(
        code="E9",
        pillar="environment",
        label="Transport vert",
        description="Optimisation logistique et réduction de l'empreinte transport.",
        question="Comment organisez-vous vos transports et livraisons ? Cherchez-vous à réduire les trajets ou émissions ?",
    ),
    ESGCriterion(
        code="E10",
        pillar="environment",
        label="Économie circulaire",
        description="Réutilisation, réparation et valorisation des produits et matériaux.",
        question="Pratiquez-vous la réutilisation ou la valorisation de vos produits et sous-produits ?",
    ),
)

# --- Pilier Social (S1-S10) ---

SOCIAL_CRITERIA: tuple[ESGCriterion, ...] = (
    ESGCriterion(
        code="S1",
        pillar="social",
        label="Conditions de travail",
        description="Qualité de l'environnement de travail, horaires, contrats.",
        question="Quelles sont les conditions de travail dans votre entreprise ? Vos employés ont-ils des contrats formels ?",
    ),
    ESGCriterion(
        code="S2",
        pillar="social",
        label="Égalité hommes-femmes",
        description="Parité, égalité salariale et accès aux postes de responsabilité.",
        question="Quelle est la proportion de femmes dans votre entreprise, y compris aux postes de direction ?",
    ),
    ESGCriterion(
        code="S3",
        pillar="social",
        label="Formation et développement",
        description="Programmes de formation continue et développement des compétences.",
        question="Proposez-vous des formations à vos employés ? Combien de jours par an en moyenne ?",
    ),
    ESGCriterion(
        code="S4",
        pillar="social",
        label="Impact communautaire",
        description="Contribution au développement économique et social de la communauté locale.",
        question="Comment votre entreprise contribue-t-elle au développement de votre communauté locale ?",
    ),
    ESGCriterion(
        code="S5",
        pillar="social",
        label="Santé et sécurité",
        description="Mesures de protection de la santé et sécurité des travailleurs.",
        question="Quelles mesures de sécurité et de santé au travail avez-vous mises en place ?",
    ),
    ESGCriterion(
        code="S6",
        pillar="social",
        label="Rémunération équitable",
        description="Niveau de rémunération juste et avantages sociaux.",
        question="Comment se situent vos rémunérations par rapport au marché local ? Offrez-vous des avantages sociaux ?",
    ),
    ESGCriterion(
        code="S7",
        pillar="social",
        label="Inclusion et diversité",
        description="Politiques d'inclusion des personnes handicapées, minorités, jeunes.",
        question="Avez-vous des pratiques favorisant l'inclusion et la diversité dans votre recrutement ?",
    ),
    ESGCriterion(
        code="S8",
        pillar="social",
        label="Dialogue social",
        description="Communication interne, représentation du personnel, gestion des conflits.",
        question="Comment se passe la communication avec vos employés ? Existe-t-il un représentant du personnel ?",
    ),
    ESGCriterion(
        code="S9",
        pillar="social",
        label="Fournisseurs locaux",
        description="Part des achats auprès de fournisseurs locaux et nationaux.",
        question="Quelle proportion de vos achats provient de fournisseurs locaux ou nationaux ?",
    ),
    ESGCriterion(
        code="S10",
        pillar="social",
        label="Satisfaction employés",
        description="Mesure de la satisfaction, du turnover et de l'engagement des employés.",
        question="Quel est le niveau de satisfaction de vos employés ? Mesurez-vous le turnover ?",
    ),
)

# --- Pilier Gouvernance (G1-G10) ---

GOVERNANCE_CRITERIA: tuple[ESGCriterion, ...] = (
    ESGCriterion(
        code="G1",
        pillar="governance",
        label="Transparence financière",
        description="Clarté et accessibilité des comptes et rapports financiers.",
        question="Vos comptes financiers sont-ils tenus à jour et accessibles aux parties prenantes ?",
    ),
    ESGCriterion(
        code="G2",
        pillar="governance",
        label="Structure de décision",
        description="Organisation du pouvoir décisionnel et contre-pouvoirs.",
        question="Comment sont prises les décisions stratégiques dans votre entreprise ? Existe-t-il un conseil ?",
    ),
    ESGCriterion(
        code="G3",
        pillar="governance",
        label="Éthique des affaires",
        description="Respect des règles éthiques dans les relations commerciales.",
        question="Comment gérez-vous l'éthique dans vos relations commerciales (clients, fournisseurs, partenaires) ?",
    ),
    ESGCriterion(
        code="G4",
        pillar="governance",
        label="Conformité réglementaire",
        description="Respect des lois et réglementations en vigueur.",
        question="Êtes-vous en conformité avec les réglementations locales (fiscale, sociale, environnementale) ?",
    ),
    ESGCriterion(
        code="G5",
        pillar="governance",
        label="Politique anti-corruption",
        description="Mesures de prévention et de lutte contre la corruption.",
        question="Avez-vous une politique anti-corruption formelle ? Comment gérez-vous les risques de corruption ?",
    ),
    ESGCriterion(
        code="G6",
        pillar="governance",
        label="Gestion des risques",
        description="Identification, évaluation et mitigation des risques stratégiques.",
        question="Avez-vous un processus d'identification et de gestion des risques pour votre entreprise ?",
    ),
    ESGCriterion(
        code="G7",
        pillar="governance",
        label="Responsabilité du dirigeant",
        description="Engagement personnel du dirigeant dans la stratégie ESG.",
        question="En tant que dirigeant, comment vous impliquez-vous personnellement dans les sujets ESG ?",
    ),
    ESGCriterion(
        code="G8",
        pillar="governance",
        label="Communication parties prenantes",
        description="Dialogue avec les actionnaires, employés, communautés et régulateurs.",
        question="Comment communiquez-vous avec vos différentes parties prenantes (employés, clients, communauté) ?",
    ),
    ESGCriterion(
        code="G9",
        pillar="governance",
        label="Confidentialité des données",
        description="Protection des données personnelles et professionnelles.",
        question="Comment protégez-vous les données personnelles de vos clients et employés ?",
    ),
    ESGCriterion(
        code="G10",
        pillar="governance",
        label="Planification de succession",
        description="Plans de continuité et de transmission de l'entreprise.",
        question="Avez-vous un plan de succession ou de continuité pour votre entreprise ?",
    ),
)

# Tous les criteres indexes par code
ALL_CRITERIA: tuple[ESGCriterion, ...] = (
    ENVIRONMENT_CRITERIA + SOCIAL_CRITERIA + GOVERNANCE_CRITERIA
)

CRITERIA_BY_CODE: dict[str, ESGCriterion] = {c.code: c for c in ALL_CRITERIA}

PILLAR_CRITERIA: dict[str, tuple[ESGCriterion, ...]] = {
    "environment": ENVIRONMENT_CRITERIA,
    "social": SOCIAL_CRITERIA,
    "governance": GOVERNANCE_CRITERIA,
}

PILLAR_LABELS: dict[str, str] = {
    "environment": "Environnement",
    "social": "Social",
    "governance": "Gouvernance",
}

PILLAR_ORDER: list[str] = ["environment", "social", "governance"]

TOTAL_CRITERIA: int = len(ALL_CRITERIA)
