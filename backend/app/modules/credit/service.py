"""Service metier pour le module Scoring de Credit Vert Alternatif."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit import ConfidenceLabel, CreditCategory, CreditDataPoint, CreditScore

# --- Constantes ---

SOLVABILITY_WEIGHT = 0.50
GREEN_IMPACT_WEIGHT = 0.50
SCORE_VALIDITY_MONTHS = 6

# Poids des sous-facteurs solvabilite
SOLVABILITY_FACTORS = {
    "activity_regularity": 0.20,
    "information_coherence": 0.20,
    "governance": 0.20,
    "financial_transparency": 0.20,
    "engagement_seriousness": 0.20,
}

# Poids des sous-facteurs impact vert
GREEN_IMPACT_FACTORS = {
    "esg_global_score": 0.40,
    "esg_trend": 0.20,
    "carbon_engagement": 0.20,
    "green_projects": 0.20,
}

# Bareme engagement intermediaire (points bruts additionnels)
INTERMEDIARY_SCORES = {
    "contacting_intermediary": 15,  # par intermediaire, max 30
    "applying": 20,
    "submitted": 30,
    "accepted": 20,  # bonus
}

# Sources de donnees attendues
DATA_SOURCES = [
    "Profil entreprise",
    "Evaluation ESG",
    "Bilan carbone",
    "Documents fournis",
    "Candidatures fonds",
    "Interactions intermediaires",
]


# --- Fonctions de calcul ---


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    """Borner une valeur entre minimum et maximum."""
    return max(minimum, min(maximum, value))


def calculate_solvability_score(data_points: dict) -> tuple[float, dict]:
    """Calculer le score de solvabilite et le breakdown des facteurs.

    Args:
        data_points: dictionnaire {subcategory: {score, details, ...}}

    Returns:
        (score_total, factors_breakdown)
    """
    factors = {}
    total = 0.0

    for factor_key, weight in SOLVABILITY_FACTORS.items():
        point = data_points.get(factor_key, {})
        raw_score = _clamp(float(point.get("score", 0)))
        details = point.get("details", "Donnees insuffisantes")

        factor_data: dict = {
            "score": raw_score,
            "weight": weight,
            "details": details,
        }

        # Ajouter les interactions intermediaires si disponibles
        if factor_key == "engagement_seriousness" and "intermediary_interactions" in point:
            factor_data["intermediary_interactions"] = point["intermediary_interactions"]

        factors[factor_key] = factor_data
        total += raw_score * weight

    return round(_clamp(total), 1), factors


def calculate_green_impact_score(data_points: dict) -> tuple[float, dict]:
    """Calculer le score d'impact vert et le breakdown des facteurs.

    Args:
        data_points: dictionnaire {subcategory: {score, details, ...}}

    Returns:
        (score_total, factors_breakdown)
    """
    factors = {}
    total = 0.0

    for factor_key, weight in GREEN_IMPACT_FACTORS.items():
        point = data_points.get(factor_key, {})
        raw_score = _clamp(float(point.get("score", 0)))
        details = point.get("details", "Donnees insuffisantes")

        factor_data: dict = {
            "score": raw_score,
            "weight": weight,
            "details": details,
        }

        # Ajouter les statuts candidatures si disponibles
        if factor_key == "green_projects" and "application_statuses" in point:
            factor_data["application_statuses"] = point["application_statuses"]

        factors[factor_key] = factor_data
        total += raw_score * weight

    return round(_clamp(total), 1), factors


def calculate_combined_score(
    solvability: float, green_impact: float, confidence: float
) -> float:
    """Calculer le score combine ajuste par la confiance.

    Formule: (solvability * 0.5 + green_impact * 0.5) * confidence
    """
    raw = solvability * SOLVABILITY_WEIGHT + green_impact * GREEN_IMPACT_WEIGHT
    return round(_clamp(raw * confidence), 1)


def calculate_confidence(source_coverage: dict) -> tuple[float, str]:
    """Calculer le coefficient et le label de confiance.

    Args:
        source_coverage: {source_name: {available: bool, completeness: float, last_updated: str|None}}

    Returns:
        (confidence_level, confidence_label)
    """
    total_sources = len(DATA_SOURCES)
    sources_with_data = 0
    freshness_sum = 0.0
    freshness_count = 0

    now = datetime.now(tz=timezone.utc)

    for source_name in DATA_SOURCES:
        info = source_coverage.get(source_name, {})
        if info.get("available", False):
            sources_with_data += 1

        last_updated_str = info.get("last_updated")
        if last_updated_str:
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=timezone.utc)
                age_months = (now - last_updated).days / 30.0
                freshness = max(0.0, 1.0 - age_months / 12.0)
                freshness_sum += freshness
                freshness_count += 1
            except (ValueError, TypeError):
                pass

    coverage = sources_with_data / total_sources if total_sources > 0 else 0.0
    avg_freshness = freshness_sum / freshness_count if freshness_count > 0 else 0.0

    confidence = 0.5 + (coverage * 0.3) + (avg_freshness * 0.2)
    confidence = _clamp(confidence, 0.5, 1.0)
    confidence = round(confidence, 2)

    # Determiner le label
    if confidence < 0.6:
        label = ConfidenceLabel.very_low.value
    elif confidence < 0.7:
        label = ConfidenceLabel.low.value
    elif confidence < 0.8:
        label = ConfidenceLabel.medium.value
    elif confidence < 0.9:
        label = ConfidenceLabel.good.value
    else:
        label = ConfidenceLabel.excellent.value

    return confidence, label


def calculate_engagement_score(intermediary_interactions: dict) -> tuple[float, dict]:
    """Calculer le sous-score engagement_seriousness base sur les interactions intermediaires.

    Args:
        intermediary_interactions: {contacted: int, appointments: int, submitted: int,
                                    accepted: int, intermediary_names: list}

    Returns:
        (score_sur_100, interactions_detail)
    """
    contacted = intermediary_interactions.get("contacted", 0)
    appointments = intermediary_interactions.get("appointments", 0)
    submitted = intermediary_interactions.get("submitted", 0)
    accepted = intermediary_interactions.get("accepted", 0)

    # Calcul par bareme (plafonner les contacts a 2)
    score = 0.0
    score += min(contacted, 2) * INTERMEDIARY_SCORES["contacting_intermediary"]  # max 30
    score += min(appointments, 1) * INTERMEDIARY_SCORES["applying"]  # max 20
    score += min(submitted, 1) * INTERMEDIARY_SCORES["submitted"]  # max 30
    score += min(accepted, 1) * INTERMEDIARY_SCORES["accepted"]  # max 20

    return _clamp(score), {
        "contacted": contacted,
        "appointments": appointments,
        "submitted": submitted,
        "intermediary_names": intermediary_interactions.get("intermediary_names", []),
    }


def generate_recommendations(
    solvability_factors: dict,
    green_impact_factors: dict,
    source_coverage: dict,
    intermediary_interactions: dict | None = None,
) -> list[dict]:
    """Generer des recommandations personnalisees basees sur les facteurs.

    Retourne une liste de {action, impact, category} triee par impact.
    """
    recommendations: list[dict] = []

    # Recommandations solvabilite
    for key, factor in solvability_factors.items():
        score = factor.get("score", 0)
        if score < 50:
            impact = "high"
        elif score < 70:
            impact = "medium"
        else:
            continue

        labels = {
            "activity_regularity": "Renforcez la regularite de votre activite (historique comptable, registres)",
            "information_coherence": "Ameliorez la coherence de vos informations (verifiez les donnees saisies)",
            "governance": "Formalisez votre gouvernance (proces-verbaux, organigramme, procedures)",
            "financial_transparency": "Fournissez vos etats financiers des 2 derniers exercices",
            "engagement_seriousness": "Contactez un intermediaire financier pour accompagner votre demarche",
        }
        if key in labels:
            recommendations.append({
                "action": labels[key],
                "impact": impact,
                "category": "solvability",
            })

    # Recommandations impact vert
    for key, factor in green_impact_factors.items():
        score = factor.get("score", 0)
        if score < 50:
            impact = "high"
        elif score < 70:
            impact = "medium"
        else:
            continue

        labels = {
            "esg_global_score": "Ameliorez votre score ESG en completant votre evaluation",
            "esg_trend": "Maintenez vos efforts ESG pour ameliorer la tendance",
            "carbon_engagement": "Realisez un bilan carbone et engagez un plan de reduction",
            "green_projects": "Soumettez des candidatures a des fonds verts via un intermediaire",
        }
        if key in labels:
            recommendations.append({
                "action": labels[key],
                "impact": impact,
                "category": "green_impact",
            })

    # Recommandation couverture sources
    for source_name, info in source_coverage.items():
        if not info.get("available", False):
            recommendations.append({
                "action": f"Completez la source '{source_name}' pour ameliorer la fiabilite du score",
                "impact": "medium",
                "category": "coverage",
            })

    # Recommandation intermediaires si aucune interaction
    if intermediary_interactions and intermediary_interactions.get("contacted", 0) == 0:
        recommendations.append({
            "action": "Contactez un intermediaire financier pour ameliorer votre score d'engagement",
            "impact": "high",
            "category": "engagement",
        })

    # Trier par impact (high > medium > low)
    priority = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda r: priority.get(r["impact"], 3))

    return recommendations


# --- Collecte des data points ---


async def collect_data_points(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> tuple[dict, dict, dict, dict | None]:
    """Collecter les data points depuis les modules existants.

    Returns:
        (solvability_points, green_impact_points, source_coverage, intermediary_interactions)
    """
    solvability_points: dict = {}
    green_impact_points: dict = {}
    source_coverage: dict = {}
    intermediary_interactions: dict = {
        "contacted": 0,
        "appointments": 0,
        "submitted": 0,
        "accepted": 0,
        "intermediary_names": [],
    }

    # 1. Profil entreprise
    try:
        from app.models.company import CompanyProfile
        result = await db.execute(
            select(CompanyProfile).where(CompanyProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        if profile:
            # Calculer completude du profil
            fields = ["company_name", "sector", "city", "employee_count",
                       "annual_revenue_xof", "governance_structure", "year_founded"]
            filled = sum(1 for f in fields if getattr(profile, f, None) is not None)
            completeness = filled / len(fields) if fields else 0

            solvability_points["activity_regularity"] = {
                "score": min(completeness * 100, 100),
                "details": f"Profil complete a {int(completeness * 100)}%",
            }
            solvability_points["information_coherence"] = {
                "score": min(completeness * 90, 100),
                "details": f"{filled}/{len(fields)} champs renseignes",
            }
            solvability_points["governance"] = {
                "score": 40 if completeness < 0.5 else 60 if completeness < 0.8 else 75,
                "details": "Structure de gouvernance " + (
                    "basique" if completeness < 0.5 else
                    "partielle" if completeness < 0.8 else
                    "bien documentee"
                ),
            }
            source_coverage["Profil entreprise"] = {
                "available": True,
                "completeness": round(completeness, 2),
                "last_updated": profile.updated_at.isoformat() if hasattr(profile, "updated_at") and profile.updated_at else None,
            }
        else:
            source_coverage["Profil entreprise"] = {"available": False, "completeness": 0}
    except Exception:
        source_coverage["Profil entreprise"] = {"available": False, "completeness": 0}

    # 2. Evaluation ESG
    try:
        from app.models.esg import ESGAssessment
        result = await db.execute(
            select(ESGAssessment)
            .where(ESGAssessment.user_id == user_id)
            .order_by(ESGAssessment.created_at.desc())
            .limit(1)
        )
        esg = result.scalar_one_or_none()
        if esg:
            esg_score = esg.overall_score if hasattr(esg, "overall_score") and esg.overall_score else 50
            green_impact_points["esg_global_score"] = {
                "score": _clamp(esg_score),
                "details": f"Score ESG {esg_score}/100",
            }
            # Tendance ESG (simplifiee — comparer avec l'avant-dernier)
            result2 = await db.execute(
                select(ESGAssessment)
                .where(ESGAssessment.user_id == user_id)
                .order_by(ESGAssessment.created_at.desc())
                .offset(1)
                .limit(1)
            )
            prev_esg = result2.scalar_one_or_none()
            if prev_esg and hasattr(prev_esg, "overall_score") and prev_esg.overall_score:
                diff = esg_score - prev_esg.overall_score
                trend_score = _clamp(50 + diff * 2)
                green_impact_points["esg_trend"] = {
                    "score": trend_score,
                    "details": f"{'Amelioration' if diff > 0 else 'Baisse'} de {abs(diff):.0f} points",
                }
            else:
                green_impact_points["esg_trend"] = {
                    "score": 50,
                    "details": "Premiere evaluation — pas de tendance disponible",
                }
            source_coverage["Evaluation ESG"] = {
                "available": True,
                "completeness": 1.0,
                "last_updated": esg.created_at.isoformat() if esg.created_at else None,
            }
        else:
            source_coverage["Evaluation ESG"] = {"available": False, "completeness": 0}
    except Exception:
        source_coverage["Evaluation ESG"] = {"available": False, "completeness": 0}

    # 3. Bilan carbone
    try:
        from app.models.carbon import CarbonAssessment, CarbonStatusEnum
        result = await db.execute(
            select(CarbonAssessment)
            .where(
                CarbonAssessment.user_id == user_id,
                CarbonAssessment.status == CarbonStatusEnum.completed,
            )
            .order_by(CarbonAssessment.created_at.desc())
            .limit(1)
        )
        carbon = result.scalar_one_or_none()
        if carbon:
            # Avoir un bilan carbone complete est un bon signal
            has_reduction = bool(carbon.reduction_plan)
            carbon_score = 70 if not has_reduction else 85
            green_impact_points["carbon_engagement"] = {
                "score": carbon_score,
                "details": "Bilan carbone realise" + (", plan de reduction actif" if has_reduction else ""),
            }
            source_coverage["Bilan carbone"] = {
                "available": True,
                "completeness": 0.9 if has_reduction else 0.7,
                "last_updated": carbon.created_at.isoformat() if carbon.created_at else None,
            }
        else:
            source_coverage["Bilan carbone"] = {"available": False, "completeness": 0}
    except Exception:
        source_coverage["Bilan carbone"] = {"available": False, "completeness": 0}

    # 4. Documents fournis
    try:
        from app.models.document import Document
        result = await db.execute(
            select(func.count()).select_from(
                select(Document).where(Document.user_id == user_id).subquery()
            )
        )
        doc_count = result.scalar() or 0
        if doc_count > 0:
            doc_completeness = min(doc_count / 5, 1.0)  # 5 docs = complet
            solvability_points["financial_transparency"] = {
                "score": _clamp(doc_completeness * 100),
                "details": f"{doc_count} document(s) fourni(s)",
            }
            source_coverage["Documents fournis"] = {
                "available": True,
                "completeness": round(doc_completeness, 2),
            }
        else:
            source_coverage["Documents fournis"] = {"available": False, "completeness": 0}
    except Exception:
        source_coverage["Documents fournis"] = {"available": False, "completeness": 0}

    # 5. Candidatures fonds + 6. Interactions intermediaires
    try:
        from app.models.financing import FundMatch, MatchStatus
        result = await db.execute(
            select(FundMatch).where(FundMatch.user_id == user_id)
        )
        matches = list(result.scalars().all())
        if matches:
            # Analyser les statuts des candidatures
            interested = 0
            submitted_via_intermediary = 0
            accepted = 0
            contacted_names: list[str] = []

            for match in matches:
                status_val = match.status.value if hasattr(match.status, "value") else match.status
                if status_val == "interested":
                    interested += 1
                elif status_val == "contacting_intermediary":
                    intermediary_interactions["contacted"] += 1
                    if match.contacted_intermediary_id:
                        # Recuperer le nom de l'intermediaire
                        try:
                            from app.models.financing import Intermediary
                            inter_result = await db.execute(
                                select(Intermediary.name).where(
                                    Intermediary.id == match.contacted_intermediary_id
                                )
                            )
                            inter_name = inter_result.scalar_one_or_none()
                            if inter_name and inter_name not in contacted_names:
                                contacted_names.append(inter_name)
                        except Exception:
                            pass
                elif status_val == "applying":
                    intermediary_interactions["appointments"] += 1
                elif status_val == "submitted":
                    intermediary_interactions["submitted"] += 1
                    submitted_via_intermediary += 1
                elif status_val == "accepted":
                    intermediary_interactions["accepted"] += 1
                    accepted += 1

            intermediary_interactions["intermediary_names"] = contacted_names

            # Score projets verts base sur les candidatures
            project_score = min(
                interested * 10 + submitted_via_intermediary * 30 + accepted * 40,
                100,
            )
            green_impact_points["green_projects"] = {
                "score": _clamp(project_score),
                "details": f"{len(matches)} candidature(s), {submitted_via_intermediary} soumise(s) via intermediaire",
                "application_statuses": {
                    "interested": interested,
                    "submitted_via_intermediary": submitted_via_intermediary,
                    "accepted": accepted,
                },
            }

            source_coverage["Candidatures fonds"] = {
                "available": True,
                "completeness": min(len(matches) / 3, 1.0),
            }

            # Score engagement intermediaire
            eng_score, eng_details = calculate_engagement_score(intermediary_interactions)
            solvability_points["engagement_seriousness"] = {
                "score": eng_score,
                "details": _build_engagement_details(intermediary_interactions),
                "intermediary_interactions": eng_details,
            }

            has_interactions = (
                intermediary_interactions["contacted"] > 0
                or intermediary_interactions["submitted"] > 0
            )
            source_coverage["Interactions intermediaires"] = {
                "available": has_interactions,
                "completeness": min(
                    (intermediary_interactions["contacted"] + intermediary_interactions["submitted"]) / 3,
                    1.0,
                ),
            }
        else:
            source_coverage["Candidatures fonds"] = {"available": False, "completeness": 0}
            source_coverage["Interactions intermediaires"] = {"available": False, "completeness": 0}
    except Exception:
        source_coverage["Candidatures fonds"] = {"available": False, "completeness": 0}
        source_coverage["Interactions intermediaires"] = {"available": False, "completeness": 0}

    # Remplir les facteurs manquants avec des valeurs par defaut
    for key in SOLVABILITY_FACTORS:
        if key not in solvability_points:
            solvability_points[key] = {"score": 0, "details": "Donnees insuffisantes"}

    for key in GREEN_IMPACT_FACTORS:
        if key not in green_impact_points:
            green_impact_points[key] = {"score": 0, "details": "Donnees insuffisantes"}

    return solvability_points, green_impact_points, source_coverage, intermediary_interactions


def _build_engagement_details(interactions: dict) -> str:
    """Construire la description textuelle de l'engagement intermediaire."""
    parts = []
    if interactions.get("contacted", 0) > 0:
        parts.append(f"{interactions['contacted']} intermediaire(s) contacte(s)")
    if interactions.get("appointments", 0) > 0:
        parts.append(f"{interactions['appointments']} rendez-vous")
    if interactions.get("submitted", 0) > 0:
        parts.append(f"{interactions['submitted']} dossier(s) soumis")
    if interactions.get("accepted", 0) > 0:
        parts.append(f"{interactions['accepted']} accepte(s)")
    return ", ".join(parts) if parts else "Aucune interaction avec les intermediaires"


