"""F23 — Loader contextuel de Skills (Playbooks Métier).

Charge dynamiquement 1 à 2 skills publiées en fonction du contexte utilisateur
(page_slug, active_module, intent, offer_id, fund_id, intermediary_id) via
un score de spécificité multi-critères.

Référence : ``specs/033-skills-playbooks-metier/research.md`` R1.

Notes performance :
- Requête SQL filtre uniquement sur ``status='published'`` + ``valid_to``.
- Le scoring est fait en Python (volumétrie attendue ≤ 100 skills).
- L'index GIN PG sur ``activation_rules`` accélère les requêtes plus avancées
  (ex : pré-filtrage par page_slug) mais le MVP reste simple et lisible.
- Top 2 retournées (cap budget tokens system prompt 12k).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, SkillStatus

logger = logging.getLogger(__name__)


# Cap maximum de skills chargées par tour (cf. plan.md "Performance Goals").
MAX_SKILLS_LOADED: int = 2


def _specificity_score(skill: Any, ctx: dict[str, Any]) -> float:
    """Calcule le score de spécificité d'une skill pour un contexte donné.

    Plus le score est élevé, plus la skill est pertinente. Le score est
    additif : plusieurs critères peuvent se cumuler.

    Args:
        skill: Objet ``Skill`` (ou mock avec ``activation_rules``).
        ctx: Dict du contexte utilisateur (page_slug, active_module, intent,
             offer_id, fund_id, intermediary_id).

    Returns:
        Float ≥ 0. Score 0 = aucun match.
    """
    rules: dict[str, Any] = skill.activation_rules or {}
    score: float = 0.0

    # Niveau 4 — offer_id explicite (le plus spécifique).
    if (
        rules.get("offer_id")
        and ctx.get("offer_id")
        and rules.get("offer_id") == ctx.get("offer_id")
    ):
        score += 4.0

    # Niveau 3 — combo fund_id + intermediary_id (moins spécifique qu'offer_id).
    if (
        rules.get("fund_id")
        and rules.get("intermediary_id")
        and ctx.get("fund_id")
        and ctx.get("intermediary_id")
        and rules.get("fund_id") == ctx.get("fund_id")
        and rules.get("intermediary_id") == ctx.get("intermediary_id")
    ):
        score += 3.0

    # Niveau 2 — fund_id seul OU intermediary_id seul.
    if rules.get("fund_id") and ctx.get("fund_id") and rules.get("fund_id") == ctx.get(
        "fund_id"
    ):
        score += 2.0
    if (
        rules.get("intermediary_id")
        and ctx.get("intermediary_id")
        and rules.get("intermediary_id") == ctx.get("intermediary_id")
    ):
        score += 2.0

    # Niveau 1.5 — active_module.
    active_module = ctx.get("active_module")
    if active_module and active_module in (rules.get("active_module") or []):
        score += 1.5

    # Niveau 1 — page_slug.
    page_slug = ctx.get("page_slug")
    if page_slug and page_slug in (rules.get("page_slugs") or []):
        score += 1.0

    # Niveau 0.5 — intent_keywords (au moins 1 keyword présent).
    intent = (ctx.get("intent") or "").lower()
    keywords = rules.get("intent_keywords") or []
    if intent and any(kw.lower() in intent for kw in keywords):
        score += 0.5

    return score


async def load_skills_for_context(
    *,
    page_slug: str | None,
    active_module: str | None,
    intent: str | None,
    offer_id: str | None,
    fund_id: str | None,
    intermediary_id: str | None,
    db: AsyncSession,
) -> list[Skill]:
    """Retourne 0 à 2 skills publiées pertinentes pour le contexte.

    Critères de filtrage SQL :
    - ``status='published'``
    - ``valid_to IS NULL OR valid_to > today()``

    Tri en Python par ``(score décroissant, name croissant)`` pour
    déterminisme à score équivalent. Cap MAX_SKILLS_LOADED.

    Args:
        page_slug: URL de la page actuelle (ex "/esg", "/applications").
        active_module: Module actif (ex "esg_scoring", "application").
        intent: Intent utilisateur libre (last user message).
        offer_id, fund_id, intermediary_id: UUIDs strictement matchés.
        db: Session SQLAlchemy async.

    Returns:
        Liste de ``Skill`` triées (top 2). Liste vide si aucun match.
    """
    today = date.today()
    stmt = (
        select(Skill)
        .where(Skill.status == SkillStatus.PUBLISHED.value)
        .where(or_(Skill.valid_to.is_(None), Skill.valid_to > today))
    )
    result = await db.execute(stmt)
    candidates = list(result.scalars().all())

    ctx: dict[str, Any] = {
        "page_slug": page_slug,
        "active_module": active_module,
        "intent": intent,
        "offer_id": offer_id,
        "fund_id": fund_id,
        "intermediary_id": intermediary_id,
    }

    scored: list[tuple[float, str, Skill]] = []
    for skill in candidates:
        score = _specificity_score(skill, ctx)
        if score > 0:
            scored.append((score, skill.name, skill))

    # Tri : score desc, puis name asc pour déterminisme.
    scored.sort(key=lambda triple: (-triple[0], triple[1]))
    selected = [triple[2] for triple in scored[:MAX_SKILLS_LOADED]]

    if selected:
        logger.info(
            "[skill_loader] loaded %d skills for ctx=%s : %s",
            len(selected),
            {
                k: v
                for k, v in ctx.items()
                if v is not None
            },
            [s.name for s in selected],
        )
    return selected
