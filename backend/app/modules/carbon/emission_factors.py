"""Facteurs d'emission et constantes pour le calcul carbone.

Sources : grilles ADEME adaptees Afrique de l'Ouest.
"""

# Facteurs d'emission par source (kgCO2e par unite)
EMISSION_FACTORS: dict[str, dict] = {
    # Energie
    "electricity_ci": {
        "factor": 0.41,
        "unit": "kgCO2e/kWh",
        "label": "Electricite (reseau CI)",
        "category": "energy",
    },
    "diesel_generator": {
        "factor": 2.68,
        "unit": "kgCO2e/L",
        "label": "Generateur diesel",
        "category": "energy",
    },
    "butane_gas": {
        "factor": 2.98,
        "unit": "kgCO2e/kg",
        "label": "Gaz butane",
        "category": "energy",
    },
    # Transport
    "gasoline": {
        "factor": 2.31,
        "unit": "kgCO2e/L",
        "label": "Essence",
        "category": "transport",
    },
    "diesel_transport": {
        "factor": 2.68,
        "unit": "kgCO2e/L",
        "label": "Gasoil",
        "category": "transport",
    },
    # Dechets
    "waste_landfill": {
        "factor": 0.5,
        "unit": "kgCO2e/kg",
        "label": "Dechets (enfouissement)",
        "category": "waste",
    },
    "waste_incineration": {
        "factor": 1.1,
        "unit": "kgCO2e/kg",
        "label": "Dechets (incineration)",
        "category": "waste",
    },
}

# Equivalences parlantes contextualisees Afrique de l'Ouest
EQUIVALENCES: dict[str, dict] = {
    "flight_paris_dakar": {
        "value": 1.2,
        "unit": "tCO2e",
        "label": "vols Paris-Dakar",
    },
    "car_year_avg": {
        "value": 2.4,
        "unit": "tCO2e",
        "label": "annees de conduite moyenne",
    },
    "tree_year_absorption": {
        "value": 0.025,
        "unit": "tCO2e",
        "label": "arbres necessaires pour compenser (1 an)",
    },
}

# Tarifs moyens pour conversion FCFA → unites physiques
PRICE_REFERENCES_FCFA: dict[str, dict] = {
    "electricity_kwh": {
        "price": 100,
        "unit": "FCFA/kWh",
        "label": "Electricite CIE (tranche moyenne)",
    },
    "diesel_liter": {
        "price": 700,
        "unit": "FCFA/L",
        "label": "Diesel",
    },
    "gasoline_liter": {
        "price": 615,
        "unit": "FCFA/L",
        "label": "Essence",
    },
    "butane_12kg": {
        "price": 6000,
        "unit": "FCFA/12.5kg",
        "label": "Gaz butane (bouteille 12.5 kg)",
    },
}

# Categories d'emissions et leur ordre de progression.
# F17 — Ajout de la categorie ``purchases`` (achats matieres premieres).
EMISSION_CATEGORIES: list[dict] = [
    {
        "key": "energy",
        "label": "Energie",
        "required": True,
        "subcategories": ["electricity", "diesel_generator", "butane_gas"],
    },
    {
        "key": "transport",
        "label": "Transport",
        "required": True,
        "subcategories": ["gasoline", "diesel_transport"],
    },
    {
        "key": "waste",
        "label": "Dechets",
        "required": True,
        "subcategories": ["waste_landfill", "waste_incineration"],
    },
    {
        "key": "industrial",
        "label": "Processus industriels",
        "required": False,
        "applicable_sectors": ["manufacturing", "construction", "mining"],
    },
    {
        "key": "agriculture",
        "label": "Agriculture",
        "required": False,
        "applicable_sectors": ["agriculture", "agroalimentaire"],
    },
    # F17 — Achats matieres premieres (optionnel, applicable aux secteurs
    # industriels, BTP, commerce et exploitation miniere).
    {
        "key": "purchases",
        "label": "Achats",
        "required": False,
        "applicable_sectors": [
            "manufacturing",
            "construction",
            "commerce",
            "mining",
            "industrie",
            "btp",
            "agroalimentaire",
        ],
        "subcategories": [
            "purchases_steel",
            "purchases_cement",
            "purchases_paper",
            "purchases_food",
            "purchases_plastic",
            "purchases_other",
        ],
    },
]


def get_emission_factor(subcategory: str) -> float:
    """Retourne le facteur d'emission pour une sous-categorie donnee.

    DEPRECATED (F17) : ce helper est conserve pour retro-compatibilite
    transitoire mais utilise la constante Python figee. Pour les nouveaux
    codes, utiliser ``app.modules.carbon.factor_service.get_emission_factor``
    qui interroge la BDD avec priorite pays/annee.
    """
    factor_info = EMISSION_FACTORS.get(subcategory)
    if factor_info is None:
        raise ValueError(f"Facteur d'emission inconnu: {subcategory}")
    return factor_info["factor"]


def compute_emissions_tco2e(quantity: float, emission_factor: float) -> float:
    """Calcule les emissions en tCO2e a partir de la quantite et du facteur."""
    return round((quantity * emission_factor) / 1000, 4)


def compute_equivalences(total_tco2e: float) -> list[dict]:
    """Calcule les equivalences parlantes pour un total d'emissions."""
    results: list[dict] = []
    for _key, equiv in EQUIVALENCES.items():
        if equiv["value"] > 0:
            count = round(total_tco2e / equiv["value"], 1)
            results.append({
                "label": equiv["label"],
                "value": count,
            })
    return results


def get_applicable_categories(sector: str | None) -> list[str]:
    """Retourne les categories applicables pour un secteur donne."""
    categories: list[str] = []
    for cat in EMISSION_CATEGORIES:
        if cat["required"]:
            categories.append(cat["key"])
        elif sector and sector.lower() in cat.get("applicable_sectors", []):
            categories.append(cat["key"])
    return categories