# --- Operations CRUD ---


async def get_latest_score(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> CreditScore | None:
    """Recuperer le score le plus recent d'un utilisateur."""
    result = await db.execute(
        select(CreditScore)
        .where(CreditScore.user_id == user_id)
        .order_by(CreditScore.generated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_next_version(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> int:
    """Obtenir le prochain numero de version pour un utilisateur."""
    result = await db.execute(
        select(func.max(CreditScore.version)).where(CreditScore.user_id == user_id)
    )
    max_version = result.scalar()
    return (max_version or 0) + 1


async def get_score_history(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 10,
    offset: int = 0,
) -> tuple[list[CreditScore], int]:
    """Recuperer l'historique des scores avec pagination."""
    base_query = select(CreditScore).where(CreditScore.user_id == user_id)

    # Total
    count_query = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Resultats pagines
    query = base_query.order_by(CreditScore.generated_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    scores = list(result.scalars().all())

    return scores, total


async def is_generation_in_progress(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> bool:
    """Verifier si une generation est en cours (via credit_data.generating dans un state recemment)."""
    # Verification simple : aucun score avec generated_at dans les 10 dernieres secondes
    # (indicateur de generation en cours)
    ten_seconds_ago = datetime.now(tz=timezone.utc) - timedelta(seconds=10)
    result = await db.execute(
        select(func.count()).select_from(
            select(CreditScore)
            .where(
                CreditScore.user_id == user_id,
                CreditScore.generated_at >= ten_seconds_ago,
            )
            .subquery()
        )
    )
    return (result.scalar() or 0) > 0


async def generate_credit_score(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID | None = None,
) -> CreditScore:
    """Generer un nouveau score de credit vert complet.

    F02 multi-tenant : `account_id` est requis par la RLS (policy WITH CHECK
    `account_id IS NOT NULL`). Si non fourni, on le resout depuis l'utilisateur.

    1. Collecter les data points
    2. Calculer solvabilite et impact vert
    3. Calculer la confiance
    4. Calculer le score combine
    5. Generer les recommandations
    6. Persister en BDD
    """
    # Verrou anti-generation simultanee
    if await is_generation_in_progress(db, user_id):
        raise ValueError("Une generation de score est deja en cours. Veuillez patienter.")

    # F02 — resoudre account_id (sinon l'INSERT est rejete par la RLS)
    if account_id is None:
        from app.models.user import User as _User

        result = await db.execute(select(_User).where(_User.id == user_id))
        user_obj = result.scalar_one_or_none()
        if user_obj is None or user_obj.account_id is None:
            raise ValueError(
                "generate_credit_score: account_id introuvable pour l'utilisateur."
            )
        account_id = user_obj.account_id

    # Collecter les donnees
    solvability_points, green_impact_points, source_coverage, intermediary_interactions = (
        await collect_data_points(db, user_id)
    )

    # Calculer les scores
    solvability_score, solvability_factors = calculate_solvability_score(solvability_points)
    green_impact_score, green_impact_factors = calculate_green_impact_score(green_impact_points)

    # Calculer la confiance
    confidence_level, confidence_label = calculate_confidence(source_coverage)

    # Score combine
    combined_score = calculate_combined_score(solvability_score, green_impact_score, confidence_level)

    # Recommandations
    recommendations = generate_recommendations(
        solvability_factors,
        green_impact_factors,
        source_coverage,
        intermediary_interactions,
    )

    # Construire le breakdown
    score_breakdown = {
        "solvability": {
            "total": solvability_score,
            "factors": solvability_factors,
        },
        "green_impact": {
            "total": green_impact_score,
            "factors": green_impact_factors,
        },
    }

    # Construire les data_sources
    data_sources = {
        "sources": [
            {
                "name": name,
                "available": source_coverage.get(name, {}).get("available", False),
                "completeness": source_coverage.get(name, {}).get("completeness", 0),
                "last_updated": source_coverage.get(name, {}).get("last_updated"),
            }
            for name in DATA_SOURCES
        ],
        "overall_coverage": round(
            sum(
                1 for name in DATA_SOURCES
                if source_coverage.get(name, {}).get("available", False)
            )
            / len(DATA_SOURCES),
            2,
        ),
    }

    # Persister
    now = datetime.now(tz=timezone.utc)
    version = await get_next_version(db, user_id)

    credit_score = CreditScore(
        user_id=user_id,
        account_id=account_id,
        version=version,
        solvability_score=solvability_score,
        green_impact_score=green_impact_score,
        combined_score=combined_score,
        score_breakdown=score_breakdown,
        data_sources=data_sources,
        confidence_level=confidence_level,
        confidence_label=confidence_label,
        recommendations=recommendations,
        generated_at=now,
        valid_until=now + timedelta(days=SCORE_VALIDITY_MONTHS * 30),
    )
    db.add(credit_score)
    await db.flush()

    return credit_score
