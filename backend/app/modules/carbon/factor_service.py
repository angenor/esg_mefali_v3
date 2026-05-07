"""Service de selection de facteur d'emission par pays/annee (F17).

Fournit la fonction ``get_emission_factor(db, category, country, year)``
qui retourne le facteur le plus pertinent selon une priorite stricte :

    (1) country exact + year exact
    (2) country exact + year anterieure la plus recente
    (3) global + year exact
    (4) global + year anterieure la plus recente

Si aucun match : leve ``EmissionFactorNotFoundError``.

Le flag ``is_approximate`` est ``True`` quand :
    - le pays demande n'est pas couvert (fallback global), OU
    - la difference d'annee est superieure a 3 ans.

Seuls les facteurs ``publication_status='published'`` sont consideres.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.emission_factor import EmissionFactor
from app.models.source import PublicationStatus


_GLOBAL_COUNTRY = "global"
# Ecart d'annee tolere avant de marquer le facteur comme approximatif.
_APPROXIMATE_YEAR_DIFF = 3


@dataclass(frozen=True)
class EmissionFactorResolution:
    """Resultat d'une recherche de facteur d'emission.

    Attributes:
        factor: Le facteur d'emission selectionne.
        is_approximate: True si le facteur est degrade (annee > 3 ans
            anterieure ou pays global).
        fallback_reason: Raison du fallback (``year_older``,
            ``country_global``) ou ``None`` si match exact.
    """

    factor: EmissionFactor
    is_approximate: bool
    fallback_reason: str | None


class EmissionFactorNotFoundError(LookupError):
    """Levee quand aucun facteur n'est trouve, meme global.

    Args:
        category: Categorie demandee.
        country: Pays demande (code ISO 2 lettres ou None).
        year: Annee demandee.
    """

    def __init__(
        self, category: str, country: str | None, year: int
    ) -> None:
        self.category = category
        self.country = country
        self.year = year
        super().__init__(
            f"Aucun facteur d'emission trouve pour la categorie '{category}' "
            f"(pays={country or 'aucun'}, annee={year})."
        )


async def _query_best_factor(
    db: AsyncSession,
    category: str,
    country: str,
    year: int,
) -> EmissionFactor | None:
    """Cherche le meilleur facteur pour ``(category, country)`` :
    priorise ``year`` exact, puis annee anterieure la plus recente.
    Filtre sur ``publication_status='published'``.
    """
    stmt = (
        select(EmissionFactor)
        .where(
            EmissionFactor.category == category,
            EmissionFactor.country == country,
            EmissionFactor.year <= year,
            EmissionFactor.publication_status == PublicationStatus.PUBLISHED.value,
        )
        .order_by(EmissionFactor.year.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_emission_factor(
    db: AsyncSession,
    category: str,
    country: str | None,
    year: int,
) -> EmissionFactorResolution:
    """Selectionne le facteur d'emission selon priorite pays/annee.

    Args:
        db: Session SQLAlchemy async.
        category: Categorie d'emission (ex. ``electricity``, ``fuel_diesel``,
            ``purchases_cement``).
        country: Code ISO 2 lettres (CI, SN, BF, ...) ou None pour fallback
            global.
        year: Annee de reference du calcul.

    Returns:
        EmissionFactorResolution contenant le facteur, le flag
        ``is_approximate`` et la ``fallback_reason``.

    Raises:
        EmissionFactorNotFoundError: si aucun facteur (pays + global) n'est
            trouve pour cette categorie.
    """
    # 1. Tentative country-specific (si fourni).
    factor = None
    fallback_reason: str | None = None

    if country and country != _GLOBAL_COUNTRY:
        factor = await _query_best_factor(db, category, country, year)
        if factor is not None:
            year_diff = year - factor.year
            if year_diff == 0:
                # Match exact pays + annee.
                return EmissionFactorResolution(
                    factor=factor,
                    is_approximate=False,
                    fallback_reason=None,
                )
            # Pays exact + annee anterieure : approximatif si > 3 ans.
            return EmissionFactorResolution(
                factor=factor,
                is_approximate=year_diff > _APPROXIMATE_YEAR_DIFF,
                fallback_reason="year_older",
            )

        # Pays demande mais aucun facteur trouve : fallback global.
        fallback_reason = "country_global"

    # 2. Fallback global : country=None ou pas de match country-specific.
    factor = await _query_best_factor(db, category, _GLOBAL_COUNTRY, year)
    if factor is None:
        raise EmissionFactorNotFoundError(category, country, year)

    # Le fallback global est toujours marque approximatif si un pays etait
    # demande au depart. Sinon (country=None ou 'global'), la valeur est
    # toujours considere approximative car non country-specific.
    is_approximate = True
    if fallback_reason is None:
        # country est None ou == 'global' a l'entree : on considere
        # toujours le fallback global comme approximatif (le LLM doit
        # informer l'utilisateur).
        fallback_reason = "country_global"

    return EmissionFactorResolution(
        factor=factor,
        is_approximate=is_approximate,
        fallback_reason=fallback_reason,
    )
